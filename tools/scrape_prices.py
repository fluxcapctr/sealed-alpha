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
            if pp.get("printingType", "").lower() == "normal" or len(data) == 1:
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


TCGPLAYER_SEARCH_API = "https://mp-search-api.tcgplayer.com/v1/search/request"


async def scrape_prices_batch(db: Database, config: Config, set_filter: str | None = None) -> dict:
    """
    Batch-scrape prices using the TCGPlayer search API.

    Instead of one API call per product (753 calls), this queries by set name
    and matches returned products by tcgplayer_product_id (~63 calls total).
    """
    sets = db.get_sets()
    if set_filter:
        sets = [s for s in sets if s["id"] == set_filter]

    results = {"success": 0, "failed": 0, "skipped": 0, "sets_processed": 0}
    today = str(date.today())

    # Build lookup: tcgplayer_product_id -> product row
    all_products = db.get_products(is_active=True)
    tcg_id_to_product = {}
    for p in all_products:
        tcg_id = p.get("tcgplayer_product_id")
        if tcg_id:
            tcg_id_to_product[int(tcg_id)] = p

    logger.info(f"Batch scraping prices for {len(sets)} sets ({len(tcg_id_to_product)} products)...")

    search_payload = {
        "algorithm": "sales_synonym_v2",
        "from": 0,
        "size": 50,
        "filters": {
            "term": {
                "productLineName": ["pokemon"],
                "productTypeName": ["Sealed Products"],
            },
            "range": {},
            "match": {},
        },
        "listingSearch": {
            "filters": {
                "term": {},
                "range": {},
                "exclude": {"channelExclusion": 0},
            }
        },
        "context": {"cart": {}, "shippingCountry": "US", "userProfile": {}},
        "settings": {"useFuzzySearch": True, "didYouMean": {}},
        "sort": {},
    }

    async with httpx.AsyncClient(timeout=config.httpx_timeout) as client:
        for i, set_data in enumerate(sets):
            set_name = set_data["name"]
            logger.info(f"[{i + 1}/{len(sets)}] Fetching prices for set: {set_name}")

            try:
                resp = await client.post(
                    TCGPLAYER_SEARCH_API,
                    params={"q": set_name, "isList": "false"},
                    json=search_payload,
                    headers={"User-Agent": config.random_user_agent()},
                )

                if resp.status_code != 200:
                    logger.warning(f"  Search API returned {resp.status_code} for '{set_name}'")
                    results["failed"] += 1
                    continue

                data = resp.json()
                api_results = data.get("results", [{}])
                items = []
                for r in api_results:
                    items.extend(r.get("results", []))

                matched = 0
                for item in items:
                    raw_id = item.get("productId")
                    if raw_id is None:
                        continue
                    tcg_id = int(raw_id)

                    product = tcg_id_to_product.get(tcg_id)
                    if not product:
                        continue  # Not in our DB (e.g. "Other" type we skipped)

                    market_price = item.get("marketPrice")
                    lowest_price = item.get("lowestPrice")
                    total_listings = item.get("totalListings")

                    if market_price is None and lowest_price is None:
                        results["skipped"] += 1
                        continue

                    snapshot = PriceSnapshot(
                        product_id=product["id"],
                        snapshot_date=today,
                        market_price=float(market_price) if market_price else None,
                        low_price=float(lowest_price) if lowest_price else None,
                        total_listings=int(total_listings) if total_listings else None,
                    )

                    try:
                        db.insert_price_snapshot(snapshot)
                        results["success"] += 1
                        matched += 1
                    except Exception as e:
                        results["failed"] += 1
                        logger.error(f"  DB error for {product['name']}: {e}")

                results["sets_processed"] += 1
                logger.info(f"  Matched {matched} products with prices")

            except Exception as e:
                logger.error(f"  Error fetching set '{set_name}': {e}")
                results["failed"] += 1

            # Rate limiting between sets
            if i < len(sets) - 1:
                await asyncio.sleep(config.random_delay())

    return results


TCGPLAYER_LISTINGS_API = "https://mp-search-api.tcgplayer.com/v1/product"


async def fetch_product_quantity(
    tcgplayer_id: int, client: httpx.AsyncClient, config: Config
) -> int | None:
    """
    Fetch the total available quantity for a product from TCGPlayer's listings API.

    Calls /v1/product/{id}/listings with size=0 and aggregates the quantity buckets
    to compute the sum of all available units across all sellers.
    """
    url = f"{TCGPLAYER_LISTINGS_API}/{tcgplayer_id}/listings"
    payload = {
        "filters": {
            "term": {"sellerStatus": "Live", "channelId": [0]},
            "range": {"quantity": {"gte": 1}},
            "exclude": {"channelExclusion": 0},
        },
        "from": 0,
        "size": 0,
        "sort": {"field": "price+shipping", "order": "asc"},
        "context": {"shippingCountry": "US", "cart": {}},
        "aggregations": ["quantity"],
    }

    try:
        resp = await client.post(
            url,
            json=payload,
            headers={"User-Agent": config.random_user_agent()},
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        results = data.get("results", [{}])
        if not results:
            return None

        # Sum quantity * count from the aggregation buckets
        aggs = results[0].get("aggregations", {})
        qty_buckets = aggs.get("quantity", [])
        total_qty = sum(
            int(bucket["value"]) * int(bucket["count"])
            for bucket in qty_buckets
        )
        return total_qty if total_qty > 0 else None

    except Exception as e:
        logger.debug(f"Quantity fetch failed for {tcgplayer_id}: {e}")
        return None


async def scrape_quantities_batch(db: Database, config: Config) -> dict:
    """
    Scrape available_quantity for all active products using the listings API.

    This updates today's price_snapshots with the available_quantity field.
    Run AFTER scrape_prices_batch so the snapshot rows already exist.
    """
    products = db.get_products(is_active=True)
    today = str(date.today())

    results = {"updated": 0, "skipped": 0, "failed": 0}

    logger.info(f"Scraping quantities for {len(products)} products...")

    async with httpx.AsyncClient(timeout=config.httpx_timeout) as client:
        for i, product in enumerate(products):
            tcg_id = product.get("tcgplayer_product_id")
            if not tcg_id:
                results["skipped"] += 1
                continue

            qty = await fetch_product_quantity(int(tcg_id), client, config)

            if qty is not None:
                try:
                    # Update today's snapshot with the quantity
                    db.client.table("price_snapshots").update(
                        {"available_quantity": qty}
                    ).eq(
                        "product_id", product["id"]
                    ).eq(
                        "snapshot_date", today
                    ).execute()
                    results["updated"] += 1

                    if (i + 1) % 50 == 0:
                        logger.info(
                            f"  [{i + 1}/{len(products)}] {results['updated']} updated so far..."
                        )
                except Exception as e:
                    results["failed"] += 1
                    logger.error(f"  DB error for {product['name']}: {e}")
            else:
                results["skipped"] += 1

            # Light rate limiting (these are lightweight calls)
            if i < len(products) - 1:
                await asyncio.sleep(0.3)

    logger.info(
        f"Quantities done: {results['updated']} updated, "
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
