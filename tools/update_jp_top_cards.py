"""
Find the most expensive card per Japanese set from TCGPlayer and store its image URL.

Searches TCGPlayer for individual cards (not sealed products) in each JP set,
finds the most expensive card by market price, and stores the TCGPlayer CDN
image URL in sets.top_card_image_url for use as background art.

Usage:
    python tools/update_jp_top_cards.py
    python tools/update_jp_top_cards.py --set-name "S6a: Eevee Heroes"
    python tools/update_jp_top_cards.py --dry-run
    python tools/update_jp_top_cards.py --force
    python tools/update_jp_top_cards.py --rank 2
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from config import Config
from db import Database

logger = logging.getLogger("update_jp_top_cards")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TCGPLAYER_SEARCH_API = "https://mp-search-api.tcgplayer.com/v1/search/request"
TCGPLAYER_CDN = "https://product-images.tcgplayer.com/fit-in/400x558"


async def search_top_card(
    client: httpx.AsyncClient, set_name: str, config: Config, rank: int = 1
) -> dict | None:
    """Search TCGPlayer for the most expensive individual card in a JP set."""
    payload = {
        "algorithm": "sales_synonym_v2",
        "from": 0,
        "size": rank + 5,  # Fetch a few extra in case some lack data
        "filters": {
            "term": {
                "productLineName": ["pokemon-japan"],
                "productTypeName": ["Cards"],
            },
            "range": {},
            "match": {},
        },
        "listingSearch": {
            "filters": {
                "term": {},
                "range": {},
                "exclude": {"channelExclusion": 0},
            }
        },
        "context": {"cart": {}, "shippingCountry": "US", "userProfile": {}},
        "settings": {"useFuzzySearch": True, "didYouMean": {}},
        "sort": {"field": "market-price", "order": "desc"},
    }

    try:
        resp = await client.post(
            TCGPLAYER_SEARCH_API,
            params={"q": set_name, "isList": "false"},
            json=payload,
            headers={
                "User-Agent": config.random_user_agent(),
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            logger.warning(f"TCGPlayer returned {resp.status_code} for '{set_name}'")
            return None

        data = resp.json()
        results_list = data.get("results", [])
        if not results_list:
            return None

        items = results_list[0].get("results", [])

        # Filter to items that match the set name exactly
        matching = [
            item for item in items
            if item.get("setName", "").lower() == set_name.lower()
            and item.get("marketPrice") is not None
            and item.get("marketPrice") > 0
        ]

        if len(matching) < rank:
            return None

        # Sort by market price descending (should already be sorted, but be safe)
        matching.sort(key=lambda x: x.get("marketPrice", 0), reverse=True)
        winner = matching[rank - 1]

        product_id = int(winner.get("productId", 0))
        if not product_id:
            return None

        return {
            "name": winner.get("productName", ""),
            "price": winner.get("marketPrice", 0),
            "product_id": product_id,
            "image_url": f"{TCGPLAYER_CDN}/{product_id}.jpg",
        }

    except Exception as e:
        logger.error(f"Search failed for '{set_name}': {e}")
        return None


async def main():
    parser = argparse.ArgumentParser(
        description="Find most expensive JP card per set and store image URL"
    )
    parser.add_argument("--set-name", help="Only process a specific set by name")
    parser.add_argument("--dry-run", action="store_true", help="Print without updating")
    parser.add_argument("--force", action="store_true", help="Re-process sets with existing images")
    parser.add_argument("--rank", type=int, default=1, help="Use Nth most expensive card")
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    # Get JP sets
    resp = db.client.table("sets").select("id, name, code, top_card_image_url, language").eq(
        "language", "ja"
    ).execute()
    jp_sets = resp.data

    if args.set_name:
        jp_sets = [s for s in jp_sets if s["name"] == args.set_name]
        if not jp_sets:
            logger.error(f"Set '{args.set_name}' not found")
            return

    # Skip sets already processed unless --force
    if not args.force and not args.set_name:
        before = len(jp_sets)
        jp_sets = [s for s in jp_sets if not s.get("top_card_image_url")]
        skipped = before - len(jp_sets)
        if skipped:
            logger.info(f"Skipping {skipped} sets already with top card (use --force)")

    logger.info(f"Processing {len(jp_sets)} JP sets...")
    start = time.time()
    updated = 0
    failed = 0

    async with httpx.AsyncClient(timeout=config.httpx_timeout) as client:
        for s in jp_sets:
            set_name = s["name"]
            set_id = s["id"]

            top = await search_top_card(client, set_name, config, rank=args.rank)

            if not top:
                logger.warning(f"No top card found for: {set_name}")
                failed += 1
                await asyncio.sleep(0.3)
                continue

            image_url = top["image_url"]
            logger.info(
                f"{'[DRY] ' if args.dry_run else ''}"
                f"{set_name:40s}  ${top['price']:>8.2f}  {top['name']:30s}  {image_url}"
            )

            if not args.dry_run:
                db.client.table("sets").update(
                    {"top_card_image_url": image_url}
                ).eq("id", set_id).execute()

            updated += 1
            await asyncio.sleep(0.3)

    elapsed = time.time() - start
    logger.info(f"--- Summary ---")
    logger.info(f"Updated: {updated}, Failed: {failed}, Elapsed: {elapsed:.1f}s")
    if args.dry_run:
        logger.info("(Dry run - no database changes made)")


if __name__ == "__main__":
    asyncio.run(main())
