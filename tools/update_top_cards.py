"""
Find the most expensive card per set and store its pokemontcg.io image URL.

Uses PokeDATA.io to find the highest-priced card per set, then constructs
a pokemontcg.io high-res image URL from the set code + card number.
The URL is stored in sets.top_card_image_url for use as background art.

Usage:
    python tools/update_top_cards.py
    python tools/update_top_cards.py --set-name "Surging Sparks"
    python tools/update_top_cards.py --dry-run
    python tools/update_top_cards.py --force
    python tools/update_top_cards.py --rank 2 --set-name "Black Bolt"
"""

import argparse
import asyncio
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
from config import Config
from db import Database

# Reuse PokeDATA.io functions from scrape_set_values
from scrape_set_values import (
    fetch_pokedata_sets,
    build_set_mapping,
    fetch_set_cards,
    fetch_card_stats,
    PRICE_SOURCE,
    SKIP_SUBSETS,
)

logger = logging.getLogger("update_top_cards")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)

POKEMONTCG_IMAGE_BASE = "https://images.pokemontcg.io"

# pokemontcg.io set code overrides (our DB code → pokemontcg.io code)
# Some sets have different codes on pokemontcg.io
CODE_OVERRIDES: dict[str, str] = {
    "cel25c": "cel25",  # Classic Collection cards are under cel25
}

# pokemontcg.io uses the shiny vault sub-set code for SV-prefix cards
# Map: main set code → shiny vault code on pokemontcg.io
SHINY_VAULT_CODES: dict[str, str] = {
    "swsh45": "swsh45sv",  # Shining Fates → Shining Fates Shiny Vault
    "sm115": "sma",        # Hidden Fates → Hidden Fates Shiny Vault
}


def normalize_card_num(num: str) -> str:
    """Strip leading zeros from numeric card numbers for pokemontcg.io URLs."""
    # Pure numeric: strip leading zeros
    if num.isdigit():
        return str(int(num))
    # Alphanumeric like "SV49", "TG15" — keep as-is
    return num


def find_top_cards(
    cards: list[dict], stats: list[dict], count: int = 1
) -> list[tuple[str, str, float]]:
    """
    Find the top N most expensive non-reverse-holo cards.
    Skips cards with non-numeric numbers (SV, TG prefix) since those
    use different set codes on pokemontcg.io.
    Returns list of (card_name, card_number, price).
    """
    # Build price lookup: pokedata card_id → price
    price_by_card: dict[int, float] = {}
    for stat in stats:
        if stat.get("source") == PRICE_SOURCE and stat.get("avg") is not None:
            price_by_card[stat["card_id"]] = stat["avg"]

    # Collect all non-reverse cards with prices
    candidates: list[tuple[str, str, float]] = []
    seen_nums: set[str] = set()

    for c in cards:
        name = c.get("name", "")
        if "reverse" in name.lower():
            continue
        num = c.get("num", "")
        cid = c["id"]
        if not num or num in seen_nums:
            continue
        seen_nums.add(num)

        # Skip cards with letter prefixes (SV, TG, etc.) — these use
        # different set codes on pokemontcg.io and would 404
        if not num.isdigit():
            continue

        price = price_by_card.get(cid, 0)
        candidates.append((name, num, price))

    # Sort by price descending, return top N
    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates[:count]


async def main():
    parser = argparse.ArgumentParser(
        description="Find most expensive card per set and store image URL"
    )
    parser.add_argument("--set-name", help="Only process a specific set by name")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results without updating database",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process sets that already have a top card image",
    )
    parser.add_argument(
        "--rank",
        type=int,
        default=1,
        help="Use the Nth most expensive card (default: 1 = most expensive)",
    )
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    db_sets = db.get_sets()

    async with httpx.AsyncClient(timeout=30) as client:
        pokedata_sets = await fetch_pokedata_sets(client)

    logger.info("Found %d English sets on pokedata.io", len(pokedata_sets))

    mapping = build_set_mapping(db_sets, pokedata_sets)
    logger.info("Matched %d of %d DB sets", len(mapping), len(db_sets))

    # Filter
    if args.set_name:
        db_sets = [s for s in db_sets if s["name"] == args.set_name]
        if not db_sets:
            logger.error("Set '%s' not found in database", args.set_name)
            return

    # Skip sets that already have top card (unless --force)
    if not args.force and not args.set_name:
        before = len(db_sets)
        db_sets = [s for s in db_sets if not s.get("top_card_image_url")]
        skipped = before - len(db_sets)
        if skipped:
            logger.info(
                "Skipping %d sets that already have top card images (use --force)",
                skipped,
            )

    # Only sets we have a mapping + code for
    sets_to_process = [
        s
        for s in db_sets
        if s["id"] in mapping
        and s["name"] not in SKIP_SUBSETS
        and s.get("code")
    ]

    no_code = [
        s["name"]
        for s in db_sets
        if s["id"] in mapping and not s.get("code") and s["name"] not in SKIP_SUBSETS
    ]
    if no_code:
        logger.warning("Skipping %d sets without code: %s", len(no_code), ", ".join(no_code))

    logger.info("Processing %d sets...", len(sets_to_process))
    start = time.time()
    results = []

    async with httpx.AsyncClient(timeout=30) as client:
        for s in sets_to_process:
            pd_id = mapping[s["id"]]
            name = s["name"]
            code = s["code"]
            set_id = s["id"]

            cards = await fetch_set_cards(client, pd_id)
            if not cards:
                logger.warning("No cards for %s", name)
                await asyncio.sleep(0.3)
                continue

            card_ids = [c["id"] for c in cards]
            stats = await fetch_card_stats(client, card_ids)
            if not stats:
                logger.warning("No stats for %s", name)
                await asyncio.sleep(0.3)
                continue

            top_cards = find_top_cards(cards, stats, count=args.rank)
            if len(top_cards) < args.rank:
                logger.warning("Not enough cards for rank %d in %s", args.rank, name)
                await asyncio.sleep(0.3)
                continue

            card_name, card_num, card_price = top_cards[args.rank - 1]

            # Apply code override if needed
            img_code = CODE_OVERRIDES.get(code, code)
            # Strip leading zeros for pokemontcg.io URLs
            clean_num = normalize_card_num(card_num)
            image_url = f"{POKEMONTCG_IMAGE_BASE}/{img_code}/{clean_num}_hires.png"

            logger.info(
                "%-35s  #%-5s  $%8.2f  %s  →  %s",
                name,
                card_num,
                card_price,
                card_name,
                image_url,
            )

            if not args.dry_run:
                db.client.table("sets").update(
                    {"top_card_image_url": image_url}
                ).eq("id", set_id).execute()

            results.append(
                {"name": name, "card": card_name, "num": card_num, "price": card_price, "url": image_url}
            )

            await asyncio.sleep(0.3)

    elapsed = time.time() - start
    logger.info("--- Summary ---")
    logger.info("Sets processed: %d", len(results))
    logger.info("Elapsed: %.1fs", elapsed)
    if args.dry_run:
        logger.info("(Dry run - no database changes made)")


if __name__ == "__main__":
    asyncio.run(main())
