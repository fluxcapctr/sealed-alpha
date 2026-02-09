"""
Seed Pokemon TCG sets into Supabase.

Uses the Pokemon TCG API (api.pokemontcg.io) for set metadata.
By default seeds from XY era (2014) onward, skipping promos and sub-sets.

Usage:
    python tools/seed_sets.py
    python tools/seed_sets.py --year-from 2014
    python tools/seed_sets.py --dry-run
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from config import Config
from db import Database
from models import PokemonSet

logger = logging.getLogger("seed_sets")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Pokemon TCG API endpoint
POKEMON_TCG_API = "https://api.pokemontcg.io/v2/sets"

# TCGPlayer search API for discovering group IDs
TCGPLAYER_SEARCH_API = "https://mp-search-api.tcgplayer.com/v1/search/request"


async def fetch_sets_from_pokemon_api(config: Config, max_retries: int = 3) -> list[dict]:
    """Fetch all Pokemon TCG sets from the free pokemontcg.io API."""
    all_sets = []
    page = 1
    page_size = 250

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                while True:
                    logger.info(f"Fetching sets page {page}...")
                    resp = await client.get(
                        POKEMON_TCG_API,
                        params={"page": page, "pageSize": page_size, "orderBy": "-releaseDate"},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    sets = data.get("data", [])
                    if not sets:
                        break

                    all_sets.extend(sets)
                    total = data.get("totalCount", 0)
                    if len(all_sets) >= total:
                        break
                    page += 1

            logger.info(f"Fetched {len(all_sets)} total sets from Pokemon TCG API")
            return all_sets
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPStatusError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Timeout (attempt {attempt + 1}/{max_retries}), retrying in 5s...")
                await asyncio.sleep(5)
                all_sets = []
                page = 1
            else:
                raise

    return all_sets


# Set codes to skip: promos, McDonalds, sub-sets (Trainer Galleries, Shiny Vaults)
SKIP_CODES = {
    # Black Star Promos
    "xyp", "smp", "swshp", "svp",
    # McDonald's collections
    "mcd14", "mcd15", "mcd16", "mcd17", "mcd18", "mcd19", "mcd21", "mcd22",
    # Sub-sets (cards already in parent set)
    "swsh12pt5gg", "swsh12tg", "swsh11tg", "swsh10tg", "swsh9tg",
    "swsh45sv", "cel25c", "sma",
    # Misc non-expansion
    "fut20",  # Pokémon Futsal Collection
    "sve",    # SV Energies
}


def filter_sets_by_year(sets: list[dict], min_year: int) -> list[dict]:
    """Filter sets to only include those released from min_year onward.
    Also skips promos, McDonalds, sub-sets, and pre-XY era sets."""
    filtered = []
    for s in sets:
        release = s.get("releaseDate", "")
        if not release or int(release[:4]) < min_year:
            continue

        code = s.get("id", "")

        # Skip explicitly excluded codes
        if code in SKIP_CODES:
            continue

        # Skip Black & White and older series by code prefix
        if code.startswith(("bw", "dpp", "pl", "hgss", "ex", "np", "base", "gym", "neo", "ecard")):
            continue

        filtered.append(s)
    return filtered


def normalize_date(date_str: str) -> str:
    """Normalize date string to ISO format (YYYY-MM-DD)."""
    return date_str.replace("/", "-")


def estimate_print_status(release_date_str: str) -> tuple[bool, bool]:
    """Estimate if a set is still in print and in rotation based on release date."""
    if not release_date_str:
        return True, True

    release = date.fromisoformat(normalize_date(release_date_str))
    today = date.today()
    age_days = (today - release).days

    # Sets typically in print for ~2 years
    in_print = age_days < 730

    # Sets rotate out of Standard roughly 2 years after release
    in_rotation = age_days < 730

    return in_print, in_rotation


async def discover_tcgplayer_group_id(set_name: str, config: Config) -> int | None:
    """Try to find the TCGPlayer group ID for a set by searching."""
    search_payload = {
        "algorithm": "sales_synonym_v2",
        "from": 0,
        "size": 5,
        "filters": {
            "term": {"productLineName": ["pokemon"], "productTypeName": ["Sealed Products"]},
            "range": {},
            "match": {},
        },
        "listingSearch": {"filters": {"term": {}, "range": {}, "exclude": {"channelExclusion": 0}}},
        "context": {"cart": {}, "shippingCountry": "US", "userProfile": {}},
        "settings": {"useFuzzySearch": True, "didYouMean": {}},
        "sort": {},
    }

    try:
        async with httpx.AsyncClient(timeout=config.httpx_timeout) as client:
            resp = await client.post(
                TCGPLAYER_SEARCH_API,
                params={"q": set_name, "isList": "false"},
                json=search_payload,
                headers={"User-Agent": config.random_user_agent()},
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [{}])
                if results:
                    aggregations = results[0].get("aggregations", {})
                    set_name_agg = aggregations.get("setName", [])
                    if set_name_agg:
                        # Return the first matching set's group info
                        # The actual group ID may need to be extracted differently
                        pass
    except Exception as e:
        logger.debug(f"Could not discover TCGPlayer group ID for {set_name}: {e}")

    return None


def api_set_to_model(api_set: dict) -> PokemonSet:
    """Convert a Pokemon TCG API set object to our PokemonSet model."""
    release_raw = api_set.get("releaseDate", "")
    release = normalize_date(release_raw) if release_raw else ""
    in_print, in_rotation = estimate_print_status(release)

    return PokemonSet(
        name=api_set.get("name", ""),
        code=api_set.get("id", ""),
        series=api_set.get("series", ""),
        release_date=release or None,
        set_url=f"https://www.tcgplayer.com/search/pokemon/{api_set.get('id', '')}",
        image_url=api_set.get("images", {}).get("logo", ""),
        is_in_print=in_print,
        is_in_rotation=in_rotation,
    )


async def main():
    parser = argparse.ArgumentParser(description="Seed Pokemon TCG sets")
    parser.add_argument("--year-from", type=int, default=None, help="Override minimum year")
    parser.add_argument("--dry-run", action="store_true", help="Print sets without inserting")
    args = parser.parse_args()

    config = Config()
    min_year = args.year_from or config.min_set_year

    # Step 1: Fetch sets from Pokemon TCG API
    logger.info(f"Fetching sets released from {min_year} onward...")
    all_sets = await fetch_sets_from_pokemon_api(config)
    filtered = filter_sets_by_year(all_sets, min_year)
    logger.info(f"Found {len(filtered)} sets from {min_year}+")

    if args.dry_run:
        for s in filtered:
            logger.info(f"  {s.get('releaseDate', '?')} | {s.get('name', '?')} ({s.get('id', '?')})")
        logger.info(f"Dry run: {len(filtered)} sets would be seeded")
        return

    # Step 2: Insert into Supabase
    db = Database(config)
    results = {"success": 0, "failed": 0}

    for api_set in filtered:
        try:
            model = api_set_to_model(api_set)
            db.upsert_set(model)
            results["success"] += 1
            logger.info(f"  Seeded: {model.name} ({model.code})")
        except Exception as e:
            results["failed"] += 1
            logger.error(f"  Failed: {api_set.get('name', '?')}: {e}")

    # Save results
    output = {
        "total_api_sets": len(all_sets),
        "filtered_sets": len(filtered),
        "min_year": min_year,
        **results,
    }
    output_path = config.tmp_dir / "seed_sets_results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Done! {results['success']} seeded, {results['failed']} failed")
    logger.info(f"Results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
