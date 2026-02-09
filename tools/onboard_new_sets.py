"""
Detect and fully onboard new Pokemon TCG sets into the database.

Checks the Pokemon TCG API for sets not yet in our database, then runs
the full onboarding pipeline: seed set, discover products, compute set
value, fetch logo, and set top card art.

Usage:
    python tools/onboard_new_sets.py
    python tools/onboard_new_sets.py --dry-run
    python tools/onboard_new_sets.py --force
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
from config import Config
from db import Database

# Reuse existing tool functions
from seed_sets import (
    fetch_sets_from_pokemon_api,
    filter_sets_by_year,
    api_set_to_model,
)
from seed_products import seed_products_for_set
from scrape_set_values import (
    fetch_pokedata_sets,
    build_set_mapping,
    fetch_set_cards,
    fetch_card_stats,
    PRICE_SOURCE,
    SKIP_SUBSETS,
)
from update_set_logos import POKELLECTOR_LOGOS
from update_top_cards import (
    find_top_cards,
    normalize_card_num,
    CODE_OVERRIDES,
    POKEMONTCG_IMAGE_BASE,
)

logger = logging.getLogger("onboard_new_sets")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)


async def detect_new_sets(config: Config, db: Database) -> list[dict]:
    """Compare Pokemon TCG API sets against DB and return those not yet seeded."""
    # Pokemon TCG API can be slow — retry up to 3 times
    api_sets = None
    for attempt in range(3):
        try:
            api_sets = await fetch_sets_from_pokemon_api(config)
            break
        except Exception as e:
            logger.warning(f"Pokemon TCG API attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                await asyncio.sleep(5)

    if api_sets is None:
        logger.error("Pokemon TCG API unavailable after 3 attempts - skipping")
        return []

    filtered = filter_sets_by_year(api_sets, config.min_set_year)

    # Get existing set codes from DB
    db_sets = db.get_sets()
    existing_codes = {s["code"] for s in db_sets if s.get("code")}

    new_sets = [s for s in filtered if s.get("id", "") not in existing_codes]
    return new_sets


async def onboard_set_value(
    client: httpx.AsyncClient,
    set_data: dict,
    pd_id: int,
    db: Database,
) -> bool:
    """Compute and store master set value for a single set."""
    cards = await fetch_set_cards(client, pd_id)
    if not cards:
        logger.warning("  No cards found on PokeDATA.io")
        return False

    card_ids = [c["id"] for c in cards]
    stats = await fetch_card_stats(client, card_ids)
    if not stats:
        logger.warning("  No card stats found on PokeDATA.io")
        return False

    # Compute total set value
    seen: set[str] = set()
    total_value = 0.0
    total_cards = 0

    for c in cards:
        num = c.get("num", "")
        if not num or num in seen:
            continue
        name = c.get("name", "")
        if "reverse" in name.lower():
            continue
        seen.add(num)
        total_cards += 1

    price_by_card: dict[int, float] = {}
    for stat in stats:
        if stat.get("source") == PRICE_SOURCE and stat.get("avg") is not None:
            price_by_card[stat["card_id"]] = stat["avg"]

    seen2: set[str] = set()
    for c in cards:
        num = c.get("num", "")
        if not num or num in seen2:
            continue
        name = c.get("name", "")
        if "reverse" in name.lower():
            continue
        seen2.add(num)
        total_value += price_by_card.get(c["id"], 0)

    if total_value > 0:
        db.client.table("sets").update({
            "total_set_value": round(total_value, 2),
            "total_cards": total_cards,
        }).eq("id", set_data["id"]).execute()
        logger.info(f"  Set value: ${total_value:.2f} ({total_cards} cards)")
        return True

    return False


async def onboard_set_top_card(
    client: httpx.AsyncClient,
    set_data: dict,
    pd_id: int,
    db: Database,
) -> bool:
    """Find and store the top card image URL for a set."""
    code = set_data.get("code")
    if not code:
        return False

    cards = await fetch_set_cards(client, pd_id)
    if not cards:
        return False

    card_ids = [c["id"] for c in cards]
    stats = await fetch_card_stats(client, card_ids)
    if not stats:
        return False

    top_cards = find_top_cards(cards, stats, count=1)
    if not top_cards:
        return False

    card_name, card_num, card_price = top_cards[0]
    img_code = CODE_OVERRIDES.get(code, code)
    clean_num = normalize_card_num(card_num)
    image_url = f"{POKEMONTCG_IMAGE_BASE}/{img_code}/{clean_num}_hires.png"

    db.client.table("sets").update(
        {"top_card_image_url": image_url}
    ).eq("id", set_data["id"]).execute()

    logger.info(f"  Top card: {card_name} #{card_num} (${card_price:.2f})")
    return True


async def onboard_single_set(
    api_set: dict,
    config: Config,
    db: Database,
    pokedata_sets: list[dict],
    dry_run: bool = False,
) -> dict:
    """Run the full onboarding pipeline for a single new set."""
    name = api_set.get("name", "?")
    code = api_set.get("id", "?")
    result = {
        "name": name,
        "code": code,
        "seeded": False,
        "products": 0,
        "value": False,
        "logo": False,
        "top_card": False,
    }

    logger.info(f"Onboarding: {name} ({code})")

    if dry_run:
        logger.info(f"  [DRY RUN] Would onboard {name}")
        return result

    # Step 1: Seed the set
    try:
        model = api_set_to_model(api_set)
        db.upsert_set(model)
        result["seeded"] = True
        logger.info(f"  Seeded set: {name}")
    except Exception as e:
        logger.error(f"  Failed to seed set: {e}")
        return result

    # Get the newly-created set from DB
    db_sets = db.get_sets()
    set_data = next((s for s in db_sets if s["code"] == code), None)
    if not set_data:
        logger.error(f"  Could not find set in DB after seeding")
        return result

    # Step 2: Discover and seed products
    try:
        prod_results = await seed_products_for_set(set_data, db, config)
        result["products"] = prod_results.get("seeded", 0)
        logger.info(f"  Products: {result['products']} seeded")
    except Exception as e:
        logger.error(f"  Failed to seed products: {e}")

    # Step 3: Set logo from Pokellector
    logo_url = POKELLECTOR_LOGOS.get(name)
    if logo_url:
        try:
            db.client.table("sets").update(
                {"image_url": logo_url}
            ).eq("id", set_data["id"]).execute()
            result["logo"] = True
            logger.info(f"  Logo: set from Pokellector")
        except Exception as e:
            logger.error(f"  Failed to set logo: {e}")
    else:
        logger.warning(f"  Logo: no Pokellector mapping for '{name}'")

    # Step 4: Set value + top card (PokeDATA.io)
    mapping = build_set_mapping(db_sets, pokedata_sets)
    pd_id = mapping.get(set_data["id"])

    if pd_id and name not in SKIP_SUBSETS:
        async with httpx.AsyncClient(timeout=30) as client:
            # Set value
            try:
                result["value"] = await onboard_set_value(
                    client, set_data, pd_id, db
                )
            except Exception as e:
                logger.error(f"  Failed to compute set value: {e}")

            await asyncio.sleep(0.3)

            # Top card
            if set_data.get("code"):
                try:
                    result["top_card"] = await onboard_set_top_card(
                        client, set_data, pd_id, db
                    )
                except Exception as e:
                    logger.error(f"  Failed to set top card: {e}")
    else:
        if not pd_id:
            logger.warning(f"  No PokeDATA.io mapping — skipping value + top card")
        if name in SKIP_SUBSETS:
            logger.info(f"  Sub-set — skipping value computation")

    # Reminder for manual pull rates
    logger.info(f"  NOTE: Pull rates need manual entry in seed_pull_rates.py")

    return result


async def onboard_new_sets(
    config: Config, db: Database, dry_run: bool = False, force: bool = False
) -> dict:
    """
    Main entry point: detect and onboard all new sets.
    Returns summary dict for pipeline logging.
    """
    start = time.time()

    # Detect new sets
    if force:
        api_sets = await fetch_sets_from_pokemon_api(config)
        new_api_sets = filter_sets_by_year(api_sets, config.min_set_year)
        logger.info(f"Force mode: re-checking all {len(new_api_sets)} sets")
    else:
        new_api_sets = await detect_new_sets(config, db)

    if not new_api_sets:
        logger.info("No new sets detected")
        return {"new_sets": 0, "elapsed": 0}

    logger.info(f"Found {len(new_api_sets)} new set(s) to onboard")

    # Pre-fetch PokeDATA.io sets for mapping
    async with httpx.AsyncClient(timeout=30) as client:
        pokedata_sets = await fetch_pokedata_sets(client)

    results = []
    for api_set in new_api_sets:
        result = await onboard_single_set(
            api_set, config, db, pokedata_sets, dry_run
        )
        results.append(result)
        await asyncio.sleep(1)  # Rate limit between sets

    elapsed = time.time() - start

    # Summary
    logger.info("--- Onboarding Summary ---")
    for r in results:
        status = []
        if r["seeded"]:
            status.append("seeded")
        if r["products"]:
            status.append(f"{r['products']} products")
        if r["value"]:
            status.append("value")
        if r["logo"]:
            status.append("logo")
        if r["top_card"]:
            status.append("top card")
        logger.info(f"  {r['name']}: {', '.join(status) or 'dry run'}")

    logger.info(f"Onboarded {len(results)} set(s) in {elapsed:.1f}s")

    return {
        "new_sets": len(results),
        "details": results,
        "elapsed": round(elapsed, 1),
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Detect and onboard new Pokemon TCG sets"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be onboarded without making changes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-check all sets (not just new ones)",
    )
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    await onboard_new_sets(config, db, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    asyncio.run(main())
