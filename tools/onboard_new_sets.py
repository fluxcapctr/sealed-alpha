"""
Detect and fully onboard new Pokemon TCG sets into the database.

Uses PokeDATA.io as the primary source for detecting new sets (pokemontcg.io
is unreliable/down). Then runs the full onboarding pipeline: seed set,
discover products, compute set value, fetch logo, and set top card art.

Usage:
    python tools/onboard_new_sets.py
    python tools/onboard_new_sets.py --dry-run
    python tools/onboard_new_sets.py --force
"""

import argparse
import asyncio
import logging
import re
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
from config import Config
from db import Database
from models import PokemonSet

# Reuse existing tool functions
from seed_sets import estimate_print_status, normalize_date
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

# PokeDATA.io series names that map to our eras
POKEDATA_SERIES_SKIP = {
    "Base", "Gym", "Neo", "e-Card", "EX", "Diamond & Pearl",
    "Platinum", "HeartGold SoulSilver", "Black & White",
}

# Subsets / promos / name variants to skip on PokeDATA.io
# Includes promos, McDonald's, Trick or Trade, and sets whose PokeDATA.io
# name differs from our DB name (e.g., "XY Base" vs "XY")
POKEDATA_NAME_SKIP = {
    # Promos
    "Scarlet & Violet Promos", "Mega Evolution Promos",
    "Sword & Shield Promos", "Sun & Moon Promos", "XY Promos",
    "Sword & Shield Promo", "Sun & Moon Black Star Promo",
    "Alternate Art Promos",
    # McDonald's / misc
    "Mcdonald's Dragon Discovery", "McDonald's Promos 2023",
    "McDonald's Promos 2024", "McDonald's Promos 2022",
    "McDonald's Promos 2019", "McDonald's Promos 2018",
    "McDonald's Promos 2017", "McDonald's Promos 2016",
    "McDonald's Promos 2015", "McDonald's Promos 2014",
    "Mcdonald's 25th Anniversary", "Mcdonald's Promos 2022",
    "Trick or Trade 2024", "Trick or Trade 2023", "Trick or Trade 2022",
    # Sub-collections
    "Generations Radiant Collection", "Trading Card Game Classic",
    # Name variants already in DB under different names
    "XY Base",             # DB: "XY"
    "Scarlet & Violet Base",  # DB: "Scarlet & Violet"
    "Pokemon Card 151",    # DB: "151"
    "Pokemon GO",          # DB: "Pokemon GO" (may already match — keep just in case)
}


def slugify_code(name: str) -> str:
    """Generate a URL-friendly code from a set name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def parse_pokedata_date(date_str: str) -> str:
    """Parse PokeDATA.io date format to ISO date string.
    Input: 'Fri, 30 Jan 2026 00:00:00 GMT'
    Output: '2026-01-30'
    """
    if not date_str:
        return ""
    try:
        from datetime import datetime
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def pokedata_set_to_model(pd_set: dict, code: str) -> PokemonSet:
    """Convert a PokeDATA.io set object to our PokemonSet model."""
    release_raw = parse_pokedata_date(pd_set.get("release_date", ""))
    in_print, in_rotation = estimate_print_status(release_raw) if release_raw else (True, True)

    return PokemonSet(
        name=pd_set.get("name", ""),
        code=code,
        series=pd_set.get("series", ""),
        release_date=release_raw or None,
        set_url=f"https://www.tcgplayer.com/search/pokemon/{code}",
        image_url=pd_set.get("img_url", ""),
        is_in_print=in_print,
        is_in_rotation=in_rotation,
    )


async def detect_new_sets_pokedata(config: Config, db: Database) -> list[dict]:
    """Detect new sets using PokeDATA.io (primary, fast and reliable)."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get("https://pokedata.io/api/sets")
        if r.status_code != 200:
            logger.error(f"PokeDATA.io API returned {r.status_code}")
            return []
        all_sets = r.json()

    # Filter to English, modern eras only
    candidates = []
    for s in all_sets:
        if s.get("language") != "ENGLISH":
            continue
        series = s.get("series", "")
        if series in POKEDATA_SERIES_SKIP:
            continue
        name = s.get("name", "")
        if name in POKEDATA_NAME_SKIP:
            continue

        # Filter by release year
        release_str = parse_pokedata_date(s.get("release_date", ""))
        if release_str:
            try:
                year = int(release_str[:4])
                if year < config.min_set_year:
                    continue
            except ValueError:
                continue
        else:
            continue

        candidates.append(s)

    # Compare against DB by name (more reliable than code matching)
    db_sets = db.get_sets()
    existing_names = {s["name"].lower() for s in db_sets if s.get("name")}

    new_sets = [s for s in candidates if s.get("name", "").lower() not in existing_names]
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

    price_by_card: dict[int, float] = {}
    for stat in stats:
        if stat.get("source") == PRICE_SOURCE and stat.get("avg") is not None:
            price_by_card[stat["card_id"]] = stat["avg"]

    for c in cards:
        num = c.get("num", "")
        if not num or num in seen:
            continue
        name = c.get("name", "")
        if "reverse" in name.lower():
            continue
        seen.add(num)
        total_cards += 1
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
    pd_set: dict,
    config: Config,
    db: Database,
    pokedata_sets: list[dict],
    dry_run: bool = False,
) -> dict:
    """Run the full onboarding pipeline for a single new set."""
    name = pd_set.get("name", "?")
    # Use PokeDATA.io code if available, otherwise generate a slug
    code = pd_set.get("code") or slugify_code(name)
    pd_id = pd_set.get("id")

    result = {
        "name": name,
        "code": code,
        "seeded": False,
        "products": 0,
        "value": False,
        "logo": False,
        "top_card": False,
    }

    logger.info(f"Onboarding: {name} (code={code}, pokedata_id={pd_id})")

    if dry_run:
        logger.info(f"  [DRY RUN] Would onboard {name}")
        return result

    # Step 1: Seed the set
    try:
        model = pokedata_set_to_model(pd_set, code)
        db.upsert_set(model)
        result["seeded"] = True
        logger.info(f"  Seeded set: {name}")
    except Exception as e:
        logger.error(f"  Failed to seed set: {e}")
        return result

    # Get the newly-created set from DB
    db_sets = db.get_sets()
    set_data = next((s for s in db_sets if s["name"] == name), None)
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
    if pd_id and name not in SKIP_SUBSETS:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
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
            logger.warning(f"  No PokeDATA.io ID — skipping value + top card")
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

    # Detect new sets via PokeDATA.io
    if force:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get("https://pokedata.io/api/sets")
            all_pd_sets = r.json()
        new_sets = [
            s for s in all_pd_sets
            if s.get("language") == "ENGLISH"
            and s.get("series", "") not in POKEDATA_SERIES_SKIP
            and s.get("name", "") not in POKEDATA_NAME_SKIP
        ]
        logger.info(f"Force mode: re-checking all {len(new_sets)} sets")
    else:
        new_sets = await detect_new_sets_pokedata(config, db)

    if not new_sets:
        logger.info("No new sets detected")
        return {"new_sets": 0, "elapsed": 0}

    logger.info(f"Found {len(new_sets)} new set(s) to onboard")

    # PokeDATA.io sets are already fetched — pass them for mapping
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        pokedata_sets = await fetch_pokedata_sets(client)

    results = []
    for pd_set in new_sets:
        result = await onboard_single_set(
            pd_set, config, db, pokedata_sets, dry_run
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
