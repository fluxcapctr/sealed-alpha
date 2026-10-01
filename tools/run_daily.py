"""
Daily pipeline orchestrator: detect new sets, scrape prices, compute signals, refresh analytics.

Every step runs even if an earlier one fails, but the run exits non-zero (so the CI job
goes red and GitHub emails you) when anything went wrong: too many failed searches, price
coverage below MIN_PRICE_COVERAGE, a failed analytics refresh, or any step raising. Problems
are listed under "problems" in .tmp/daily_run_log.json.

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
    """Run the price scraper using batch mode (by set, ~10x faster than per-product)."""
    from tools.scrape_prices import scrape_prices_batch

    results = await scrape_prices_batch(db, config)
    logger.info(
        f"[PRICES] Done: {results['success']} success, "
        f"{results['failed']} failed, {results['skipped']} skipped, "
        f"{results['sets_processed']} sets processed, "
        f"coverage {results['coverage']:.1%} of {results['expected']} products"
    )
    return results


def run_signal_engine(config: Config, db: Database) -> dict:
    """Compute signals for all products."""
    from tools.compute_signals import compute_and_store_signals

    outcome = compute_and_store_signals(db, db.get_product_analytics())
    results = {k: outcome[k] for k in ("computed", "alerts", "failed")}
    logger.info(
        f"[SIGNALS] Done: {results['computed']} computed, "
        f"{results['alerts']} alerts created, {results['failed']} failed"
    )
    return results


def refresh_analytics(db: Database) -> str | None:
    """Refresh the product_analytics materialized view. Returns an error message, or None on success."""
    try:
        db.refresh_analytics()
        logger.info("[ANALYTICS] Materialized view refreshed")
        return None
    except Exception as e:
        logger.error(f"[ANALYTICS] Failed to refresh: {e}")
        return f"analytics refresh failed: {e}"


def check_price_health(config: Config, prices: dict, sets_total: int) -> list[str]:
    """Turn the price scrape's numbers into a list of problems (empty = healthy)."""
    problems = []
    if prices.get("expected") and prices["coverage"] < config.min_price_coverage:
        problems.append(
            f"price coverage {prices['coverage']:.1%} is below the {config.min_price_coverage:.0%} minimum "
            f"({prices['unpriced_count']} of {prices['expected']} products unpriced)"
        )
    if sets_total and prices.get("queries_failed", 0) / sets_total > config.max_failed_query_fraction:
        problems.append(f"{prices['queries_failed']} of {sets_total} set searches failed")
    if prices.get("success", 0) == 0 and prices.get("expected", 0) > 0:
        problems.append("no price snapshots were written")
    return problems


async def main() -> int:
    parser = argparse.ArgumentParser(description="Daily pipeline orchestrator")
    parser.add_argument("--prices-only", action="store_true")
    parser.add_argument("--signals-only", action="store_true")
    parser.add_argument("--skip-onboard", action="store_true", help="Skip new set detection")
    parser.add_argument("--language", default=None, help="Filter by language (en, ja, or all). Default: all products")
    parser.add_argument("--skip-drip", action="store_true", help="Skip drip email sending")
    args = parser.parse_args()

    config = Config()
    db = Database(config)
    start = time.time()
    pipeline_results: dict = {"date": str(date.today())}
    problems: list[str] = []

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
                if error := refresh_analytics(db):
                    problems.append(error)
        except Exception as e:
            logger.error(f"[ONBOARD] Failed: {e}")
            pipeline_results["new_sets"] = {"error": str(e)}
            problems.append(f"new-set onboarding failed: {e}")

    # Step 1: Scrape prices
    if not args.signals_only:
        logger.info("\n--- Step 1: Scrape Prices ---")
        try:
            prices = await run_price_scraper(config, db, args.language)
            pipeline_results["prices"] = prices
            problems.extend(check_price_health(config, prices, prices["sets_processed"] + prices["queries_failed"]))
        except Exception as e:
            logger.error(f"[PRICES] Failed: {e}")
            pipeline_results["prices"] = {"error": str(e)}
            problems.append(f"price scrape failed: {e}")

    # Step 1b: Scrape quantities (updates today's snapshots with available_quantity)
    if not args.signals_only:
        logger.info("\n--- Step 1b: Scrape Quantities ---")
        try:
            from tools.scrape_prices import scrape_quantities_batch
            quantities = await scrape_quantities_batch(db, config)
            pipeline_results["quantities"] = quantities
            if quantities.get("aborted"):
                problems.append("quantity scrape aborted after repeated request failures")
            elif quantities["updated"] == 0 and quantities["failed"] > 0:
                problems.append(f"quantity scrape updated nothing ({quantities['failed']} requests failed)")
        except Exception as e:
            logger.error(f"[QUANTITIES] Failed: {e}")
            pipeline_results["quantities"] = {"error": str(e)}
            problems.append(f"quantity scrape failed: {e}")

    # Step 2: Refresh analytics (needs fresh price data)
    logger.info("\n--- Step 2: Refresh Analytics ---")
    if error := refresh_analytics(db):
        problems.append(error)

    # Step 3: Compute signals
    if not args.prices_only:
        logger.info("\n--- Step 3: Compute Signals ---")
        try:
            signals = run_signal_engine(config, db)
            pipeline_results["signals"] = signals
            if signals["failed"]:
                problems.append(f"{signals['failed']} signals could not be written")
        except Exception as e:
            logger.error(f"[SIGNALS] Failed: {e}")
            pipeline_results["signals"] = {"error": str(e)}
            problems.append(f"signal computation failed: {e}")

    # Step 4: Refresh analytics again (with fresh signals)
    logger.info("\n--- Step 4: Final Analytics Refresh ---")
    if error := refresh_analytics(db):
        problems.append(error)

    # Step 5: Send drip emails
    if not args.prices_only and not args.signals_only and not args.skip_drip:
        logger.info("\n--- Step 5: Send Drip Emails ---")
        try:
            from tools.send_drip_emails import send_drip_emails
            drip_result = send_drip_emails(db, config, dry_run=False)
            pipeline_results["drip"] = drip_result
            if drip_result.get("failed"):
                problems.append(f"{drip_result['failed']} drip email(s) failed to send")
            if drip_result.get("error"):
                problems.append(f"drip: {drip_result['error']}")
        except Exception as e:
            logger.error(f"[DRIP] Failed: {e}")
            pipeline_results["drip"] = {"error": str(e)}
            problems.append(f"drip emails failed: {e}")

    elapsed = time.time() - start
    pipeline_results["elapsed_seconds"] = round(elapsed, 1)
    pipeline_results["problems"] = problems
    pipeline_results["ok"] = not problems

    # Save run log
    output_path = config.tmp_dir / "daily_run_log.json"
    with open(output_path, "w") as f:
        json.dump(pipeline_results, f, indent=2)

    logger.info("=" * 60)
    if problems:
        logger.error(f"PIPELINE FINISHED WITH {len(problems)} PROBLEM(S) in {elapsed:.1f}s:")
        for problem in problems:
            logger.error(f"  - {problem}")
    else:
        logger.info(f"PIPELINE COMPLETE in {elapsed:.1f}s")
    logger.info(f"Log saved to {output_path}")
    logger.info("=" * 60)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
