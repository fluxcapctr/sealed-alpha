"""
Scrape current prices for sealed products from TCGPlayer.

For each active product in the database, fetches the current market price,
low/mid/high prices, listing count, and stores a PriceSnapshot.

Usage:
    python tools/scrape_prices.py
    python tools/scrape_prices.py --product-id UUID
    python tools/scrape_prices.py --set-id UUID
    python tools/scrape_prices.py --dry-run
    python tools/scrape_prices.py --scheduled  # Only scrape products that are due
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from config import Config
from db import Database
from models import PriceSnapshot
from tools.tcgplayer import (
    TcgPlayerError,
    clean_count,
    clean_price,
    fetch_listing_quantity,
    fetch_pricepoints,
    product_line_for,
    search_sealed,
)

logger = logging.getLogger("scrape_prices")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# TCGPlayer product API endpoint (discovered during investigation phase)
TCGPLAYER_PRODUCT_API = "https://mpapi.tcgplayer.com/v2/product"


async def scrape_product_price_api(
    product: dict, config: Config
) -> PriceSnapshot | None:
    """
    Fetch price data for a single product using TCGPlayer's API.

    This function tries the discovered API endpoints first. If those fail,
    it falls back to Playwright page scraping.
    """
    tcgplayer_id = product.get("tcgplayer_product_id")
    if not tcgplayer_id:
        logger.warning(f"No TCGPlayer ID for product: {product['name']}")
        return None

    # Try the direct product API
    url = f"{TCGPLAYER_PRODUCT_API}/{tcgplayer_id}/pricepoints"

    for attempt in range(config.max_retries):
        try:
            async with httpx.AsyncClient(timeout=config.httpx_timeout) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": config.random_user_agent(),
                        "Accept": "application/json",
                    },
                )

                if resp.status_code == 200:
                    data = resp.json()
                    return parse_price_response(product["id"], data)

                if resp.status_code == 429:
                    # Rate limited — back off
                    wait = config.retry_backoff_base ** (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code == 404:
                    logger.warning(f"Product not found on TCGPlayer: {tcgplayer_id}")
                    return None

                logger.warning(
                    f"API returned {resp.status_code} for product {tcgplayer_id}"
                )

        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching {tcgplayer_id} (attempt {attempt + 1})")
        except Exception as e:
            logger.error(f"Error fetching {tcgplayer_id}: {e}")

        if attempt < config.max_retries - 1:
            wait = config.retry_backoff_base ** (attempt + 1)
            await asyncio.sleep(wait)

    return None


async def scrape_product_price_playwright(
    product: dict, config: Config
) -> PriceSnapshot | None:
    """
    Fallback: scrape price data from the product page using Playwright.

    Used when API endpoints are unavailable or blocked.
    """
    from playwright.async_api import async_playwright

    tcgplayer_url = product.get("tcgplayer_url")
    if not tcgplayer_url:
        return None

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=config.random_user_agent(),
            )
            page = await context.new_page()

            # Capture API responses that load on the page
            price_data = {}

            async def on_response(response):
                if "pricepoints" in response.url or "marketprice" in response.url.lower():
                    try:
                        body = await response.json()
                        price_data["api"] = body
                    except Exception:
                        pass

            page.on("response", on_response)

            await page.goto(tcgplayer_url, wait_until="networkidle", timeout=config.playwright_timeout)
            await page.wait_for_timeout(2000)

            # If we captured API data, parse it
            if price_data.get("api"):
                await browser.close()
                return parse_price_response(product["id"], price_data["api"])

            # Otherwise parse the DOM
            snapshot = PriceSnapshot(
                product_id=product["id"],
                snapshot_date=str(date.today()),
            )

            # Try to extract prices from the page
            try:
                market_el = await page.query_selector('[class*="market-price"], [data-testid*="market"]')
                if market_el:
                    text = await market_el.inner_text()
                    snapshot.market_price = parse_dollar_amount(text)
            except Exception:
                pass

            try:
                listings_el = await page.query_selector('[class*="listing-count"], [data-testid*="listings"]')
                if listings_el:
                    text = await listings_el.inner_text()
                    snapshot.total_listings = int("".join(c for c in text if c.isdigit()) or "0")
            except Exception:
                pass

            await browser.close()

            if snapshot.market_price is not None:
                return snapshot

    except Exception as e:
        logger.error(f"Playwright scrape failed for {product['name']}: {e}")

    return None


def parse_price_response(product_id: str, data: dict | list) -> PriceSnapshot | None:
    """Parse a TCGPlayer price API response into a PriceSnapshot."""
    snapshot = PriceSnapshot(
        product_id=product_id,
        snapshot_date=str(date.today()),
    )

    # Handle different response formats
    if isinstance(data, list) and len(data) > 0:
        # Array of price points — find the "Normal" or first entry
        for pp in data:
            if (pp.get("printingType") or "").lower() == "normal" or len(data) == 1:
                snapshot.market_price = pp.get("marketPrice")
                snapshot.low_price = pp.get("lowPrice")
                snapshot.mid_price = pp.get("midPrice")
                snapshot.high_price = pp.get("highPrice")
                snapshot.listed_median_price = pp.get("listedMedianPrice")
                snapshot.direct_low_price = pp.get("directLowPrice")
                break
        if snapshot.market_price is None and data:
            pp = data[0]
            snapshot.market_price = pp.get("marketPrice")
            snapshot.low_price = pp.get("lowPrice")
            snapshot.mid_price = pp.get("midPrice")
            snapshot.high_price = pp.get("highPrice")
    elif isinstance(data, dict):
        snapshot.market_price = data.get("marketPrice") or data.get("market_price")
        snapshot.low_price = data.get("lowPrice") or data.get("low_price")
        snapshot.mid_price = data.get("midPrice") or data.get("mid_price")
        snapshot.high_price = data.get("highPrice") or data.get("high_price")
        snapshot.total_listings = data.get("totalListings") or data.get("listings")

    if snapshot.market_price is None and snapshot.low_price is None:
        return None

    return snapshot


def parse_dollar_amount(text: str) -> float | None:
    """Parse a dollar amount from text like '$123.45'."""
    cleaned = "".join(c for c in text if c.isdigit() or c == ".")
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


# Products we hold but TCGPlayer's fuzzy set search did not return are priced one by
# one from the pricepoints endpoint. Cap it so a broken search can't turn the daily
# run into thousands of single requests.
MAX_FALLBACK_PRODUCTS = 150
# After this many quantity requests in a row fail, assume we are blocked and stop.
MAX_CONSECUTIVE_QUANTITY_FAILURES = 15


def snapshot_from_search_item(product_id: str, item: dict, snapshot_date: str) -> PriceSnapshot | None:
    """
    Build a snapshot from one search-result item, or None if it carries no usable price.

    - market_price is TCGPlayer's market price (identical to /pricepoints).
    - low_price is the cheapest single listing and can be an outlier, so the listed
      median is stored alongside it (the batch path used to drop it).
    - total_listings keeps 0 as 0; only a missing value is None.
    """
    market = clean_price(item.get("marketPrice"))
    low = clean_price(item.get("lowestPrice"))
    if market is None and low is None:
        return None
    return PriceSnapshot(
        product_id=product_id,
        snapshot_date=snapshot_date,
        market_price=market,
        low_price=low,
        listed_median_price=clean_price(item.get("medianPrice")),
        total_listings=clean_count(item.get("totalListings")),
    )


async def scrape_prices_batch(db: Database, config: Config, set_filter: str | None = None) -> dict:
    """
    Price every active product, ~1 search per set instead of 1 request per product.

    Each set is searched by name (fuzzy) and results are matched to our products by
    tcgplayer_product_id, so a price can never land on the wrong product. Because the
    search is fuzzy, a set whose name is generic ("Sword & Shield") can have more
    matches than one page, and a product can be missed entirely. This therefore:
      1. pages through up to 4 pages of results per set,
      2. prices any active product that no search returned via /pricepoints,
      3. writes all snapshots in bulk, and
      4. reports coverage (priced / expected) so the caller can fail loudly.
    """
    sets = db.get_sets()
    if set_filter:
        sets = [s for s in sets if s["id"] == set_filter]

    all_products = db.get_products(is_active=True)
    if set_filter:
        all_products = [p for p in all_products if p.get("set_id") == set_filter]

    tcg_id_to_product: dict[int, dict] = {}
    for p in all_products:
        tcg_id = clean_count(p.get("tcgplayer_product_id"))
        if tcg_id:
            tcg_id_to_product[tcg_id] = p

    today = str(date.today())
    snapshots: dict[str, PriceSnapshot] = {}  # product_id -> snapshot (one per product per day)
    seen_ids: set[int] = set()                # products TCGPlayer returned, priced or not
    results = {
        "success": 0, "failed": 0, "skipped": 0, "sets_processed": 0,
        "queries_failed": 0, "truncated_queries": 0, "fallback_priced": 0,
    }

    logger.info(f"Batch scraping prices for {len(sets)} sets ({len(tcg_id_to_product)} products)...")

    async with httpx.AsyncClient(timeout=config.httpx_timeout) as client:
        for i, set_data in enumerate(sets):
            set_name = set_data["name"]
            product_line = product_line_for(set_data.get("language", "en"))
            logger.info(f"[{i + 1}/{len(sets)}] Fetching prices for set: {set_name} ({product_line})")

            try:
                found = await search_sealed(client, set_name, product_line, config)
            except TcgPlayerError as e:
                logger.error(f"  Search failed for '{set_name}': {e}")
                results["queries_failed"] += 1
                results["failed"] += 1
                continue

            if found.truncated:
                results["truncated_queries"] += 1
                logger.warning(
                    f"  '{set_name}': only {len(found.items)} of {found.total} results fetched; "
                    "anything missing falls back to per-product pricing"
                )

            matched = 0
            for item in found.items:
                tcg_id = clean_count(item.get("productId"))
                product = tcg_id_to_product.get(tcg_id) if tcg_id else None
                if not product:
                    continue  # not one of ours (other set's product, or a type we don't track)
                seen_ids.add(tcg_id)
                if product["id"] in snapshots:
                    continue  # already priced from another set's results

                snapshot = snapshot_from_search_item(product["id"], item, today)
                if snapshot is None:
                    results["skipped"] += 1  # listed on TCGPlayer but no market price or listing
                    continue
                snapshots[product["id"]] = snapshot
                matched += 1

            results["sets_processed"] += 1
            logger.info(f"  Matched {matched} new products with prices")

            if i < len(sets) - 1:
                await asyncio.sleep(config.random_delay())

        # Fallback: products no search returned at all
        missing = [p for tcg_id, p in tcg_id_to_product.items() if tcg_id not in seen_ids]
        if missing:
            logger.warning(f"{len(missing)} active products were not in any search result; pricing individually")
        for product in missing[:MAX_FALLBACK_PRODUCTS]:
            try:
                data = await fetch_pricepoints(client, int(product["tcgplayer_product_id"]), config)
            except TcgPlayerError as e:
                logger.warning(f"  Fallback failed for {product['name']}: {e}")
                results["failed"] += 1
                continue
            snapshot = parse_price_response(product["id"], data)
            if snapshot is None:
                results["skipped"] += 1
            else:
                snapshot.market_price = clean_price(snapshot.market_price)
                snapshot.low_price = clean_price(snapshot.low_price)
                snapshot.listed_median_price = clean_price(snapshot.listed_median_price)
                if snapshot.market_price is None and snapshot.low_price is None:
                    results["skipped"] += 1
                else:
                    snapshots[product["id"]] = snapshot
                    results["fallback_priced"] += 1
            await asyncio.sleep(config.random_delay())

    # Write once, in bulk
    written, failed_rows = db.insert_price_snapshots(list(snapshots.values()))
    results["success"] = written
    results["failed"] += len(failed_rows)

    expected = len(tcg_id_to_product)
    unpriced = [p["name"] for p in tcg_id_to_product.values() if p["id"] not in snapshots]
    results["expected"] = expected
    results["coverage"] = round(len(snapshots) / expected, 4) if expected else 1.0
    results["unpriced_count"] = len(unpriced)
    results["unpriced_sample"] = unpriced[:25]
    if unpriced:
        logger.warning(f"{len(unpriced)}/{expected} active products have no price today, e.g. {unpriced[:5]}")
    return results


async def scrape_quantities_batch(db: Database, config: Config, snapshot_date: str | None = None) -> dict:
    """
    Scrape available_quantity for all active products using the listings API.

    This updates today's price_snapshots with the available_quantity field.
    Run AFTER scrape_prices_batch so the snapshot rows already exist.

    A real zero (no live listings) is stored as 0 so a sold-out product shows as sold
    out; a failed request stores nothing, so the previous quantity is never silently
    replaced and a failure is never mistaken for "sold out".
    """
    products = db.get_products(is_active=True)
    today = snapshot_date or str(date.today())

    results = {"updated": 0, "skipped": 0, "failed": 0, "no_snapshot": 0, "aborted": False}

    logger.info(f"Scraping quantities for {len(products)} products...")
    consecutive_failures = 0

    async with httpx.AsyncClient(timeout=config.httpx_timeout) as client:
        for i, product in enumerate(products):
            tcg_id = clean_count(product.get("tcgplayer_product_id"))
            if not tcg_id:
                results["skipped"] += 1
                continue

            try:
                qty = await fetch_listing_quantity(client, tcg_id, config)
            except TcgPlayerError as e:
                results["failed"] += 1
                consecutive_failures += 1
                logger.warning(f"  Quantity fetch failed for {product['name']}: {e}")
                if consecutive_failures >= MAX_CONSECUTIVE_QUANTITY_FAILURES:
                    logger.error(
                        f"{consecutive_failures} quantity requests failed in a row; "
                        "assuming we are blocked and stopping"
                    )
                    results["aborted"] = True
                    break
                continue
            consecutive_failures = 0

            try:
                rows = db.set_snapshot_quantity(product["id"], today, qty)
            except Exception as e:
                results["failed"] += 1
                logger.error(f"  DB error for {product['name']}: {e}")
                continue

            if rows:
                results["updated"] += 1
            else:
                results["no_snapshot"] += 1  # no price snapshot today to attach the quantity to

            if (i + 1) % 50 == 0:
                logger.info(f"  [{i + 1}/{len(products)}] {results['updated']} updated so far...")

            # Light rate limiting (these are lightweight calls)
            if i < len(products) - 1:
                await asyncio.sleep(0.3)

    logger.info(
        f"Quantities done: {results['updated']} updated, {results['no_snapshot']} without a snapshot, "
        f"{results['skipped']} skipped, {results['failed']} failed"
    )
    return results


async def main():
    parser = argparse.ArgumentParser(description="Scrape prices from TCGPlayer")
    parser.add_argument("--product-id", help="Scrape a specific product")
    parser.add_argument("--set-id", help="Scrape all products in a set")
    parser.add_argument("--scheduled", action="store_true", help="Only scrape products due for update")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be scraped")
    parser.add_argument("--batch", action="store_true", help="Batch scrape via search API (faster)")
    parser.add_argument("--quantities", action="store_true", help="Scrape available quantities per product")
    parser.add_argument("--use-playwright", action="store_true", help="Use Playwright instead of API")
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    # Quantity scraping mode
    if args.quantities:
        start_time = time.time()
        results = await scrape_quantities_batch(db, config)
        elapsed = time.time() - start_time
        output = {"elapsed_seconds": round(elapsed, 1), **results}
        output_path = config.tmp_dir / "scrape_quantities_results.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        logger.info(f"Done in {elapsed:.1f}s")
        return

    # Batch mode: use search API to get prices for all products by set
    if args.batch:
        start_time = time.time()
        results = await scrape_prices_batch(db, config, set_filter=args.set_id)
        elapsed = time.time() - start_time
        output = {"elapsed_seconds": round(elapsed, 1), **results}
        output_path = config.tmp_dir / "scrape_prices_results.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        logger.info(f"Done in {elapsed:.1f}s: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
        return

    # Determine which products to scrape
    if args.product_id:
        product = db.get_product_by_id(args.product_id)
        if not product:
            logger.error(f"Product not found: {args.product_id}")
            return
        products = [product]
    elif args.set_id:
        products = db.get_products(set_id=args.set_id)
    elif args.scheduled:
        products = db.get_products_needing_scrape()
    else:
        products = db.get_products(is_active=True)

    logger.info(f"Scraping prices for {len(products)} products...")

    if args.dry_run:
        for p in products:
            logger.info(f"  [DRY RUN] {p['name']} (TCG ID: {p.get('tcgplayer_product_id', '?')})")
        return

    results = {"success": 0, "failed": 0, "skipped": 0}
    scrape_fn = scrape_product_price_playwright if args.use_playwright else scrape_product_price_api
    start_time = time.time()

    for i, product in enumerate(products):
        logger.info(f"[{i + 1}/{len(products)}] {product['name']}...")

        try:
            snapshot = await scrape_fn(product, config)

            if snapshot:
                db.insert_price_snapshot(snapshot)
                results["success"] += 1
                logger.info(
                    f"  Price: ${snapshot.market_price} | Low: ${snapshot.low_price} | Listings: {snapshot.total_listings}"
                )
            else:
                results["skipped"] += 1
                logger.warning(f"  No price data returned")
        except Exception as e:
            results["failed"] += 1
            logger.error(f"  Error: {e}")

        # Rate limiting
        if i < len(products) - 1:
            await asyncio.sleep(config.random_delay())

    elapsed = time.time() - start_time

    # Save results
    output = {
        "total_products": len(products),
        "elapsed_seconds": round(elapsed, 1),
        **results,
    }
    output_path = config.tmp_dir / "scrape_prices_results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Done in {elapsed:.1f}s: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")


if __name__ == "__main__":
    asyncio.run(main())
