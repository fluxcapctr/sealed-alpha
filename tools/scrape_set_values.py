"""
Scrape total set values (complete master set) from PokeDATA.io API,
with optional per-rarity value breakdowns via pokemontcg.io.

For each set, fetches all cards and their market prices to compute
the total value of a complete master set. With --rarity flag, also
fetches rarity metadata from pokemontcg.io to compute per-rarity
value breakdowns (used for Box EV / Rip Score calculations).

Usage:
    python tools/scrape_set_values.py
    python tools/scrape_set_values.py --set-name "Evolving Skies"
    python tools/scrape_set_values.py --dry-run
    python tools/scrape_set_values.py --force
    python tools/scrape_set_values.py --rarity --force
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

logger = logging.getLogger("scrape_set_values")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)

POKEDATA_BASE = "https://www.pokedata.io/api"
POKEMON_TCG_API = "https://api.pokemontcg.io/v2"
PRICE_SOURCE = 0.0  # TCGPlayer market price source

# Manual overrides for set name mapping (our DB name → pokedata name)
NAME_OVERRIDES: dict[str, str] = {
    # English overrides
    "151": "Pokemon Card 151",
    "Scarlet & Violet": "Scarlet & Violet Base",
    "Scarlet & Violet Black Star Promos": "Scarlet & Violet Promos",
    "SWSH Black Star Promos": "Sword & Shield Promo",
    "McDonald's Collection 2022": "Mcdonald's Promos 2022",
    "McDonald's Collection 2021": "Mcdonald's 25th Anniversary",
    "McDonald's Collection 2019": "McDonald's Promos 2019",
    "McDonald's Collection 2018": "Mcdonald's Promos 2018",
    "Pokémon GO": "Pokemon GO",
    "Pokémon Futsal Collection": "Pokemon Futsal Collection",
    # Japanese overrides (TCGPlayer name → PokeDATA name)
    "SV2a: Pokemon Card 151": "Pokemon Card 151 Japanese",
    "SV8a: Terastal Fest ex": "Terastal Festival ex",
    "SV11W: White Flare": "White Flare Japanese",
    "SV11B: Black Bolt": "Black Bolt Japanese",
    "S4a: Shiny Star V": "Shiny Star V s4A",
    "SM12a: TAG TEAM GX: Tag All Stars": "Tag Team GX All Stars",
    "S4: Amazing Volt Tackle": "Astonishing Volt Tackle",
    "SV6: Transformation Mask": "Mask of Change",
    "SM6: Forbidden Light": "Forbidden Light Japanese",
    "SM8: Super-Burst Impact": "Explosive Impact",
    "SM7: Sky-Splitting Charisma": "Charisma of the Cracked Sky",
    "S7D: Skyscraping Perfection": "Towering Perfection",
    "SM3+: Shining Legends": "Shining Legends Japanese",
    "SM3H: To Have Seen the Battle Rainbow": "Seen the Rainbow Battle",
    "SM3N: Darkness that Consumes Light": "Light Consuming Darkness",
    "SM4A: Ultradimensional Beasts": "Transdimensional Beast",
    "SM1+: Sun & Moon": "Strength Expansion Pack Sun & Moon",
    "S5a: Peerless Fighters": "Matchless Fighter",
    "S10b: Pokemon GO": "Pokemon GO Japanese",
    "SV9a: Heat Wave Arena": "Hot Air Arena",
    "S6K: Jet-Black Spirit": "Jet Black Spirit",
    "SV10: The Glory of Team Rocket": "Glory of Team Rocket",
    "M2: Inferno X": "Inferno X",
    "M2a: High Class Pack: MEGA Dream ex": "Mega Dream",
    "m1L: Mega Brave": "Mega Brave",
    "m1S: Mega Symphonia": "Mega Symphonia",
    "S12: Paradigm Trigger": "Paradigm Trigger",
    "S11: Lost Abyss": "Lost Abyss",
    "S12a: VSTAR Universe": "VSTAR Universe",
    "Pokemon TCG Classic: Charizard": "Trading Card Game Classic Japanese Charizard",
}

# Sets in our DB that are sub-sets (trainer galleries, shiny vaults)
# whose cards are included in the parent set on pokedata.io.
# We skip these to avoid double-counting.
SKIP_SUBSETS = {
    "Silver Tempest Trainer Gallery",
    "Lost Origin Trainer Gallery",
    "Astral Radiance Trainer Gallery",
    "Brilliant Stars Trainer Gallery",
    "Hidden Fates Shiny Vault",
    "Shining Fates Shiny Vault",
    "Crown Zenith Galarian Gallery",
    "Scarlet & Violet Energies",
}


def normalize(name: str) -> str:
    """Normalize a set name for fuzzy matching."""
    return (
        name.lower()
        .replace("é", "e")
        .replace("'", "'")
        .replace("\u2019", "'")
        .replace("&", "and")
        .replace(":", "")
        .replace("'", "")
        .replace("  ", " ")
        .strip()
    )


LANGUAGE_MAP = {"en": "ENGLISH", "ja": "JAPANESE"}


async def fetch_pokedata_sets(client: httpx.AsyncClient, language: str = "en") -> list[dict]:
    """Fetch all sets from pokedata.io, filtered by language."""
    resp = await client.get(f"{POKEDATA_BASE}/sets")
    resp.raise_for_status()
    all_sets = resp.json()
    lang_filter = LANGUAGE_MAP.get(language, "ENGLISH")
    return [s for s in all_sets if s.get("language") == lang_filter]


def build_set_mapping(
    db_sets: list[dict], pokedata_sets: list[dict]
) -> dict[str, int]:
    """
    Build a mapping from our DB set ID to pokedata.io set ID.
    Returns {db_set_id: pokedata_set_id}.
    """
    # Build normalized name → pokedata set lookup
    pd_by_name: dict[str, dict] = {}
    for ps in pokedata_sets:
        pd_by_name[normalize(ps["name"])] = ps

    mapping: dict[str, int] = {}
    unmatched: list[str] = []

    for db_set in db_sets:
        db_name = db_set["name"]
        db_id = db_set["id"]

        # Skip known sub-sets
        if db_name in SKIP_SUBSETS:
            logger.debug("Skipping sub-set: %s", db_name)
            continue

        # Try manual override first
        override_name = NAME_OVERRIDES.get(db_name)
        if override_name:
            norm = normalize(override_name)
            if norm in pd_by_name:
                mapping[db_id] = pd_by_name[norm]["id"]
                continue

        # Try exact normalized match
        norm = normalize(db_name)
        if norm in pd_by_name:
            mapping[db_id] = pd_by_name[norm]["id"]
            continue

        # Try substring match (our name contained in pokedata name or vice versa)
        matched = False
        for pd_norm, pd_set in pd_by_name.items():
            if norm in pd_norm or pd_norm in norm:
                mapping[db_id] = pd_set["id"]
                matched = True
                break

        if not matched:
            unmatched.append(db_name)

    if unmatched:
        logger.warning(
            "Could not match %d sets to pokedata.io: %s",
            len(unmatched),
            ", ".join(unmatched),
        )

    return mapping


async def fetch_set_cards(
    client: httpx.AsyncClient, pokedata_set_id: int
) -> list[dict]:
    """Fetch all cards for a set from pokedata.io."""
    for attempt in range(3):
        resp = await client.get(
            f"{POKEDATA_BASE}/cards", params={"set_id": pokedata_set_id}
        )
        if resp.status_code == 429:
            wait = 5 * (attempt + 1)
            logger.warning(f"Rate limited on cards (set {pokedata_set_id}), waiting {wait}s...")
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return []


async def fetch_card_stats(
    client: httpx.AsyncClient, card_ids: list[int]
) -> list[dict]:
    """Fetch price stats for a batch of cards. Chunks if needed."""
    all_stats: list[dict] = []
    chunk_size = 200  # Keep URL length reasonable

    for i in range(0, len(card_ids), chunk_size):
        chunk = card_ids[i : i + chunk_size]
        params = [("id", cid) for cid in chunk]
        for attempt in range(3):
            resp = await client.get(f"{POKEDATA_BASE}/cards/stats", params=params)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                logger.warning(f"Rate limited on stats, waiting {wait}s...")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            all_stats.extend(resp.json())
            break
        if i + chunk_size < len(card_ids):
            await asyncio.sleep(0.3)

    return all_stats


async def fetch_rarity_map(
    client: httpx.AsyncClient, set_code: str
) -> dict[str, str]:
    """
    Fetch card rarity metadata from pokemontcg.io.
    Returns {card_number: rarity} for all cards in the set.
    """
    rarity_map: dict[str, str] = {}
    page = 1
    while True:
        resp = await client.get(
            f"{POKEMON_TCG_API}/cards",
            params={
                "q": f"set.id:{set_code}",
                "select": "number,rarity",
                "pageSize": 250,
                "page": page,
            },
        )
        if resp.status_code != 200:
            logger.warning("pokemontcg.io returned %d for set %s", resp.status_code, set_code)
            break
        data = resp.json()
        cards = data.get("data", [])
        if not cards:
            break
        for c in cards:
            num = c.get("number", "")
            rarity = c.get("rarity", "Unknown")
            if num and rarity:
                rarity_map[num] = rarity
        total = data.get("totalCount", 0)
        if len(rarity_map) >= total:
            break
        page += 1
    return rarity_map


def compute_rarity_values(
    cards: list[dict],
    stats: list[dict],
    rarity_map: dict[str, str],
) -> dict[str, dict]:
    """
    Group card values by rarity tier.
    Returns {rarity: {"total": float, "count": int}}.
    """
    # Build price lookup: pokedata card_id → price
    price_by_card: dict[int, float] = {}
    for stat in stats:
        if stat.get("source") == PRICE_SOURCE and stat.get("avg") is not None:
            price_by_card[stat["card_id"]] = stat["avg"]

    # Build pokedata card_id → card_number (skip reverse holos)
    card_id_to_num: dict[int, str] = {}
    seen_nums: set[str] = set()
    for c in cards:
        name = c.get("name", "").lower()
        if "reverse" in name:
            continue
        num = c.get("num", "")
        cid = c["id"]
        # Only take the first (non-reverse) entry per card number
        if num and num not in seen_nums:
            card_id_to_num[cid] = num
            seen_nums.add(num)

    # Group prices by rarity
    rarity_totals: dict[str, dict] = {}
    unmatched = 0
    for cid, num in card_id_to_num.items():
        price = price_by_card.get(cid, 0)
        # Try exact match first, then try stripping leading zeros
        # (PokeDATA.io uses "030", pokemontcg.io uses "30")
        rarity = rarity_map.get(num)
        if not rarity:
            stripped = num.lstrip("0") or "0"
            rarity = rarity_map.get(stripped)
        if not rarity:
            unmatched += 1
            rarity = "Unknown"
        bucket = rarity_totals.setdefault(rarity, {"total": 0.0, "count": 0})
        bucket["total"] += price
        bucket["count"] += 1

    if unmatched > 0:
        logger.debug("  %d cards had no rarity match", unmatched)

    return rarity_totals


def compute_set_value(
    cards: list[dict], stats: list[dict]
) -> tuple[float, int]:
    """
    Compute total master set value from card stats.

    Sums the avg price (source=PRICE_SOURCE) for each unique card.
    Returns (total_value, card_count).
    """
    # Group stats by card_id, picking the source we want
    price_by_card: dict[int, float] = {}
    for stat in stats:
        if stat.get("source") == PRICE_SOURCE and stat.get("avg") is not None:
            card_id = stat["card_id"]
            price_by_card[card_id] = stat["avg"]

    total = sum(price_by_card.values())
    card_count = len(price_by_card)

    return round(total, 2), card_count


async def scrape_set_value(
    client: httpx.AsyncClient,
    db: Database,
    db_set: dict,
    pokedata_set_id: int,
    dry_run: bool,
    scrape_rarity: bool = False,
) -> dict | None:
    """Scrape and store the total value for a single set."""
    name = db_set["name"]
    set_id = db_set["id"]
    set_code = db_set.get("code", "")

    # Fetch cards
    cards = await fetch_set_cards(client, pokedata_set_id)
    if not cards:
        logger.warning("No cards found for %s (pokedata id %d)", name, pokedata_set_id)
        return None

    card_ids = [c["id"] for c in cards]

    # Fetch prices in batch
    stats = await fetch_card_stats(client, card_ids)
    if not stats:
        logger.warning("No price stats for %s", name)
        return None

    total_value, card_count = compute_set_value(cards, stats)

    logger.info(
        "%s: %d cards, $%.2f total value (pokedata id %d)",
        name,
        card_count,
        total_value,
        pokedata_set_id,
    )

    if not dry_run and total_value > 0:
        db.client.table("sets").update(
            {
                "total_set_value": total_value,
                "total_cards": card_count,
                "set_value_updated_at": "now()",
            }
        ).eq("id", set_id).execute()

    # Per-rarity value breakdown
    rarity_breakdown = None
    if scrape_rarity and set_code:
        logger.info("  Fetching rarity data from pokemontcg.io for %s (%s)...", name, set_code)
        try:
            rarity_map = await fetch_rarity_map(client, set_code)
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException) as e:
            logger.warning("  Timeout fetching rarity data for %s: %s", name, e)
            rarity_map = {}
        if rarity_map:
            rarity_breakdown = compute_rarity_values(cards, stats, rarity_map)
            for rarity, vals in sorted(rarity_breakdown.items(), key=lambda x: -x[1]["total"]):
                avg = vals["total"] / vals["count"] if vals["count"] > 0 else 0
                logger.info(
                    "    %-30s %3d cards  $%8.2f total  ($%.2f avg)",
                    rarity, vals["count"], vals["total"], avg,
                )

            if not dry_run:
                for rarity, vals in rarity_breakdown.items():
                    db.client.table("set_rarity_values").upsert(
                        {
                            "set_id": set_id,
                            "rarity": rarity,
                            "total_value": round(vals["total"], 2),
                            "card_count": vals["count"],
                            "updated_at": "now()",
                        },
                        on_conflict="set_id,rarity",
                    ).execute()
        else:
            logger.warning("  No rarity data from pokemontcg.io for %s (code=%s)", name, set_code)
        # Polite delay for pokemontcg.io
        await asyncio.sleep(1.0)

    return {
        "name": name,
        "cards": card_count,
        "value": total_value,
        "rarity_breakdown": rarity_breakdown,
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Scrape total set values from PokeDATA.io"
    )
    parser.add_argument(
        "--set-name", help="Only scrape a specific set by name"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print values without updating database",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape sets that already have values",
    )
    parser.add_argument(
        "--rarity",
        action="store_true",
        help="Also scrape per-rarity value breakdowns via pokemontcg.io",
    )
    parser.add_argument(
        "--language", default="en", choices=["en", "ja"],
        help="Language (en or ja)",
    )
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    # Fetch our sets and pokedata sets
    db_sets = db.get_sets(language=args.language)

    async with httpx.AsyncClient(timeout=30) as client:
        pokedata_sets = await fetch_pokedata_sets(client, args.language)

    lang_label = LANGUAGE_MAP.get(args.language, "ENGLISH")
    logger.info(
        "Found %d %s sets on pokedata.io", len(pokedata_sets), lang_label
    )

    # Build mapping
    mapping = build_set_mapping(db_sets, pokedata_sets)
    logger.info("Matched %d of %d DB sets to pokedata.io", len(mapping), len(db_sets))

    # Filter to requested sets
    if args.set_name:
        db_sets = [s for s in db_sets if s["name"] == args.set_name]
        if not db_sets:
            logger.error("Set '%s' not found in database", args.set_name)
            return

    # Skip sets already scraped (unless --force)
    if not args.force and not args.set_name:
        before = len(db_sets)
        db_sets = [s for s in db_sets if not s.get("total_set_value")]
        skipped = before - len(db_sets)
        if skipped:
            logger.info("Skipping %d sets that already have values (use --force to override)", skipped)

    # Filter to only sets we have a mapping for
    sets_to_scrape = [
        s for s in db_sets if s["id"] in mapping and s["name"] not in SKIP_SUBSETS
    ]
    unmapped = [s["name"] for s in db_sets if s["id"] not in mapping and s["name"] not in SKIP_SUBSETS]
    if unmapped:
        logger.warning("Skipping %d unmapped sets: %s", len(unmapped), ", ".join(unmapped))

    logger.info("Scraping set values for %d sets...", len(sets_to_scrape))
    start = time.time()
    results = []

    async with httpx.AsyncClient(timeout=90) as client:
        for s in sets_to_scrape:
            pd_id = mapping[s["id"]]
            result = await scrape_set_value(client, db, s, pd_id, args.dry_run, args.rarity)
            if result:
                results.append(result)
            # Delay to avoid rate limiting (pokedata.io returns 429 at high rates)
            await asyncio.sleep(1.5)

    elapsed = time.time() - start
    total_market = sum(r["value"] for r in results)

    logger.info("--- Summary ---")
    logger.info("Sets processed: %d", len(results))
    logger.info("Total market value (all sets): $%.2f", total_market)
    logger.info("Elapsed: %.1fs", elapsed)

    if args.dry_run:
        logger.info("(Dry run - no database changes made)")

    # Print top 10 most valuable sets
    results.sort(key=lambda r: r["value"], reverse=True)
    logger.info("--- Top 10 Most Valuable Sets ---")
    for i, r in enumerate(results[:10], 1):
        logger.info(
            "%2d. %-35s %4d cards  $%10.2f",
            i,
            r["name"],
            r["cards"],
            r["value"],
        )


if __name__ == "__main__":
    asyncio.run(main())
