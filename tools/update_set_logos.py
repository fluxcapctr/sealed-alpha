"""Update set logo URLs from Pokellector.com.

Maps our set names to Pokellector logo URLs and updates the sets table.
Usage: python tools/update_set_logos.py [--dry-run]
"""

import asyncio
import sys
import logging
import httpx

sys.path.insert(0, ".")
from config import Config
from db import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Direct mapping: our set name -> Pokellector logo URL
# Built from https://www.pokellector.com/sets
POKELLECTOR_LOGOS = {
    "151": "https://den-media.pokellector.com/logos/Scarlet-Violet-151.logo.374.png",
    "Ascended Heroes": "https://den-media.pokellector.com/logos/Ascended-Heroes.logo.426.png",
    "Astral Radiance": "https://den-media.pokellector.com/logos/Astral-Radiance.logo.345.png",
    "Astral Radiance Trainer Gallery": "https://den-media.pokellector.com/logos/Astral-Radiance-Trainer-Gallery.logo.348.png",
    "Battle Styles": "https://den-media.pokellector.com/logos/Battle-Styles.logo.305.png",
    "Black Bolt": "https://den-media.pokellector.com/logos/Black-Bolt.logo.420.png",
    "Brilliant Stars": "https://den-media.pokellector.com/logos/Brilliant-Stars.logo.340.png",
    "Brilliant Stars Trainer Gallery": "https://den-media.pokellector.com/logos/Brilliant-Stars-Trainer-Gallery.logo.349.png",
    "Celebrations": "https://den-media.pokellector.com/logos/Celebrations.logo.329.png",
    "Celebrations: Classic Collection": "https://den-media.pokellector.com/logos/Celebrations.logo.329.png",
    "Celestial Storm": "https://den-media.pokellector.com/logos/Celestial-Storm.logo.244.png",
    "Champion's Path": "https://den-media.pokellector.com/logos/Champions-Path.logo.298.png",
    "Chilling Reign": "https://den-media.pokellector.com/logos/Chilling-Reign.logo.320.png",
    "Cosmic Eclipse": "https://den-media.pokellector.com/logos/Cosmic-Eclipse.logo.280.png",
    "Crown Zenith": "https://den-media.pokellector.com/logos/Crown-Zenith.logo.358.png",
    "Crown Zenith Galarian Gallery": "https://den-media.pokellector.com/logos/Crown-Zenith-Galarian-Gallery.logo.365.png",
    "Darkness Ablaze": "https://den-media.pokellector.com/logos/Darkness-Ablaze.logo.296.png",
    "Destined Rivals": "https://den-media.pokellector.com/logos/Destined-Rivals.logo.412.png",
    "Detective Pikachu": "https://den-media.pokellector.com/logos/Detective-Pikachu.logo.270.png",
    "Dragon Majesty": "https://den-media.pokellector.com/logos/Dragon-Majesty.logo.257.png",
    "Evolving Skies": "https://den-media.pokellector.com/logos/Evolving-Skies.logo.325.png",
    "Forbidden Light": "https://den-media.pokellector.com/logos/Forbidden-Light.logo.239.png",
    "Fusion Strike": "https://den-media.pokellector.com/logos/Fusion-Strike.logo.335.png",
    "Hidden Fates": "https://den-media.pokellector.com/logos/Hidden-Fates.logo.279.png",
    "Hidden Fates Shiny Vault": "https://den-media.pokellector.com/logos/Hidden-Fates.logo.279.png",
    "Journey Together": "https://den-media.pokellector.com/logos/Journey-Together.logo.409.png",
    "Lost Origin": "https://den-media.pokellector.com/logos/Lost-Origin.logo.350.png",
    "Lost Origin Trainer Gallery": "https://den-media.pokellector.com/logos/Lost-Origin-Trainer-Gallery.logo.355.png",
    "Lost Thunder": "https://den-media.pokellector.com/logos/Lost-Thunder.logo.259.png",
    "McDonald's Collection 2021": "https://den-media.pokellector.com/logos/McDonalds-25th-Anniversary.logo.300.png",
    "McDonald's Collection 2022": "https://den-media.pokellector.com/logos/McDonalds-Match-Battle.logo.353.png",
    "Mega Evolution": "https://den-media.pokellector.com/logos/Mega-Evolution.logo.422.png",
    "Obsidian Flames": "https://den-media.pokellector.com/logos/Obsidian-Flames.logo.373.png",
    "Paldea Evolved": "https://den-media.pokellector.com/logos/Paldea-Evolved.logo.367.png",
    "Paldean Fates": "https://den-media.pokellector.com/logos/Paldean-Fates.logo.384.png",
    "Paradox Rift": "https://den-media.pokellector.com/logos/Paradox-Rift.logo.377.png",
    "Phantasmal Flames": "https://den-media.pokellector.com/logos/Phantasmal-Flames.logo.424.png",
"Pokémon GO": "https://den-media.pokellector.com/logos/Pokemon-Go.logo.346.png",
    "Prismatic Evolutions": "https://den-media.pokellector.com/logos/Prismatic-Evolutions.logo.407.png",
    "Rebel Clash": "https://den-media.pokellector.com/logos/Rebel-Clash.logo.292.png",
    "Scarlet & Violet": "https://den-media.pokellector.com/logos/Scarlet-Violet.logo.363.png",
    "Scarlet & Violet Black Star Promos": "https://den-media.pokellector.com/logos/Scarlet-Violet-Promos.logo.364.png",
    "Scarlet & Violet Energies": "https://den-media.pokellector.com/logos/Scarlet-Violet-Energies.logo.404.png",
    "Shining Fates": "https://den-media.pokellector.com/logos/Shining-Fates.logo.304.png",
    "Shining Fates Shiny Vault": "https://den-media.pokellector.com/logos/Shining-Fates.logo.304.png",
    "Shrouded Fable": "https://den-media.pokellector.com/logos/Shrouded-Fable.logo.399.png",
    "Silver Tempest": "https://den-media.pokellector.com/logos/Silver-Tempest.logo.354.png",
    "Silver Tempest Trainer Gallery": "https://den-media.pokellector.com/logos/Silver-Tempest-Trainer-Gallery.logo.356.png",
    "Stellar Crown": "https://den-media.pokellector.com/logos/Stellar-Crown.logo.400.png",
    "Surging Sparks": "https://den-media.pokellector.com/logos/Surging-Sparks.logo.402.png",
    "Sword & Shield": "https://den-media.pokellector.com/logos/Sword-Shield.logo.286.png",
    "SWSH Black Star Promos": "https://den-media.pokellector.com/logos/Sword-Shield-Promos.logo.287.png",
    "Team Up": "https://den-media.pokellector.com/logos/Team-Up.logo.261.png",
    "Temporal Forces": "https://den-media.pokellector.com/logos/Temporal-Forces.logo.383.png",
    "Twilight Masquerade": "https://den-media.pokellector.com/logos/Twilight-Masquerade.logo.392.png",
    "Ultra Prism": "https://den-media.pokellector.com/logos/Ultra-Prism.logo.234.png",
    "Unbroken Bonds": "https://den-media.pokellector.com/logos/Unbroken-Bonds.logo.269.png",
    "Unified Minds": "https://den-media.pokellector.com/logos/Unified-Minds.logo.275.png",
    "Vivid Voltage": "https://den-media.pokellector.com/logos/Vivid-Voltage.logo.299.png",
    "White Flare": "https://den-media.pokellector.com/logos/White-Flare.logo.421.png",
    # Sun & Moon era
    "Sun & Moon": "https://den-media.pokellector.com/logos/Sun-Moon.logo.205.png",
    "Guardians Rising": "https://den-media.pokellector.com/logos/Guardians-Rising.logo.220.png",
    "Burning Shadows": "https://den-media.pokellector.com/logos/Burning-Shadows.logo.225.png",
    "Crimson Invasion": "https://den-media.pokellector.com/logos/Crimson-Invasion.logo.229.png",
    "Shining Legends": "https://den-media.pokellector.com/logos/Shining-Legends.logo.231.png",
    # XY era
    "XY": "https://den-media.pokellector.com/logos/XY.logo.142.png",
    "Flashfire": "https://den-media.pokellector.com/logos/XY-Flashfire.logo.155.png",
    "Furious Fists": "https://den-media.pokellector.com/logos/Furious-Fists.logo.159.png",
    "Phantom Forces": "https://den-media.pokellector.com/logos/Phantom-Forces.logo.162.png",
    "Primal Clash": "https://den-media.pokellector.com/logos/Primal-Clash.logo.166.png",
    "Roaring Skies": "https://den-media.pokellector.com/logos/Roaring-Skies.logo.169.png",
    "Ancient Origins": "https://den-media.pokellector.com/logos/Ancient-Origins.logo.174.png",
    "BREAKthrough": "https://den-media.pokellector.com/logos/XY-Breakthrough.logo.179.png",
    "BREAKpoint": "https://den-media.pokellector.com/logos/BREAKPoint.logo.183.png",
    "Generations": "https://den-media.pokellector.com/logos/Generations.logo.187.png",
    "Fates Collide": "https://den-media.pokellector.com/logos/Fates-Collide.logo.188.png",
    "Steam Siege": "https://den-media.pokellector.com/logos/Steam-Siege.logo.192.png",
    "Evolutions": "https://den-media.pokellector.com/logos/Evolutions.logo.197.png",
    "Double Crisis": "https://den-media.pokellector.com/logos/Double-Crisis.logo.172.png",
}


async def verify_urls(urls: list[str]) -> dict[str, bool]:
    """Check which URLs return 200."""
    results = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for url in urls:
            try:
                resp = await client.head(url, follow_redirects=True)
                results[url] = resp.status_code == 200
            except Exception:
                results[url] = False
    return results


def main():
    dry_run = "--dry-run" in sys.argv
    config = Config()
    db = Database(config)

    resp = db.client.table("sets").select("id, name, image_url").execute()
    sets = resp.data

    updated = 0
    skipped = 0
    missing = 0

    for s in sets:
        name = s["name"]
        logo_url = POKELLECTOR_LOGOS.get(name)

        if not logo_url:
            log.warning(f"No Pokellector logo for: {name}")
            missing += 1
            continue

        if dry_run:
            log.info(f"[DRY RUN] {name} -> {logo_url}")
            updated += 1
            continue

        db.client.table("sets").update({"image_url": logo_url}).eq("id", s["id"]).execute()
        log.info(f"Updated: {name}")
        updated += 1

    log.info(f"Done: {updated} updated, {skipped} skipped, {missing} unmapped")


if __name__ == "__main__":
    main()
