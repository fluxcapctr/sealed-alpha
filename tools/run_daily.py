"""
Daily pipeline orchestrator: detect new sets, scrape prices, compute signals, refresh analytics.

Usage:
    python tools/run_daily.py
    python tools/run_daily.py --prices-only
    python tools/run_daily.py --signals-only
    python tools/run_daily.py --skip-onboard
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

from config import Config
from db import Database

logger = logging.getLogger("daily_pipeline")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def run_price_scraper(config: Config, db: Database, language: str | None = None) -> dict:
    """Run the price scraper for all products due for scraping."""
    from tools.scrape_prices import scrape_product_price_api

    products = db.get_products_needing_scrape()
    # Filter by language if specified
    if language and language != "all":
        products = [p for p in products if p.get("language", "en") == language]
    logger.info(f"[PRICES] {len(products)} products due for scraping")

    results = {"success": 0, "failed": 0, "skipped": 0}

    for i, product in enumerate(products):
        try:
            snapshot = await scrape_product_price_api(product, config)
            if snapshot:
                db.insert_price_snapshot(snapshot)
                results["success"] += 1
            else:
                results["skipped"] += 1
        except Exception as e:
            results["failed"] += 1
            logger.error(f"  Price scrape failed for {product['name']}: {e}")

        if i < len(products) - 1:
            await asyncio.sleep(config.random_delay())

    logger.info(
        f"[PRICES] Done: {results['success']} success, "
        f"{results['failed']} failed, {results['skipped']} skipped"
    )
    return results


def run_signal_engine(config: Config, db: Database) -> dict:
    """Compute signals for all products."""
    from tools.compute_signals import compute_signal, check_for_alerts

    analytics_list = db.get_product_analytics()
    results = {"computed": 0, "alerts": 0}

    for analytics in analytics_list:
        if analytics.get("current_price") is None:
            continue

        signal = compute_signal(analytics)
        db.upsert_signal(signal)
        results["computed"] += 1

        # Check alerts
        alerts = check_for_alerts(signal, None, analytics)
        for alert in alerts:
            db.create_alert(alert)
            results["alerts"] += 1

    logger.info(
        f"[SIGNALS] Done: {results['computed']} computed, "
        f"{results['alerts']} alerts created"
    )
    return results


def refresh_analytics(db: Database) -> None:
    """Refresh the product_analytics materialized view."""
    try:
        db.refresh_analytics()
        logger.info("[ANALYTICS] Materialized view refreshed")
    except Exception as e:
        logger.error(f"[ANALYTICS] Failed to refresh: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Daily pipeline orchestrator")
    parser.add_argument("--prices-only", action="store_true")
    parser.add_argument("--signals-only", action="store_true")
    parser.add_argument("--skip-onboard", action="store_true", help="Skip new set detection")
    parser.add_argument("--language", default=None, help="Filter by language (en, ja, or all). Default: all products")
    args = parser.parse_args()

    config = Config()
    db = Database(config)
    start = time.time()
    pipeline_results = {"date": str(date.today())}

    logger.info("=" * 60)
    logger.info(f"DAILY PIPELINE — {date.today()}")
    logger.info("=" * 60)

    # Step 0: Check for new sets
    if not args.prices_only and not args.signals_only and not args.skip_onboard:
        logger.info("\n--- Step 0: Check for New Sets ---")
        try:
            from tools.onboard_new_sets import onboard_new_sets
            onboard_result = await onboard_new_sets(config, db)
            pipeline_results["new_sets"] = onboard_result
            if onboard_result.get("new_sets", 0) > 0:
                logger.info(f"[ONBOARD] {onboard_result['new_sets']} new set(s) onboarded")
                # Refresh analytics so new products appear
                refresh_analytics(db)
        except Exception as e:
            logger.error(f"[ONBOARD] Failed: {e}")
            pipeline_results["new_sets"] = {"error": str(e)}

    # Step 1: Scrape prices
    if not args.signals_only:
        logger.info("\n--- Step 1: Scrape Prices ---")
        pipeline_results["prices"] = await run_price_scraper(config, db, args.language)

    # Step 2: Refresh analytics (needs fresh price data)
    logger.info("\n--- Step 2: Refresh Analytics ---")
    refresh_analytics(db)

    # Step 3: Compute signals
    if not args.prices_only:
        logger.info("\n--- Step 3: Compute Signals ---")
        pipeline_results["signals"] = run_signal_engine(config, db)

    # Step 4: Refresh analytics again (with fresh signals)
    logger.info("\n--- Step 4: Final Analytics Refresh ---")
    refresh_analytics(db)

    elapsed = time.time() - start
    pipeline_results["elapsed_seconds"] = round(elapsed, 1)

    # Save run log
    output_path = config.tmp_dir / "daily_run_log.json"
    with open(output_path, "w") as f:
        json.dump(pipeline_results, f, indent=2)

    logger.info("=" * 60)
    logger.info(f"PIPELINE COMPLETE in {elapsed:.1f}s")
    logger.info(f"Log saved to {output_path}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
