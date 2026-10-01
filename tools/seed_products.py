"""
Seed sealed products for each set from TCGPlayer into Supabase.

Uses TCGPlayer's search API to discover sealed products
for each set already in the database.

Usage:
    python tools/seed_products.py
    python tools/seed_products.py --language ja
    python tools/seed_products.py --set-id UUID
    python tools/seed_products.py --dry-run
    python tools/seed_products.py --update-existing   # refresh fields of known products
    python tools/seed_products.py --no-set-check      # accept results from any TCGPlayer set
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from config import Config
from db import Database
from models import Product
from tools.tcgplayer import TcgPlayerError, clean_count, product_line_for, search_sealed

logger = logging.getLogger("seed_products")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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
    """Search TCGPlayer for sealed products matching the set name (all result pages)."""
    try:
        async with httpx.AsyncClient(timeout=config.httpx_timeout) as client:
            found = await search_sealed(client, set_name, product_line_for(language), config)
    except TcgPlayerError as e:
        logger.error(f"TCGPlayer search failed for '{set_name}': {e}")
        return []
    if found.truncated:
        logger.warning(
            f"'{set_name}': fetched {len(found.items)} of {found.total} search results; some products may be missing"
        )
    return found.items


def _normalize_name(name: str) -> str:
    """Lowercase, strip accents and punctuation: 'SWSH10.5: Pokémon GO' -> 'swsh10 5 pokemon go'."""
    folded = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", folded.lower()).strip()


def item_belongs_to_set(item: dict, set_name: str) -> bool:
    """
    Is this search result in the set we searched for?

    The search is fuzzy: `q=Paldea Evolved` returned 23 products from other sets
    among its first 50. Our set names come from pokemontcg.io ("151") and TCGPlayer's
    are longer ("SV: Scarlet & Violet 151"), so require our name to appear, as whole
    words, in the result's TCGPlayer set name.
    """
    wanted = _normalize_name(set_name)
    if not wanted:
        return False
    return f" {wanted} " in f" {_normalize_name(item.get('setName', ''))} "


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


def tcgplayer_item_to_product(
    item: dict, set_id: str, language: str = "en", release_date: str | None = None
) -> Product | None:
    """Convert a TCGPlayer search result item to a Product model."""
    name = item.get("productName", "")
    product_type = classify_product_type(name)

    tcgplayer_id_raw = item.get("productId")
    tcgplayer_id = int(tcgplayer_id_raw) if tcgplayer_id_raw is not None else None
    product_url_name = item.get("productUrlName", "")

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
        release_date=release_date,
        language=language,
    )


async def seed_products_for_set(
    set_data: dict, db: Database, config: Config, dry_run: bool = False,
    language: str = "en", check_set: bool = True, update_existing: bool = False,
) -> dict:
    """
    Discover and seed products for a single set.

    - Results from other TCGPlayer sets are ignored (`check_set`), so a fuzzy match
      can't attach another set's products to this one.
    - Products already in the database are never moved to a different set. They are
      skipped unless `update_existing` is set, which refreshes their other fields.
    """
    set_name = set_data["name"]
    set_id = set_data["id"]

    logger.info(f"Discovering products for: {set_name}")

    items = await search_tcgplayer_products(set_name, None, config, language=language)

    results = {"found": len(items), "seeded": 0, "skipped": 0, "failed": 0, "other_set": 0, "existing": 0}

    candidates: list[dict] = []
    other_groups: dict[str, int] = {}
    for item in items:
        if check_set and not item_belongs_to_set(item, set_name):
            results["other_set"] += 1
            group = item.get("setName", "?")
            other_groups[group] = other_groups.get(group, 0) + 1
            continue
        candidates.append(item)

    if other_groups:
        top = sorted(other_groups.items(), key=lambda kv: -kv[1])[:5]
        logger.info(f"  Ignored {results['other_set']} results from other sets: {dict(top)}")
    if items and not candidates:
        logger.warning(
            f"  None of the {len(items)} results for '{set_name}' are in a TCGPlayer set with that name. "
            "If the TCGPlayer name differs, review the groups above and rerun with --no-set-check."
        )

    products: list[Product] = []
    for item in candidates:
        product = tcgplayer_item_to_product(item, set_id, language, set_data.get("release_date"))
        if not product or product.tcgplayer_product_id is None:
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

        products.append(product)

    existing = db.get_existing_products_by_tcgplayer_ids(
        [p.tcgplayer_product_id for p in products]
    )

    for product in products:
        row = existing.get(product.tcgplayer_product_id)
        if row:
            results["existing"] += 1
            if row.get("set_id") is not None:
                if not update_existing:
                    continue
                product.set_id = None  # refresh other fields, but never move it to another set

        if dry_run:
            logger.info(f"  [DRY RUN] {product.product_type}: {product.name}")
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
    parser.add_argument(
        "--no-set-check", action="store_true",
        help="Accept search results from any TCGPlayer set (use only after reviewing what would be added)",
    )
    parser.add_argument(
        "--update-existing", action="store_true",
        help="Also refresh name/url/image of products already in the database (never moves them between sets)",
    )
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

    all_results = {
        "total_found": 0, "total_seeded": 0, "total_skipped": 0, "total_failed": 0,
        "total_other_set": 0, "total_existing": 0,
    }

    for set_data in sets:
        results = await seed_products_for_set(
            set_data, db, config, args.dry_run, language=args.language,
            check_set=not args.no_set_check, update_existing=args.update_existing,
        )
        all_results["total_found"] += results["found"]
        all_results["total_seeded"] += results["seeded"]
        all_results["total_skipped"] += results["skipped"]
        all_results["total_failed"] += results["failed"]
        all_results["total_other_set"] += results["other_set"]
        all_results["total_existing"] += results["existing"]

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
