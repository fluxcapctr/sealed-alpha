"""
Consolidate miscellaneous Japanese sets into a single 'Japan Special Products' set.

Merges starter decks, start decks, promo sets, world championship decks,
special box collections, build boxes, trainer boxes, and master battle sets
into one umbrella set. Products are reassigned; old sets are deleted.

Usage:
    python tools/consolidate_jp_misc_sets.py --dry-run
    python tools/consolidate_jp_misc_sets.py
"""

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from db import Database

logger = logging.getLogger("consolidate_jp_misc")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Patterns that identify miscellaneous JP sets (case-insensitive)
MERGE_PATTERNS = [
    r"starter",
    r"start deck",
    r"world champion",
    r"special box",
    r"build box",
    r"trainer box",
    r"master battle",
    r"promotional",
    r"promo",
    r"pokemon.e starter",
]

TARGET_SET_NAME = "Japan Special Products"
TARGET_SET_CODE = "jp-special-products"


def should_merge(set_name: str) -> bool:
    """Check if a set name matches any of the merge patterns."""
    name_lower = set_name.lower()
    for pattern in MERGE_PATTERNS:
        if re.search(pattern, name_lower):
            return True
    return False


async def main():
    parser = argparse.ArgumentParser(description="Consolidate misc JP sets")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    # Get all JP sets
    resp = db.client.table("sets").select("id, name, code, language").eq(
        "language", "ja"
    ).execute()
    jp_sets = resp.data
    logger.info(f"Found {len(jp_sets)} total JP sets")

    # Identify sets to merge
    sets_to_merge = [s for s in jp_sets if should_merge(s["name"])]
    logger.info(f"Found {len(sets_to_merge)} sets to merge:")
    for s in sets_to_merge:
        logger.info(f"  - {s['name']}")

    if not sets_to_merge:
        logger.info("Nothing to merge.")
        return

    # Check if target set already exists
    existing = db.client.table("sets").select("id").eq(
        "code", TARGET_SET_CODE
    ).eq("language", "ja").execute()

    if existing.data:
        target_set_id = existing.data[0]["id"]
        logger.info(f"Target set '{TARGET_SET_NAME}' already exists: {target_set_id}")
    else:
        if args.dry_run:
            target_set_id = "DRY-RUN-ID"
            logger.info(f"[DRY RUN] Would create set: {TARGET_SET_NAME}")
        else:
            result = db.client.table("sets").insert({
                "name": TARGET_SET_NAME,
                "code": TARGET_SET_CODE,
                "language": "ja",
                "series": "",
                "is_in_print": True,
                "is_in_rotation": True,
                "set_url": "https://www.tcgplayer.com/search/pokemon-japan",
            }).execute()
            target_set_id = result.data[0]["id"]
            logger.info(f"Created target set: {TARGET_SET_NAME} ({target_set_id})")

    merge_set_ids = [s["id"] for s in sets_to_merge]

    # Count products that will be reassigned
    products_resp = db.client.table("products").select("id, name, set_id").in_(
        "set_id", merge_set_ids
    ).execute()
    products = products_resp.data
    logger.info(f"Found {len(products)} products to reassign")

    if args.dry_run:
        for p in products:
            source_name = next(
                (s["name"] for s in sets_to_merge if s["id"] == p["set_id"]), "?"
            )
            logger.info(f"  [DRY RUN] {p['name']} ({source_name} -> {TARGET_SET_NAME})")
        logger.info(f"[DRY RUN] Would delete {len(sets_to_merge)} old sets")
        return

    # Reassign products to target set
    if products:
        db.client.table("products").update(
            {"set_id": target_set_id}
        ).in_("set_id", merge_set_ids).execute()
        logger.info(f"Reassigned {len(products)} products to '{TARGET_SET_NAME}'")

    # Delete old sets (products have been moved, so FK won't block)
    for s in sets_to_merge:
        db.client.table("sets").delete().eq("id", s["id"]).execute()
        logger.info(f"Deleted set: {s['name']}")

    logger.info(f"Done! Merged {len(sets_to_merge)} sets into '{TARGET_SET_NAME}'")
    logger.info(f"Remaining JP sets: {len(jp_sets) - len(sets_to_merge) + 1}")


if __name__ == "__main__":
    asyncio.run(main())
