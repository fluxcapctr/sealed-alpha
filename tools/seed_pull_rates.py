"""
Seed pull rate data into Supabase from TCGPlayer article data.

Data sourced from "TCG in Figures" spreadsheets covering SV, SWSH, and SM eras.
Pull rates are hardcoded because the TSV formats are too inconsistent for
automated parsing (typos, varying "1 in X" vs "/X" formats, missing data).

Usage:
    python tools/seed_pull_rates.py
    python tools/seed_pull_rates.py --dry-run
    python tools/seed_pull_rates.py --era sv
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from db import Database

logger = logging.getLogger("seed_pull_rates")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Hardcoded pull rate data ──────────────────────────────────────────
# Format: { "DB Set Name": [ (rarity, packs_per_hit, cards_in_set_or_None), ... ] }

SV_PULL_RATES: dict[str, list[tuple[str, float, int | None]]] = {
    "Scarlet & Violet": [
        ("Double Rare", 7, None),
        ("Ultra Rare", 15, 20),
        ("Illustration Rare", 13, 24),
        ("Special Illustration Rare", 32, 10),
        ("Hyper Rare", 54, 6),
    ],
    "Paldea Evolved": [
        ("Double Rare", 7, None),
        ("Ultra Rare", 15, 26),
        ("Illustration Rare", 13, 36),
        ("Special Illustration Rare", 32, 15),
        ("Hyper Rare", 57, 9),
    ],
    "Obsidian Flames": [
        ("Double Rare", 7, None),
        ("Ultra Rare", 15, 12),
        ("Illustration Rare", 13, 12),
        ("Special Illustration Rare", 32, 6),
        ("Hyper Rare", 52, 3),
    ],
    "151": [
        ("Foil Energy", 4, None),
        ("Double Rare", 8, None),
        ("Ultra Rare", 16, 16),
        ("Illustration Rare", 12, 16),
        ("Special Illustration Rare", 32, 7),
        ("Hyper Rare", 51, 3),
    ],
    "Paradox Rift": [
        ("Double Rare", 6, None),
        ("Ultra Rare", 15, 28),
        ("Illustration Rare", 13, 33),
        ("Special Illustration Rare", 47, 15),
        ("Hyper Rare", 82, 7),
    ],
    "Paldean Fates": [
        ("Double Rare", 6, None),
        ("Ultra Rare", 15, 5),
        ("Shiny Rare", 4, 130),
        ("Shiny Ultra Rare", 13, None),
        ("Illustration Rare", 14, 3),
        ("Special Illustration Rare", 58, 8),
        ("Hyper Rare", 62, 7),
    ],
    "Temporal Forces": [
        ("Double Rare", 6, None),
        ("Ultra Rare", 15, 18),
        ("ACE SPEC Rare", 20, 6),
        ("Illustration Rare", 13, 23),
        ("Special Illustration Rare", 86, 10),
        ("Hyper Rare", 139, 6),
    ],
    "Twilight Masquerade": [
        ("Double Rare", 6, None),
        ("Ultra Rare", 15, 21),
        ("ACE SPEC Rare", 20, 6),
        ("Illustration Rare", 13, 21),
        ("Special Illustration Rare", 86, 11),
        ("Hyper Rare", 146, 6),
    ],
    "Shrouded Fable": [
        ("Ultra Rare", 15, 10),
        ("ACE SPEC Rare", 20, 3),
        ("Illustration Rare", 12, 15),
        ("Special Illustration Rare", 67, 5),
        ("Hyper Rare", 144, 5),
    ],
    "Stellar Crown": [
        ("Double Rare", 6, None),
        ("Ultra Rare", 15, 11),
        ("ACE SPEC Rare", 20, 3),
        ("Illustration Rare", 13, 13),
        ("Special Illustration Rare", 90, 6),
        ("Hyper Rare", 137, 3),
    ],
    "Surging Sparks": [
        ("Double Rare", 6, None),
        ("Ultra Rare", 15, 20),
        ("ACE SPEC Rare", 20, 8),
        ("Illustration Rare", 13, 23),
        ("Special Illustration Rare", 87, 11),
        ("Hyper Rare", 188, 6),
    ],
    "Prismatic Evolutions": [
        ("Poké Ball Foil", 3, 100),
        ("Double Rare", 6, None),
        ("Ultra Rare", 13, 12),
        ("ACE SPEC Rare", 21, 8),
        ("Master Ball Foil", 20, 100),
        ("Special Illustration Rare", 45, 32),
        ("Hyper Rare", 180, 5),
    ],
    "Journey Together": [
        ("Double Rare", 5, None),
        ("Ultra Rare", 15, 11),
        ("Illustration Rare", 12, 11),
        ("Special Illustration Rare", 86, 6),
        ("Hyper Rare", 137, 3),
    ],
    "Destined Rivals": [
        ("Double Rare", 5, None),
        ("Ultra Rare", 16, None),
        ("Illustration Rare", 12, None),
        ("Special Illustration Rare", 94, None),
        ("Hyper Rare", 149, None),
    ],
    "Mega Evolution": [
        ("Double Rare", 4.78, None),
        ("Ultra Rare", 12.15, None),
        ("Illustration Rare", 9.18, None),
        ("Special Illustration Rare", 101.01, None),
    ],
    "Black Bolt": [
        ("Poké Ball Foil", 3, None),
        ("Double Rare", 5, None),
        ("Ultra Rare", 17, None),
        ("Illustration Rare", 6, None),
        ("Master Ball Foil", 19, None),
        ("Special Illustration Rare", 80, None),
    ],
    "White Flare": [
        ("Poké Ball Foil", 3, None),
        ("Double Rare", 5, None),
        ("Ultra Rare", 17, None),
        ("Illustration Rare", 6, None),
        ("Master Ball Foil", 19, None),
        ("Special Illustration Rare", 80, None),
    ],
    "Phantasmal Flames": [
        ("Double Rare", 5, None),
        ("Ultra Rare", 12, None),
        ("Illustration Rare", 9, None),
        ("Special Illustration Rare", 80, None),
        ("Mega Hyper Rare", 1260, None),
    ],
    "Ascended Heroes": [
        ("Double Rare", 5, None),
        ("Ultra Rare", 21, None),
        ("Illustration Rare", 9, None),
        ("Special Illustration Rare", 70, None),
    ],
}

SWSH_PULL_RATES: dict[str, list[tuple[str, float, int | None]]] = {
    "Sword & Shield": [
        ("V", 7.04, 17),
        ("VMAX", 45.37, 4),
        ("Full Art Pokemon", 35.06, 12),
        ("Full Art Trainer", 112.88, 4),
        ("Rainbow Rare", 81.19, 8),
        ("Secret Rare (Gold)", 110.19, 6),
    ],
    "Rebel Clash": [
        ("V", 7.91, 16),
        ("VMAX", 29.42, 7),
        ("Full Art Pokemon", 32.96, 14),
        ("Full Art Trainer", 136.80, 4),
        ("Rainbow Rare", 66.73, 11),
        ("Secret Rare (Gold)", 105.23, 6),
    ],
    "Darkness Ablaze": [
        ("V", 7.95, 14),
        ("VMAX", 25.98, 7),
        ("Full Art Pokemon", 36.79, 9),
        ("Full Art Trainer", 88.42, 4),
        ("Rainbow Rare", 84.00, 7),
        ("Secret Rare (Gold)", 114.55, 5),
    ],
    "Champion's Path": [
        ("V", 6.36, 11),
        ("VMAX", 29.83, 3),
        ("Full Art Pokemon", 26.60, 4),
        ("Full Art Trainer", 61.38, 1),
        ("Rainbow Rare", 63.84, 5),
        ("Secret Rare (Gold)", 76.00, 2),
    ],
    "Vivid Voltage": [
        ("VMAX", 6, None),
        ("Ultra Rare", 20, None),
        ("Rainbow Rare", 12, None),
        ("Secret Rare (Gold)", 6, None),
    ],
    "Shining Fates": [
        ("V", 9.23, 8),
        ("VMAX", 18.38, 6),
        ("Full Art Pokemon", 199, 1),
        ("Full Art Trainer", 36.45, 8),
        ("Amazing Rare", 17.36, 3),
        ("Rainbow Rare", 84.12, 1),
        ("Secret Rare (Gold)", 109.35, 2),
        ("Shiny Rare", 4.40, 120),
        ("Shiny V/VMAX", 11.16, 16),
    ],
    "Battle Styles": [
        ("V", None, None),
        ("VMAX/VSTAR", None, 6),
        ("Full Art V", 48, None),
        ("Full Art Trainer", 94, None),
        ("Alt Art", 201, 4),
        ("Alt Art VMAX", 703, 2),
        ("Rainbow Rare", 108, 12),
        ("Secret Rare (Gold)", 117, 6),
    ],
    "Chilling Reign": [
        ("V", None, 15),
        ("VMAX/VSTAR", 24, 8),
        ("Full Art V", 49, 18),
        ("Full Art Trainer", 78, 13),
        ("Alt Art", 147, 10),
        ("Alt Art VMAX", 454, 3),
        ("Rainbow Rare", 122, 20),
        ("Secret Rare (Gold)", 100, 12),
    ],
    "Evolving Skies": [
        ("V", 9, 18),
        ("VMAX/VSTAR", 18, 15),
        ("Full Art V", 36, 27),
        ("Alt Art", 91, 11),
        ("Alt Art VMAX", 332, 6),
        ("Rainbow Rare", 118, 16),
        ("Secret Rare (Gold)", 109, 12),
    ],
    "Celebrations": [],  # Mini set — no standard pull rate data in TSV
    "Fusion Strike": [
        ("V", 8, 19),
        ("VMAX/VSTAR", 30, 8),
        ("Full Art V", 58, 13),
        ("Full Art Trainer", 64, 7),
        ("Alt Art", 180, 4),
        ("Alt Art VMAX", 332, 4),
        ("Rainbow Rare", 127, 11),
        ("Secret Rare (Gold)", 120, 5),
    ],
    "Brilliant Stars": [
        ("V", None, 20),
        ("VMAX/VSTAR", None, 7),
        ("Full Art V", None, 11),
        ("Full Art Trainer", 54, 6),
        ("Alt Art", None, 4),
        ("Trainer Gallery", 8, 30),
        ("Rainbow Rare", 51, 8),
        ("Secret Rare (Gold)", 92, 8),
    ],
    "Astral Radiance": [
        ("V", 8, 19),
        ("VMAX/VSTAR", 29, 9),
        ("Full Art V", 47, 15),
        ("Full Art Trainer", 93, 9),
        ("Alt Art", 135, 6),
        ("Trainer Gallery", 8, 30),
        ("Rainbow Rare", 78, 18),
        ("Secret Rare (Gold)", 130, 9),
    ],
    "Pokémon GO": [
        ("Rare Holo V", 8, 6),
        ("Rare Holo VSTAR", 24, 2),
        ("Rare Ultra", 36, 8),
        ("Rare Rainbow", 72, 7),
        ("Rare Secret", 300, 3),
        ("Radiant Rare", 11, 3),
    ],
    "Lost Origin": [
        ("V", 9, 12),
        ("VMAX/VSTAR", 23, 7),
        ("Full Art V", 51, 13),
        ("Full Art Trainer", 70, 8),
        ("Alt Art", 201, 4),
        ("Trainer Gallery", 8, 30),
        ("Radiant Rare", 20, 3),
        ("Rainbow Rare", 78, 15),
        ("Secret Rare (Gold)", 131, 6),
    ],
    "Silver Tempest": [
        ("V", 9, 15),
        ("VMAX/VSTAR", 27, 7),
        ("Full Art V", 48, 14),
        ("Full Art Trainer", 99, 8),
        ("Alt Art", 168, 4),
        ("Trainer Gallery", 8, 30),
        ("Radiant Rare", 22, 3),
        ("Rainbow Rare", 80, 14),
        ("Secret Rare (Gold)", 106, 6),
    ],
    "Crown Zenith": [
        ("V", 8, 17),
        ("VMAX/VSTAR", 19, 12),
        ("Full Art Trainer", 105, 5),
        ("Signature Trainer", 13, 4),
        ("Radiant Rare", 22, 3),
        ("Secret Rare (Gold)", 133, 1),
        ("Galarian Gallery", 3, 70),
    ],
}

XY_PULL_RATES: dict[str, list[tuple[str, float, int | None]]] = {
    "XY": [
        ("EX", 9, None),
        ("Full Art", 18, None),
        ("Secret Rare", 36, None),
    ],
    "Flashfire": [
        ("EX", 9, None),
        ("Full Art", 18, None),
        ("Secret Rare", 36, None),
        ("Full Art Trainer", 72, None),
    ],
    "Furious Fists": [
        ("EX", 9, None),
        ("Full Art", 18, None),
        ("Secret Rare", 36, None),
        ("Full Art Trainer", 72, None),
    ],
    "Phantom Forces": [
        ("EX", 9, None),
        ("Full Art", 18, None),
        ("Secret Rare", 36, None),
        ("Full Art Trainer", 72, None),
    ],
    "Primal Clash": [
        ("EX", 9, None),
        ("Full Art", 9, None),
        ("Secret Rare", 12, None),
        ("Full Art Trainer", 72, None),
    ],
    "Double Crisis": [
        ("EX", 5, None),
    ],
    "Roaring Skies": [
        ("EX", 9, None),
        ("Full Art", 9, None),
        ("Secret Rare", 12, None),
        ("Full Art Trainer", 72, None),
    ],
    "Ancient Origins": [
        ("EX", 9, None),
        ("Full Art", 9, None),
        ("Secret Rare", 12, None),
        ("Full Art Trainer", 72, None),
    ],
    "BREAKthrough": [
        ("EX", 9, None),
        ("Full Art", 9, None),
        ("Secret Rare", 12, None),
        ("Full Art Trainer", 72, None),
    ],
    "BREAKpoint": [
        ("EX", 8, None),
        ("Full Art", 9, None),
        ("Secret Rare", 12, None),
        ("Full Art Trainer", 72, None),
    ],
    "Generations": [
        ("EX", 8, None),
        ("Full Art", 9, None),
        ("Full Art Trainer", 12, None),
    ],
    "Fates Collide": [
        ("EX", 8, None),
    ],
    "Steam Siege": [
        ("EX", 8, None),
    ],
    "Evolutions": [
        ("EX", 7, None),
    ],
}

SM_PULL_RATES: dict[str, list[tuple[str, float, int | None]]] = {
    "Sun & Moon": [
        ("GX", 9, 11),
        ("Full Art Pokemon", 36, 8),
        ("Full Art Trainer", 72, 4),
        ("Rainbow Rare", 68, 8),
        ("Secret Rare (Gold)", 123, 6),
    ],
    "Guardians Rising": [
        ("GX", 9, 12),
        ("Full Art Pokemon", 34, 12),
        ("Full Art Trainer", 138, 3),
        ("Rainbow Rare", 77, 15),
        ("Secret Rare (Gold)", 122, 9),
    ],
    "Burning Shadows": [
        ("GX", 9.14, 12),
        ("Full Art Pokemon", 37.22, 13),
        ("Full Art Trainer", 80.40, 6),
        ("Rainbow Rare", 62.81, 13),
        ("Secret Rare (Gold)", 105.79, 9),
    ],
    "Shining Legends": [
        ("GX", 8.44, 4),
        ("Full Art Pokemon", 35.72, 2),
        ("Full Art Trainer", 85.33, 1),
        ("Rainbow Rare", 66.78, 4),
        ("Secret Rare (Gold)", 109.71, 1),
        ("Shiny Rare", 11.46, 6),
    ],
    "Crimson Invasion": [
        ("GX", 12.05, 8),
        ("Full Art Pokemon", 30.60, 8),
        ("Full Art Trainer", 85.00, 3),
        ("Rainbow Rare", 90.00, 8),
        ("Secret Rare (Gold)", 90.00, 5),
    ],
    "Ultra Prism": [
        ("GX", 12.49, 11),
        ("Full Art Pokemon", 42.92, 9),
        ("Full Art Trainer", 50.73, 9),
        ("Rainbow Rare", 66.96, 9),
        ("Secret Rare (Gold)", 128.77, 8),
        ("Prism Star", 11.47, 6),
    ],
    "Forbidden Light": [
        ("GX", 13.45, 12),
        ("Full Art Pokemon", 43.59, 9),
        ("Full Art Trainer", 79.00, 4),
        ("Rainbow Rare", 74.35, 9),
        ("Secret Rare (Gold)", 140.44, 6),
        ("Prism Star", 12.64, 4),
    ],
    "Celestial Storm": [
        ("GX", 9.67, 11),
        ("Full Art Pokemon", 47.74, 9),
        ("Full Art Trainer", 59.20, 8),
        ("Rainbow Rare", 82.22, 9),
        ("Secret Rare (Gold)", 113.85, 6),
        ("Prism Star", 18.27, 3),
    ],
    "Dragon Majesty": [
        ("GX", 6.48, 6),
        ("Full Art Pokemon", 32.42, 4),
        ("Full Art Trainer", 25.93, 2),
        ("Rainbow Rare", 43.22, 4),
        ("Secret Rare (Gold)", 129.67, 4),
        ("Prism Star", 9.26, 2),
    ],
    "Lost Thunder": [
        ("GX", 9.73, 20),
        ("Full Art Pokemon", 31.85, 13),
        ("Full Art Trainer", 79.63, 7),
        ("Rainbow Rare", 74.94, 13),
        ("Secret Rare (Gold)", 98.00, 9),
        ("Prism Star", 8.22, 7),
    ],
    "Team Up": [
        ("GX", 10.77, 15),
        ("Full Art Pokemon", 41.52, 13),
        ("Full Art Trainer", 41.52, 10),
        ("Rainbow Rare", 96.89, 10),
        ("Secret Rare (Gold)", 145.33, 5),
        ("Prism Star", 16.77, 4),
    ],
    "Detective Pikachu": [
        ("Rare Holo", 2.70, None),
    ],
    "Unbroken Bonds": [
        ("GX", 10.13, 14),
        ("Full Art Pokemon", 32.13, 18),
        ("Full Art Trainer", 99.69, 6),
        ("Rainbow Rare", 72.00, 14),
        ("Secret Rare (Gold)", 111.09, 6),
    ],
    "Unified Minds": [
        ("GX", 7.86, 17),
        ("Full Art Pokemon", 31.38, 17),
        ("Full Art Trainer", 85.40, 6),
        ("Rainbow Rare", 69.28, 13),
        ("Secret Rare (Gold)", 111.27, 9),
    ],
    "Hidden Fates": [
        ("GX", 6.64, 9),
        ("Full Art Pokemon", 68.70, 1),
        ("Full Art Trainer", 29.26, 8),
        ("Rainbow Rare", 58.52, 1),
        ("Secret Rare (Gold)", 56.43, 8),
        ("Shiny", 3.72, 94),
        ("Shiny GX", 8.81, 35),
    ],
    "Cosmic Eclipse": [
        ("GX", 8.39, 16),
        ("Full Art Pokemon", 37.33, 18),
        ("Full Art Trainer", 101.16, 9),
        ("Rainbow Rare", 66.72, 14),
        ("Secret Rare (Character)", 9.89, 12),
        ("Secret Rare (Gold)", 112.00, 9),
    ],
}


async def main():
    parser = argparse.ArgumentParser(description="Seed pull rate data")
    parser.add_argument("--dry-run", action="store_true", help="Print without inserting")
    parser.add_argument("--era", choices=["sv", "swsh", "sm", "xy"], help="Only seed one era")
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    # Build combined data dict based on era filter
    all_data: dict[str, list[tuple[str, float, int | None]]] = {}
    if not args.era or args.era == "sv":
        all_data.update(SV_PULL_RATES)
    if not args.era or args.era == "swsh":
        all_data.update(SWSH_PULL_RATES)
    if not args.era or args.era == "sm":
        all_data.update(SM_PULL_RATES)
    if not args.era or args.era == "xy":
        all_data.update(XY_PULL_RATES)

    # Fetch all sets from DB for name → id mapping
    sets = db.client.table("sets").select("id, name").execute().data
    name_to_id: dict[str, str] = {s["name"]: s["id"] for s in sets}

    total_inserted = 0
    total_skipped = 0
    total_no_match = 0

    for set_name, rates in all_data.items():
        set_id = name_to_id.get(set_name)
        if not set_id:
            logger.warning(f"No DB match for set: {set_name}")
            total_no_match += 1
            continue

        if not rates:
            logger.info(f"  {set_name}: no pull rate data, skipping")
            continue

        for rarity, packs_per_hit, cards_in_set in rates:
            if packs_per_hit is None:
                logger.info(f"  {set_name} / {rarity}: no rate data, skipping")
                total_skipped += 1
                continue

            row = {
                "set_id": set_id,
                "rarity": rarity,
                "packs_per_hit": float(packs_per_hit),
                "cards_in_set": cards_in_set,
                "source": "TCGPlayer",
            }

            if args.dry_run:
                logger.info(f"  [DRY] {set_name} | {rarity}: 1 in {packs_per_hit} ({cards_in_set or '?'} cards)")
                total_inserted += 1
                continue

            try:
                db.client.table("pull_rates").upsert(
                    row, on_conflict="set_id,rarity"
                ).execute()
                total_inserted += 1
            except Exception as e:
                logger.error(f"  Failed: {set_name} / {rarity}: {e}")

        logger.info(f"  {set_name}: {len([r for r in rates if r[1] is not None])} rarities")

    logger.info(f"Done! Inserted: {total_inserted}, Skipped: {total_skipped}, No match: {total_no_match}")


if __name__ == "__main__":
    asyncio.run(main())
