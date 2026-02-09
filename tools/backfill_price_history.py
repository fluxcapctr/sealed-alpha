"""
Backfill historical price data from TCGPlayer's price history API.

Uses the infinite-api.tcgplayer.com endpoint to fetch weekly market prices
going back ~2.8 years. Inserts into price_snapshots using upsert to avoid
duplicating existing daily scraper data.

Usage:
    python tools/backfill_price_history.py
    python tools/backfill_price_history.py --dry-run
    python tools/backfill_price_history.py --product-id <uuid>
    python tools/backfill_price_history.py --set-name "Battle Styles"
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from config import Config
from db import Database
from models import PriceSnapshot

logger = logging.getLogger("backfill_prices")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
# Silence verbose httpx request logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

PRICE_HISTORY_URL = "https://infinite-api.tcgplayer.com/price/history/{product_id}/detailed"

# Valid range values: month (daily, 30d), quarter (3-day, 90d),
# annual (weekly, 1yr), alltime (weekly, ~2.8yr)
DEFAULT_RANGE = "alltime"

HEADERS = {
    "referer": "https://www.tcgplayer.com/",
    "accept": "*/*",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
}


async def fetch_price_history(
    client: httpx.AsyncClient,
    tcgplayer_product_id: int,
    range_param: str = DEFAULT_RANGE,
    max_retries: int = 3,
) -> list[dict]:
    """Fetch historical price buckets for a product from TCGPlayer."""
    url = PRICE_HISTORY_URL.format(product_id=tcgplayer_product_id)

    for attempt in range(max_retries):
        headers = {
            **HEADERS,
            "x-pagerequest-id": f"{int(time.time() * 1000)}:www.tcgplayer.com",
        }

        resp = await client.get(url, params={"range": range_param}, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            results = data.get("result", [])
            if not results:
                return []
            return results[0].get("buckets", [])

        if resp.status_code == 403 and attempt < max_retries - 1:
            wait = 30 * (attempt + 1)  # 30s, 60s
            logger.info(
                f"  Rate limited (403) for tcg_id={tcgplayer_product_id}, "
                f"waiting {wait}s (attempt {attempt + 1}/{max_retries})"
            )
            await asyncio.sleep(wait)
            continue

        logger.warning(
            f"  HTTP {resp.status_code} for tcg_id={tcgplayer_product_id}"
        )
        return []

    return []


def buckets_to_snapshots(
    buckets: list[dict], product_id: str
) -> list[PriceSnapshot]:
    """Convert TCGPlayer price history buckets to PriceSnapshot models."""
    snapshots = []
    for bucket in buckets:
        market_price_str = bucket.get("marketPrice")
        if not market_price_str:
            continue

        market_price = float(market_price_str)
        if market_price <= 0:
            continue

        snapshot_date = bucket.get("bucketStartDate")
        if not snapshot_date:
            continue

        # Extract low/high sale prices if available
        low_price = None
        high_price = None
        low_str = bucket.get("lowSalePrice")
        high_str = bucket.get("highSalePrice")
        if low_str and float(low_str) > 0:
            low_price = float(low_str)
        if high_str and float(high_str) > 0:
            high_price = float(high_str)

        snapshots.append(
            PriceSnapshot(
                product_id=product_id,
                snapshot_date=snapshot_date,
                market_price=market_price,
                low_price=low_price,
                high_price=high_price,
            )
        )

    return snapshots


async def backfill_product(
    client: httpx.AsyncClient,
    product: dict,
    db: Database,
    dry_run: bool = False,
    range_param: str = DEFAULT_RANGE,
    force: bool = False,
) -> dict:
    """Backfill price history for a single product."""
    product_id = product["id"]
    tcg_id = product.get("tcgplayer_product_id")
    name = product.get("name", "?")

    if not tcg_id:
        return {"name": name, "status": "no_tcg_id", "count": 0}

    # Skip products that already have historical data (>30 snapshots)
    if not force and not dry_run:
        existing = (
            db.client.table("price_snapshots")
            .select("snapshot_date", count="exact")
            .eq("product_id", product_id)
            .execute()
        )
        if existing.count and existing.count > 30:
            return {"name": name, "status": "skipped", "count": 0}

    buckets = await fetch_price_history(client, tcg_id, range_param)
    if not buckets:
        return {"name": name, "status": "no_data", "count": 0}

    snapshots = buckets_to_snapshots(buckets, product_id)
    if not snapshots:
        return {"name": name, "status": "no_valid_prices", "count": 0}

    if dry_run:
        earliest = snapshots[-1].snapshot_date
        latest = snapshots[0].snapshot_date
        logger.info(
            f"  [DRY RUN] {name}: {len(snapshots)} snapshots "
            f"({earliest} to {latest})"
        )
        return {"name": name, "status": "dry_run", "count": len(snapshots)}

    # Batch upsert all snapshots for this product in one call
    rows = [snap.to_dict() for snap in snapshots]
    try:
        db.client.table("price_snapshots").upsert(
            rows, on_conflict="product_id,snapshot_date"
        ).execute()
        inserted = len(rows)
    except Exception as e:
        logger.warning(f"  Batch insert failed for {name}: {e}")
        inserted = 0

    earliest = snapshots[-1].snapshot_date
    latest = snapshots[0].snapshot_date
    logger.info(
        f"  {name}: {inserted}/{len(snapshots)} snapshots "
        f"({earliest} to {latest})"
    )
    return {"name": name, "status": "ok", "count": inserted}


async def backfill_all(
    config: Config,
    db: Database,
    dry_run: bool = False,
    product_id: str | None = None,
    set_name: str | None = None,
    range_param: str = DEFAULT_RANGE,
    force: bool = False,
) -> dict:
    """Backfill historical prices for all (or filtered) products."""
    start = time.time()

    products = db.get_products(is_active=True)

    if product_id:
        products = [p for p in products if p["id"] == product_id]
    elif set_name:
        set_name_lower = set_name.lower()
        products = [
            p
            for p in products
            if p.get("sets", {}).get("name", "").lower() == set_name_lower
        ]

    logger.info(f"Backfilling {len(products)} products (range={range_param})")

    results = []
    success = 0
    skipped = 0
    total_snapshots = 0
    api_calls = 0  # Track actual API calls for rate limit cooling
    next_cool_at = 100  # Next api_calls threshold to trigger a cooldown

    async with httpx.AsyncClient(timeout=15) as client:
        for i, product in enumerate(products):
            result = await backfill_product(
                client, product, db, dry_run, range_param, force
            )
            results.append(result)

            if result["status"] == "ok" or result["status"] == "dry_run":
                success += 1
                total_snapshots += result["count"]
                api_calls += 1
            elif result["status"] == "skipped":
                skipped += 1
            elif result["status"] in ("no_data", "no_valid_prices"):
                api_calls += 1

            # Only delay on actual API calls (not skips)
            if result["status"] not in ("skipped", "no_tcg_id") and i < len(products) - 1:
                await asyncio.sleep(0.5)

            # Cooling period: pause 60s every 100 API calls to avoid rate limit
            if api_calls >= next_cool_at:
                logger.info(f"  Cooling period: pausing 60s after {api_calls} API calls...")
                await asyncio.sleep(60)
                next_cool_at = api_calls + 100

            if (i + 1) % 50 == 0:
                logger.info(f"  Progress: {i + 1}/{len(products)} ({skipped} skipped, {success} ok)")

    elapsed = time.time() - start

    logger.info("=" * 50)
    logger.info(f"Backfill complete in {elapsed:.1f}s")
    logger.info(f"  Products processed: {len(products)}")
    logger.info(f"  Successful: {success}")
    logger.info(f"  Total snapshots: {total_snapshots}")
    no_data = sum(1 for r in results if r["status"] == "no_data")
    no_tcg = sum(1 for r in results if r["status"] == "no_tcg_id")
    if skipped:
        logger.info(f"  Skipped (already backfilled): {skipped}")
    if no_data:
        logger.info(f"  No data returned: {no_data}")
    if no_tcg:
        logger.info(f"  No TCGPlayer ID: {no_tcg}")
    logger.info("=" * 50)

    return {
        "products": len(products),
        "success": success,
        "total_snapshots": total_snapshots,
        "elapsed": round(elapsed, 1),
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Backfill historical price data from TCGPlayer"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be backfilled without inserting",
    )
    parser.add_argument(
        "--product-id",
        help="Backfill a single product by UUID",
    )
    parser.add_argument(
        "--set-name",
        help="Backfill products for a specific set",
    )
    parser.add_argument(
        "--range",
        default=DEFAULT_RANGE,
        choices=["month", "quarter", "annual", "alltime"],
        help="Time range to fetch (default: alltime)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even for products that already have historical data",
    )
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    await backfill_all(
        config,
        db,
        dry_run=args.dry_run,
        product_id=args.product_id,
        set_name=args.set_name,
        range_param=args.range,
        force=args.force,
    )


if __name__ == "__main__":
    asyncio.run(main())
