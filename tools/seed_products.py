"""
Seed sealed products for each set from TCGPlayer into Supabase.

Uses TCGPlayer's search API to discover sealed products
for each set already in the database.

Usage:
    python tools/seed_products.py
    python tools/seed_products.py --language ja
    python tools/seed_products.py --set-id UUID
    python tools/seed_products.py --dry-run
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from config import Config
from db import Database
from models import Product

logger = logging.getLogger("seed_products")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TCGPLAYER_SEARCH_API = "https://mp-search-api.tcgplayer.com/v1/search/request"

# Map our product types to TCGPlayer's naming
PRODUCT_TYPE_MAP = {
    "Booster Box": "Booster Box",
    "Elite Trainer Box": "Elite Trainer Box",
    "Pokemon Center Elite Trainer Box": "Elite Trainer Box",  # Filtered by name containing "Pokemon Center"
    "Booster Pack": "Booster Pack",
    "Collection Box": "Collection Box",
    "Booster Bundle": "Booster Bundle",
    "Booster Bundle Case": "Booster Bundle",
}


async def search_tcgplayer_products(
    set_name: str, product_type: str | None, config: Config, language: str = "en"
) -> list[dict]:
    """Search TCGPlayer for sealed products matching the set and type."""
    product_line = "pokemon-japan" if language == "ja" else "pokemon"
    search_payload = {
        "algorithm": "sales_synonym_v2",
        "from": 0,
        "size": 50,
        "filters": {
            "term": {
                "productLineName": [product_line],
                "productTypeName": ["Sealed Products"],
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
        "sort": {},
    }

    products = []
    try:
        async with httpx.AsyncClient(timeout=config.httpx_timeout) as client:
            resp = await client.post(
                TCGPLAYER_SEARCH_API,
                params={"q": set_name, "isList": "false"},
                json=search_payload,
                headers={
                    "User-Agent": config.random_user_agent(),
                    "Content-Type": "application/json",
                },
            )

            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [{}])
                if results:
                    for result in results:
                        for item in result.get("results", []):
                            products.append(item)
            else:
                logger.warning(
                    f"TCGPlayer search returned {resp.status_code} for '{set_name}'"
                )
    except Exception as e:
        logger.error(f"TCGPlayer search failed for '{set_name}': {e}")

    return products


def classify_product_type(product_name: str) -> str:
    """Classify a product by name into our product type categories."""
    name_lower = product_name.lower()

    if "pokemon center" in name_lower and "elite trainer box" in name_lower:
        return "Pokemon Center Elite Trainer Box"
    if "elite trainer box" in name_lower or "etb" in name_lower:
        return "Elite Trainer Box"
    if "booster box" in name_lower:
        return "Booster Box"
    # Must check bundle case before standalone bundle
    if "booster bundle" in name_lower and "case" in name_lower:
        return "Booster Bundle Case"
    if "booster bundle" in name_lower:
        return "Booster Bundle"
    if "booster pack" in name_lower:
        return "Booster Pack"
    if "collection box" in name_lower or "collection" in name_lower:
        return "Collection Box"

    return "Other"


def tcgplayer_item_to_product(item: dict, set_id: str, language: str = "en") -> Product | None:
    """Convert a TCGPlayer search result item to a Product model."""
    name = item.get("productName", "")
    product_type = classify_product_type(name)

    tcgplayer_id_raw = item.get("productId")
    tcgplayer_id = int(tcgplayer_id_raw) if tcgplayer_id_raw is not None else None
    product_url_name = item.get("productUrlName", "")
    set_url_name = item.get("setUrlName", "")

    url = ""
    if tcgplayer_id and product_url_name:
        url = f"https://www.tcgplayer.com/product/{tcgplayer_id}/{product_url_name}"

    image_url = item.get("imageUrl", "")
    if image_url and not image_url.startswith("http"):
        image_url = f"https://tcgplayer-cdn.tcgplayer.com/product/{tcgplayer_id}_200w.jpg"

    return Product(
        set_id=set_id,
        name=name,
        product_type=product_type,
        tcgplayer_product_id=tcgplayer_id,
        tcgplayer_url=url,
        image_url=image_url,
        is_active=True,
        language=language,
    )


async def seed_products_for_set(
    set_data: dict, db: Database, config: Config, dry_run: bool = False,
    language: str = "en",
) -> dict:
    """Discover and seed products for a single set."""
    set_name = set_data["name"]
    set_id = set_data["id"]

    logger.info(f"Discovering products for: {set_name}")

    items = await search_tcgplayer_products(set_name, None, config, language=language)

    results = {"found": len(items), "seeded": 0, "skipped": 0, "failed": 0}

    for item in items:
        product = tcgplayer_item_to_product(item, set_id, language)
        if not product:
            results["skipped"] += 1
            continue

        # For English, skip "Other" types. For Japanese, keep them.
        if product.product_type == "Other" and language == "en":
            results["skipped"] += 1
            continue

        # Skip half booster boxes — not worth tracking
        if "half booster box" in product.name.lower():
            results["skipped"] += 1
            continue

        if dry_run:
            logger.info(
                f"  [DRY RUN] {product.product_type}: {product.name}"
            )
            results["seeded"] += 1
            continue

        try:
            db.upsert_product(product)
            results["seeded"] += 1
            logger.info(f"  Seeded: [{product.product_type}] {product.name}")
        except Exception as e:
            results["failed"] += 1
            logger.error(f"  Failed: {product.name}: {e}")

    return results


async def main():
    parser = argparse.ArgumentParser(description="Seed sealed products from TCGPlayer")
    parser.add_argument("--set-id", help="Seed products for a specific set ID")
    parser.add_argument("--dry-run", action="store_true", help="Print products without inserting")
    parser.add_argument("--language", default="en", choices=["en", "ja"], help="Language (en or ja)")
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    if args.set_id:
        set_data = db.get_set_by_id(args.set_id)
        if not set_data:
            logger.error(f"Set not found: {args.set_id}")
            return
        sets = [set_data]
    else:
        sets = db.get_sets(language=args.language)

    logger.info(f"Seeding products for {len(sets)} {args.language.upper()} sets...")

    all_results = {"total_found": 0, "total_seeded": 0, "total_skipped": 0, "total_failed": 0}

    for set_data in sets:
        results = await seed_products_for_set(
            set_data, db, config, args.dry_run, language=args.language
        )
        all_results["total_found"] += results["found"]
        all_results["total_seeded"] += results["seeded"]
        all_results["total_skipped"] += results["skipped"]
        all_results["total_failed"] += results["failed"]

        # Rate limit between sets
        await asyncio.sleep(config.random_delay())

    # Save results
    suffix = f"_{args.language}" if args.language != "en" else ""
    output_path = config.tmp_dir / f"seed_products{suffix}_results.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)

    logger.info(f"Done! {all_results['total_seeded']} products seeded across {len(sets)} sets")
    logger.info(f"Results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
