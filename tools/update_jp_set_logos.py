"""
Update Japanese set logo URLs from jp.pokellector.com.

Scrapes jp.pokellector.com/sets to discover logo URLs, then fuzzy-matches
against our JP sets in the database. Manual overrides handle name mismatches
between TCGPlayer names and Pokellector names.

Usage:
    python tools/update_jp_set_logos.py
    python tools/update_jp_set_logos.py --dry-run
"""

import asyncio
import re
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from bs4 import BeautifulSoup
from config import Config
from db import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

JP_POKELLECTOR_URL = "https://jp.pokellector.com/sets"

# Manual overrides: DB set name -> Pokellector set name
# For sets where TCGPlayer and Pokellector use different English translations
NAME_OVERRIDES = {
    # Mega era
    "M2a: High Class Pack: MEGA Dream ex": "MEGA Dream ex",
    # SV era
    "SV10: The Glory of Team Rocket": "Glory of Team Rocket",
    "SV9a: Heat Wave Arena": "Hot Air Arena",
    "SV8a: Terastal Fest ex": "Terastal Festival ex",
    "SV7: Stellar Miracle": "Stella Miracle",
    "SV6: Transformation Mask": "Mask of Change",
    "SV2a: Pokemon Card 151": "Pokemon 151",
    "SV1a: Triplet Beat": "Triplet Beat",  # Pokellector uses "Triple Beat"
    "M3: Nihil Zero": "Munikis Zero",
    # SWSH era
    "S7D: Skyscraping Perfection": "Towering Perfection",
    "S6K: Jet-Black Spirit": "Jet Black Spirit",
    "S5a: Peerless Fighters": "Matchless Fighter",
    "S4: Amazing Volt Tackle": "Electrifying Tackle",
    "S3a: Legendary Heartbeat": "Legendary Pulse",
    "S2a: Explosive Walker": "Explosive Flame Walker",
    "S8: Fusion Arts": "Fusion ARTS",
    "S8a: 25th Anniversary Collection": "25th Anniversary Collection",
    "s8a-P: Promo Card Pack 25th Anniversary Edition": "25th Anniversary Promo Pack",
    # SM era
    "SM12a: TAG TEAM GX: Tag All Stars": "Tag Team GX All Stars",
    "SM11: Miracle Twin": "Miracle Twins",
    "SM10b: Sky Legend": "Sky Legend",
    "SM8b: GX Ultra Shiny": "Ultra Shiny GX",
    "SM8: Super-Burst Impact": "Explosive Impact",
    "SM7: Sky-Splitting Charisma": "Charisma of the Cracked Sky",
    "SM4A: Ultradimensional Beasts": "The Transdimensional Beast",
    "SM4S: Awakened Heroes": "The Awoken Hero",
    "SM3+: Shining Legends": "Strengthening Expansion: Shining Legends",
    "SM3N: Darkness that Consumes Light": "Light-Consuming Darkness",
    "SM3H: To Have Seen the Battle Rainbow": "Seen the Rainbow Battle",
    "SM2+: Facing a New Trial": "Strengthening Expansion Pack: Beyond A New Challenge",
    "SM2L: Alolan Moonlight": "Alola Moonlight",
    "SM2K: Islands Await You": "Islands Awaiting You",
    "SM1+: Sun & Moon": "Sun & Moon Strengthening Expansion",
    "SM0: Pikachu's New Friends": "Pikachu & New Friends",
    "smP2: Great Detective Pikachu": "Detective Pikachu",
    # XY era
    "CP6: Expansion Pack 20th Anniversary": "20th Anniversary Collection",
    "XY5-Bg: Gaia Volcano": "Gaia Volcano",
    "XY5-Bt: Tidal Storm": "Tidal Storm",
    # Promos
    "S-P: Sword & Shield Promos": "Sword & Shield Promos",
    "SV-P Promotional Cards": "Scarlet & Violet Promos",
    "M-P Promotional Cards": "Mega Series Promos",
}


def strip_code_prefix(name: str) -> str:
    """Strip the code prefix from a JP set name.

    Examples:
        'SV10: The Glory of Team Rocket' -> 'The Glory of Team Rocket'
        'S6a: Eevee Heroes' -> 'Eevee Heroes'
        'SM9: Tag Bolt' -> 'Tag Bolt'
    """
    # Match patterns like 'SV10:', 'S6a:', 'SM9:', 'M2a:', 'm1S:', etc.
    match = re.match(r'^[A-Za-z0-9+\-]+:\s*', name)
    if match:
        return name[match.end():]
    return name


def normalize(name: str) -> str:
    """Normalize a set name for fuzzy matching."""
    return re.sub(r'[^a-z0-9]', '', name.lower())


async def scrape_pokellector_logos() -> dict[str, str]:
    """Scrape jp.pokellector.com/sets and return {set_name: logo_url}."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(JP_POKELLECTOR_URL, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    logos: dict[str, str] = {}

    # Each set is in an <a> with class "button" inside set listing divs
    # The logo is in an <img> tag, set name is in text
    for link in soup.select("a.button"):
        img = link.select_one("img")
        name_el = link.select_one(".name")
        if img and name_el:
            name = name_el.get_text(strip=True)
            src = img.get("src", "")
            if src and name:
                # Ensure full URL
                if not src.startswith("http"):
                    src = f"https://den-media.pokellector.com{src}"
                logos[name] = src

    # If parsing didn't work well, try alternative selectors
    if len(logos) < 10:
        log.warning(f"Only found {len(logos)} logos with primary selector, trying alternatives...")
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "/logos/" in src and "pokellector.com" in src:
                # Try to find the set name from nearby text
                parent = img.parent
                if parent:
                    name = parent.get_text(strip=True)
                    if name and len(name) < 100:
                        # Convert .symbol. to .logo. for full logo images
                        src = src.replace(".symbol.", ".logo.")
                        logos[name] = src

    log.info(f"Scraped {len(logos)} logos from jp.pokellector.com")
    return logos


async def main():
    dry_run = "--dry-run" in sys.argv
    config = Config()
    db = Database(config)

    # Step 1: Scrape Pokellector
    log.info("Scraping jp.pokellector.com/sets...")
    pokellector_logos = await scrape_pokellector_logos()

    if not pokellector_logos:
        log.error("Failed to scrape any logos from Pokellector. Aborting.")
        return

    # Build normalized lookup: normalized_name -> (original_name, url)
    normalized_lookup: dict[str, tuple[str, str]] = {}
    for name, url in pokellector_logos.items():
        normalized_lookup[normalize(name)] = (name, url)

    # Step 2: Get JP sets from DB
    resp = db.client.table("sets").select("id, name, image_url, language").eq(
        "language", "ja"
    ).execute()
    jp_sets = resp.data
    log.info(f"Found {len(jp_sets)} JP sets in database")

    updated = 0
    skipped = 0
    missing = 0

    for s in jp_sets:
        db_name = s["name"]

        # Check manual override first
        if db_name in NAME_OVERRIDES:
            override_name = NAME_OVERRIDES[db_name]
            norm_override = normalize(override_name)
            if norm_override in normalized_lookup:
                _, logo_url = normalized_lookup[norm_override]
            else:
                # Try direct match in pokellector_logos
                logo_url = pokellector_logos.get(override_name)
                if not logo_url:
                    log.warning(f"Override '{override_name}' not found on Pokellector for: {db_name}")
                    missing += 1
                    continue
        else:
            # Try stripping code prefix and matching
            stripped = strip_code_prefix(db_name)
            norm_stripped = normalize(stripped)

            if norm_stripped in normalized_lookup:
                _, logo_url = normalized_lookup[norm_stripped]
            else:
                # Try full name normalized
                norm_full = normalize(db_name)
                if norm_full in normalized_lookup:
                    _, logo_url = normalized_lookup[norm_full]
                else:
                    log.warning(f"No Pokellector match for: {db_name}")
                    missing += 1
                    continue

        # Skip if already has this URL
        if s.get("image_url") == logo_url:
            skipped += 1
            continue

        if dry_run:
            log.info(f"[DRY RUN] {db_name} -> {logo_url}")
            updated += 1
            continue

        db.client.table("sets").update({"image_url": logo_url}).eq("id", s["id"]).execute()
        log.info(f"Updated: {db_name}")
        updated += 1

    log.info(f"Done: {updated} updated, {skipped} already set, {missing} unmapped")
    if missing > 0:
        log.info("Unmapped sets are likely starter decks, promos, or special collections without logos")


if __name__ == "__main__":
    asyncio.run(main())
