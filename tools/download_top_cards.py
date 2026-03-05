"""
Download high-res images of the most expensive cards from recent sets.

Uses PokeDATA.io to identify top cards by price and get image URLs from
their CDN (pokemoncardimages.pokedata.io). Falls back to TCGPlayer CDN
if PokeDATA.io image is unavailable.

Usage:
    python tools/download_top_cards.py
    python tools/download_top_cards.py --count 10 --sets 6
    python tools/download_top_cards.py --language en
    python tools/download_top_cards.py --set-name "Surging Sparks"
    python tools/download_top_cards.py --dry-run
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

from scrape_set_values import (
    fetch_pokedata_sets,
    build_set_mapping,
    fetch_set_cards,
    fetch_card_stats,
    PRICE_SOURCE,
    SKIP_SUBSETS,
)

logger = logging.getLogger("download_top_cards")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TCGPLAYER_CDN = "https://product-images.tcgplayer.com/fit-in/400x558"

# Characters not allowed in Windows file names
UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|]')


def sanitize_filename(name: str) -> str:
    """Remove filesystem-unsafe characters from a file name."""
    return UNSAFE_CHARS.sub("", name).strip()


def find_top_cards_all(
    cards: list[dict], stats: list[dict], count: int = 20
) -> list[dict]:
    """
    Find the top N most expensive non-reverse-holo cards.
    Includes ALL card number types (SV, TG prefix, numeric).
    Returns list of dicts with name, num, price, img_url, tcgplayer_id.
    """
    price_by_card: dict[int, float] = {}
    for stat in stats:
        if stat.get("source") == PRICE_SOURCE and stat.get("avg") is not None:
            price_by_card[stat["card_id"]] = stat["avg"]

    # Build card lookup by id
    card_by_id: dict[int, dict] = {c["id"]: c for c in cards}

    candidates: list[dict] = []
    seen_nums: set[str] = set()

    for c in cards:
        name = c.get("name", "")
        if "reverse" in name.lower():
            continue
        num = c.get("num", "")
        if not num or num in seen_nums:
            continue
        seen_nums.add(num)
        price = price_by_card.get(c["id"], 0)
        if price > 0:
            candidates.append({
                "name": name,
                "num": num,
                "price": price,
                "img_url": c.get("img_url", ""),
                "tcgplayer_id": c.get("tcgplayer_id", ""),
            })

    candidates.sort(key=lambda x: x["price"], reverse=True)
    return candidates[:count]


async def download_image(
    client: httpx.AsyncClient, url: str, dest: Path
) -> bool:
    """Download an image from URL to dest. Returns True on success."""
    try:
        resp = await client.get(url)
        if resp.status_code == 200 and len(resp.content) > 1000:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.content)
            return True
    except Exception as e:
        logger.debug(f"Download failed for {url}: {e}")
    return False


async def download_card_image(
    client: httpx.AsyncClient,
    card: dict,
    dest_dir: Path,
) -> bool:
    """Download card image using PokeDATA.io CDN, with TCGPlayer fallback."""
    card_name = card["name"]
    card_num = card["num"]
    img_url = card.get("img_url", "")
    tcgplayer_id = card.get("tcgplayer_id", "")

    safe_name = sanitize_filename(card_name)
    if not safe_name:
        safe_name = "card"

    # Determine extension from source URL
    ext = ".webp" if img_url.endswith(".webp") else ".png"

    # Include card number in filename (e.g., "Charizard ex 211.webp")
    dest = dest_dir / f"{safe_name} {card_num}{ext}"

    # Source 1: PokeDATA.io CDN (pokemoncardimages.pokedata.io)
    if img_url:
        if await download_image(client, img_url, dest):
            return True

    # Source 2: TCGPlayer CDN (if we have a tcgplayer_id)
    if tcgplayer_id:
        tcg_url = f"{TCGPLAYER_CDN}/{tcgplayer_id}.jpg"
        dest_jpg = dest_dir / f"{safe_name} {card_num}.jpg"
        if await download_image(client, tcg_url, dest_jpg):
            return True

    return False


async def process_set(
    client: httpx.AsyncClient,
    db_set: dict,
    pd_id: int,
    output_dir: Path,
    count: int,
    dry_run: bool,
) -> dict:
    """Process a single set: fetch cards, find top N, download images."""
    name = db_set["name"]
    language = db_set.get("language", "en")

    cards = await fetch_set_cards(client, pd_id)
    if not cards:
        logger.warning(f"No cards for {name}")
        return {"name": name, "downloaded": 0, "failed": 0, "skipped": True}

    card_ids = [c["id"] for c in cards]
    stats = await fetch_card_stats(client, card_ids)
    if not stats:
        logger.warning(f"No stats for {name}")
        return {"name": name, "downloaded": 0, "failed": 0, "skipped": True}

    top_cards = find_top_cards_all(cards, stats, count=count)
    if not top_cards:
        logger.warning(f"No priced cards for {name}")
        return {"name": name, "downloaded": 0, "failed": 0, "skipped": True}

    # Sanitize folder name (colons common in JP set names)
    folder_name = sanitize_filename(name)
    dest_dir = output_dir / folder_name

    downloaded = 0
    failed = 0
    failed_cards: list[str] = []

    for card in top_cards:
        if dry_run:
            logger.info(f"  #{card['num']:<6s} ${card['price']:>8.2f}  {card['name']}")
            downloaded += 1
            continue

        ok = await download_card_image(client, card, dest_dir)
        if ok:
            downloaded += 1
        else:
            failed += 1
            failed_cards.append(f"{card['name']} (#{card['num']})")

        await asyncio.sleep(0.2)

    tag = "[EN]" if language == "en" else "[JP]"
    if not dry_run:
        logger.info(f"{tag} {name}: {downloaded} downloaded, {failed} failed")
    else:
        logger.info(f"{tag} {name}: {downloaded} cards listed")

    if failed_cards:
        for fc in failed_cards:
            logger.warning(f"  FAILED: {fc}")

    return {
        "name": name,
        "language": language,
        "downloaded": downloaded,
        "failed": failed,
        "failed_cards": failed_cards,
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Download top card images from recent sets"
    )
    parser.add_argument(
        "--count", type=int, default=20,
        help="Number of top cards per set (default: 20)",
    )
    parser.add_argument(
        "--sets", type=int, default=12,
        help="Number of most recent sets per language (default: 12)",
    )
    parser.add_argument(
        "--language", choices=["en", "ja"],
        help="Only process one language (default: both)",
    )
    parser.add_argument(
        "--set-name", help="Only process a specific set by name",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List cards without downloading images",
    )
    args = parser.parse_args()

    config = Config()
    db = Database(config)
    output_dir = config.tmp_dir / "top_cards"

    languages = [args.language] if args.language else ["en", "ja"]

    total_downloaded = 0
    total_failed = 0
    all_results: list[dict] = []

    for lang in languages:
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing {'English' if lang == 'en' else 'Japanese'} sets")
        logger.info(f"{'='*50}")

        # Get sets from DB
        db_sets = db.get_sets(language=lang)

        # Filter out sub-sets and sets without release dates
        db_sets = [
            s for s in db_sets
            if s["name"] not in SKIP_SUBSETS and s.get("release_date")
        ]

        # Filter by name if specified
        if args.set_name:
            db_sets = [s for s in db_sets if s["name"] == args.set_name]
            if not db_sets:
                logger.error(f"Set '{args.set_name}' not found for language={lang}")
                continue
        else:
            # Take the most recent N sets
            db_sets = db_sets[: args.sets]

        logger.info(f"Selected {len(db_sets)} sets")

        # Map to PokeDATA.io
        async with httpx.AsyncClient(timeout=30) as client:
            pd_sets = await fetch_pokedata_sets(client, lang)

        mapping = build_set_mapping(db_sets, pd_sets)
        logger.info(f"Matched {len(mapping)} of {len(db_sets)} sets to PokeDATA.io")

        sets_to_process = [s for s in db_sets if s["id"] in mapping]

        async with httpx.AsyncClient(timeout=30) as client:
            for s in sets_to_process:
                pd_id = mapping[s["id"]]
                result = await process_set(
                    client, s, pd_id, output_dir, args.count, args.dry_run
                )
                all_results.append(result)
                total_downloaded += result.get("downloaded", 0)
                total_failed += result.get("failed", 0)
                await asyncio.sleep(1.5)

    # Summary
    en_count = sum(1 for r in all_results if r.get("language") == "en" and not r.get("skipped"))
    jp_count = sum(1 for r in all_results if r.get("language") == "ja" and not r.get("skipped"))

    logger.info(f"\n{'='*50}")
    logger.info("SUMMARY")
    logger.info(f"{'='*50}")
    logger.info(f"Sets processed: {en_count} EN, {jp_count} JP")
    logger.info(f"Cards {'listed' if args.dry_run else 'downloaded'}: {total_downloaded}")
    if total_failed:
        logger.info(f"Failed downloads: {total_failed}")
    if not args.dry_run:
        logger.info(f"Output directory: {output_dir}")
    if args.dry_run:
        logger.info("(Dry run - no images downloaded)")


if __name__ == "__main__":
    asyncio.run(main())
