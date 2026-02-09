#!/usr/bin/env python3
"""
Scrape TCGPlayer 90-day sales metrics (total sold, avg daily sold).

Uses the TCGPlayer price history API with range=quarter to get aggregate
sales data per product. Stores results in the sales_snapshots table.

Usage:
    python tools/scrape_sales_data.py
    python tools/scrape_sales_data.py --dry-run
    python tools/scrape_sales_data.py --product-id <uuid>
    python tools/scrape_sales_data.py --set-name "Journey Together"
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import date

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from config import Config
from db import Database
from models import SalesSnapshot

config = Config()

logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

TCGPLAYER_HISTORY_URL = (
    "https://infinite-api.tcgplayer.com/price/history/{tcg_id}/detailed?range=quarter"
)

HEADERS = {
    "accept": "application/json",
    "referer": "https://www.tcgplayer.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}

DELAY = 0.5  # seconds between requests
COOL_EVERY = 80  # cool down every N API calls (reduced from 100)
COOL_SECONDS = 60

# Sentinel for rate limiting vs genuine no-data
RATE_LIMITED = "RATE_LIMITED"


async def fetch_sales_data(
    client: httpx.AsyncClient, tcg_id: int
) -> dict | str | None:
    """Fetch 90-day sales data from TCGPlayer.

    Returns:
        dict: sales data on success
        "RATE_LIMITED": on 403
        None: on genuine no-data or other errors
    """
    url = TCGPLAYER_HISTORY_URL.format(tcg_id=tcg_id)
    headers = {
        **HEADERS,
        "x-pagerequest-id": f"{int(time.time() * 1000)}:www.tcgplayer.com",
    }

    try:
        r = await client.get(url, headers=headers, timeout=15)

        if r.status_code == 403:
            return RATE_LIMITED
        if r.status_code != 200:
            return None

        data = r.json()
        results = data.get("result", [])
        if not results:
            return None

        result = results[0]
        total_qty = int(result.get("totalQuantitySold", 0))
        avg_daily = float(result.get("averageDailyQuantitySold", 0))

        # Get low/high sale prices from buckets
        buckets = result.get("buckets", [])
        low_sale = None
        high_sale = None
        latest_market = None

        for b in buckets:
            low_str = b.get("lowSalePrice")
            high_str = b.get("highSalePrice")
            market_str = b.get("marketPrice")

            if low_str and float(low_str) > 0:
                val = float(low_str)
                if low_sale is None or val < low_sale:
                    low_sale = val

            if high_str and float(high_str) > 0:
                val = float(high_str)
                if high_sale is None or val > high_sale:
                    high_sale = val

            if market_str and float(market_str) > 0:
                latest_market = float(market_str)

        return {
            "total_sold": total_qty,
            "avg_daily_sold": avg_daily,
            "low_sale": low_sale,
            "high_sale": high_sale,
            "market_price": latest_market,
        }

    except Exception as e:
        logger.warning(f"  Error fetching sales for TCG ID {tcg_id}: {e}")
        return None


async def main():
    parser = argparse.ArgumentParser(description="Scrape TCGPlayer 90-day sales data")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--product-id", help="Scrape a single product by UUID")
    parser.add_argument("--set-name", help="Only scrape products from this set")
    args = parser.parse_args()

    db = Database()
    today = str(date.today())

    # Get products to scrape
    query = db.client.from_("products").select(
        "id, name, tcgplayer_product_id, set_id"
    ).eq("is_active", True)

    if args.product_id:
        query = query.eq("id", args.product_id)

    result = query.execute()
    products = result.data or []

    # Filter by set name if specified
    if args.set_name:
        set_result = db.client.from_("sets").select("id").ilike("name", f"%{args.set_name}%").execute()
        set_ids = {s["id"] for s in (set_result.data or [])}
        products = [p for p in products if p["set_id"] in set_ids]

    # Only products with TCGPlayer IDs
    products = [p for p in products if p.get("tcgplayer_product_id")]

    # Skip products that already have sales data for today
    existing = db.client.from_("sales_snapshots").select(
        "product_id"
    ).eq("snapshot_date", today).execute()
    existing_ids = {r["product_id"] for r in (existing.data or [])}
    skipped = len([p for p in products if p["id"] in existing_ids])
    products = [p for p in products if p["id"] not in existing_ids]

    logger.info(f"Scraping sales data for {len(products)} products ({skipped} already have today's data)")
    if args.dry_run:
        logger.info("DRY RUN — no data will be written")

    stats = {"success": 0, "no_data": 0, "rate_limited": 0, "errors": 0}
    api_calls = 0
    next_cool_at = COOL_EVERY

    async with httpx.AsyncClient() as client:
        for i, product in enumerate(products):
            name = product["name"]
            tcg_id = product["tcgplayer_product_id"]
            product_id = product["id"]

            # Rate limit cooling
            if api_calls >= next_cool_at:
                logger.info(
                    f"  Cooling period: pausing {COOL_SECONDS}s after {api_calls} API calls..."
                )
                await asyncio.sleep(COOL_SECONDS)
                next_cool_at = api_calls + COOL_EVERY

            logger.info(f"[{i+1}/{len(products)}] {name} (TCG: {tcg_id})")

            data = await fetch_sales_data(client, tcg_id)
            api_calls += 1

            # Handle rate limiting with backoff + retry
            if data == RATE_LIMITED:
                stats["rate_limited"] += 1
                logger.warning(f"  Rate limited! Waiting 60s before retry...")
                await asyncio.sleep(60)
                data = await fetch_sales_data(client, tcg_id)
                api_calls += 1
                # If still rate limited, wait longer
                if data == RATE_LIMITED:
                    logger.warning(f"  Still rate limited. Waiting 120s...")
                    await asyncio.sleep(120)
                    data = await fetch_sales_data(client, tcg_id)
                    api_calls += 1
                # Reset cooling counter after rate limit recovery
                next_cool_at = api_calls + COOL_EVERY

            if data is None or data == RATE_LIMITED:
                stats["no_data"] += 1
                logger.info(f"  No sales data available")
                await asyncio.sleep(DELAY)
                continue

            logger.info(
                f"  Sold: {data['total_sold']} (90d), "
                f"Avg/day: {data['avg_daily_sold']:.1f}, "
                f"Range: ${data['low_sale'] or 0:.2f}-${data['high_sale'] or 0:.2f}"
            )

            if not args.dry_run:
                snap = SalesSnapshot(
                    product_id=product_id,
                    snapshot_date=today,
                    total_sales=data["total_sold"],
                    sale_count_24h=int(round(data["avg_daily_sold"])),
                    avg_sale_price=data["market_price"],
                    min_sale_price=data["low_sale"],
                    max_sale_price=data["high_sale"],
                )
                try:
                    db.insert_sales_snapshot(snap)
                    stats["success"] += 1
                except Exception as e:
                    logger.error(f"  DB error: {e}")
                    stats["errors"] += 1
            else:
                stats["success"] += 1

            await asyncio.sleep(DELAY)

    logger.info(f"\nDone! {stats}")
    logger.info(f"  Success: {stats['success']}")
    logger.info(f"  No data: {stats['no_data']}")
    logger.info(f"  Rate limited: {stats['rate_limited']}")
    logger.info(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    asyncio.run(main())
