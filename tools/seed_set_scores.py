"""
Seed Set Investibility Scores into the database.

Hardcoded subjective grades for each main EN set based on:
- Chase Card quality (how iconic/popular is the #1 card)
- Art Quality (overall IR/SIR/Alt Art roster)
- Nostalgia (emotional pull, generational connection)
- Fun Factor (pull rates, opening experience)
- Scarcity (print run, supply dynamics)
- Set Depth (chase diversity beyond the #1 card)

Overall grade is auto-computed from weighted sub-scores.

Usage:
    python tools/seed_set_scores.py --dry-run
    python tools/seed_set_scores.py
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from db import Database

logger = logging.getLogger("seed_set_scores")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ============================================================================
# GRADE COMPUTATION
# Weights reflect importance to sealed product investment value.
# Weighted average of sub-scores (1-10) → letter grade.
# ============================================================================

WEIGHTS = {
    "nostalgia": 1.5,
    "chase": 1.4,
    "art": 1.2,
    "depth": 1.1,
    "fun": 1.0,
    "scarcity": 1.0,
}
TOTAL_WEIGHT = sum(WEIGHTS.values())  # 7.2

# Thresholds: weighted avg → grade (with +/- modifiers, S tier has no +/-)
GRADE_THRESHOLDS = [
    (8.0, "S"),
    (7.5, "A+"),
    (7.25, "A"),
    (7.0, "A-"),
    (6.5, "B+"),
    (6.0, "B"),
    (5.5, "B-"),
    (5.0, "C+"),
    (4.75, "C"),
    (4.5, "C-"),
    (4.0, "D+"),
    (3.75, "D"),
    (3.5, "D-"),
]


def compute_grade(scores: dict) -> tuple[str, float]:
    """Compute weighted average and letter grade from sub-scores."""
    weighted = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    avg = round(weighted / TOTAL_WEIGHT, 2)
    for threshold, grade in GRADE_THRESHOLDS:
        if avg >= threshold:
            return grade, avg
    return "F", avg


# ============================================================================
# SET INVESTIBILITY SCORES
# Keys = exact set name in DB (case-insensitive match)
# chase/art/nostalgia/fun/scarcity/depth = 1-10 scores
# chase_card = name of the #1 chase card
# notes = brief reasoning
# ============================================================================

SET_SCORES = {
    # ========================================================================
    # SCARLET & VIOLET ERA
    # ========================================================================
    "Scarlet & Violet": {
        "grade": "B",
        "chase": 6, "art": 7, "nostalgia": 4, "fun": 7, "scarcity": 5, "depth": 6,
        "chase_card": "Koraidon ex SIR",
        "notes": "A solid introduction with silver borders and ARs, but lacks any significant value or iconic chase cards to make it memorable. A top tier base set.",
    },
    "Paldea Evolved": {
        "grade": "A",
        "chase": 9, "art": 8, "nostalgia": 5, "fun": 7, "scarcity": 7, "depth": 9,
        "chase_card": "Iono SIR",
        "notes": "Praised for a bloated roster of incredible Illustration Rares (Magikarp, Tyranitar) despite lacking a massive SIR chase.",
    },
    "Obsidian Flames": {
        "grade": "D",
        "chase": 7, "art": 5, "nostalgia": 4, "fun": 5, "scarcity": 4, "depth": 3,
        "chase_card": "Charizard ex SIR",
        "notes": "Often called Darkness Ablaze 2.0; relies entirely on Charizard, with the rest being lackluster and weak.",
    },
    "Paradox Rift": {
        "grade": "B",
        "chase": 6, "art": 7, "nostalgia": 4, "fun": 7, "scarcity": 5, "depth": 7,
        "chase_card": "Roaring Moon ex SIR",
        "notes": "Artistically stunning (Groudon, Roaring Moon) but generally considered forgettable with no massive main chase card to drive value.",
    },
    "151": {
        "grade": "S",
        "chase": 10, "art": 9, "nostalgia": 10, "fun": 8, "scarcity": 8, "depth": 9,
        "chase_card": "Charizard ex SIR",
        "notes": "Widely considered one of the greatest modern sets, successfully bringing people back to the hobby with Gen 1 nostalgia and master set appeal.",
    },
    "Paldean Fates": {
        "grade": "B",
        "chase": 8, "art": 7, "nostalgia": 6, "fun": 7, "scarcity": 5, "depth": 7,
        "chase_card": "Charizard ex (Shiny)",
        "notes": "Carried by the Bubble Mew and shiny Charizard; offers a fun opening experience with baby shinies even if the rest is top-heavy.",
    },
    "Temporal Forces": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 4, "fun": 7, "scarcity": 5, "depth": 7,
        "chase_card": "Walking Wake ex SIR",
        "notes": "A picture perfect Gen 9 set with great art (Raging Bolt, Walking Wake) but suffers from having no top chase the market wants.",
    },
    "Twilight Masquerade": {
        "grade": "B",
        "chase": 7, "art": 8, "nostalgia": 4, "fun": 7, "scarcity": 5, "depth": 6,
        "chase_card": "Ogerpon ex SIR",
        "notes": "A one-card set saved by the Greninja ex SIR; otherwise has low lows and lackluster Ogerpon cards.",
    },
    "Shrouded Fable": {
        "grade": "C",
        "chase": 4, "art": 5, "nostalgia": 3, "fun": 6, "scarcity": 5, "depth": 4,
        "chase_card": "Pecharunt ex SIR",
        "notes": "Widely regarded as one of the worst sets of the era; a dark Halloween-style set with no real chase cards.",
    },
    "Stellar Crown": {
        "grade": "C",
        "chase": 5, "art": 6, "nostalgia": 6, "fun": 6, "scarcity": 5, "depth": 4,
        "chase_card": "Terapagos ex SIR",
        "notes": "A small, forgettable set where the main chase (Terapagos) is considered weak and unable to carry the set's popularity.",
    },
    "Surging Sparks": {
        "grade": "A",
        "chase": 9, "art": 8, "nostalgia": 7, "fun": 7, "scarcity": 6, "depth": 7,
        "chase_card": "Pikachu ex SIR",
        "notes": "A huge level up for the era featuring a Pikachu chase and Latias/Latios, considered a strong long-term hold.",
    },
    "Prismatic Evolutions": {
        "grade": "A",
        "chase": 10, "art": 9, "nostalgia": 8, "fun": 7, "scarcity": 7, "depth": 9,
        "chase_card": "Umbreon ex SIR",
        "notes": "Immense popularity due to Eevee evolutions and god packs, though marred by severe scalping and difficult pull rates.",
    },
    "Journey Together": {
        "grade": "A",
        "chase": 7, "art": 8, "nostalgia": 6, "fun": 7, "scarcity": 5, "depth": 7,
        "chase_card": "Pikachu & Mewtwo",
        "notes": "Sold out initially on hype but prices retraced; an okay set that didn't live up to the excitement of Trainer Pokemon returning.",
    },
    "Destined Rivals": {
        "grade": "S",
        "chase": 10, "art": 9, "nostalgia": 10, "fun": 8, "scarcity": 6, "depth": 9,
        "chase_card": "Charizard & Blastoise",
        "notes": "Hailed as one of the best sets of the era due to the return of Team Rocket and a Chase Mewtwo, heavily relying on nostalgia.",
    },

    # ========================================================================
    # MEGA EVOLUTION ERA (2026)
    # ========================================================================
    "Mega Evolution": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 7, "fun": 7, "scarcity": 5, "depth": 7,
        "chase_card": "Mega Charizard EX",
        "notes": "Mega Evolution return generates hype. Nostalgic for XY-era fans.",
    },
    "Phantasmal Flames": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 6, "fun": 7, "scarcity": 5, "depth": 6,
        "chase_card": "Mega Gengar EX",
        "notes": "Ghost-themed Mega set. Gengar is always a solid chase Pokemon.",
    },
    "Ascended Heroes": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 6, "fun": 7, "scarcity": 5, "depth": 7,
        "chase_card": "Mega Lucario EX",
        "notes": "Features a crazy lineup of Pikachu, Mewtwo, and Gengar — just having these three ensures its success.",
    },
    "White Flare": {
        "grade": "B",
        "chase": 8, "art": 7, "nostalgia": 7, "fun": 7, "scarcity": 5, "depth": 6,
        "chase_card": "Mega Reshiram EX",
        "notes": "Strong Gen 5 throwback with great art, but split nature and reliance on Unova nostalgia keeps it just below S-Tier.",
    },
    "Black Bolt": {
        "grade": "B",
        "chase": 8, "art": 7, "nostalgia": 7, "fun": 7, "scarcity": 5, "depth": 6,
        "chase_card": "Mega Zekrom EX",
        "notes": "Strong Gen 5 throwback with great art, but split nature and reliance on Unova nostalgia keeps it just below S-Tier.",
    },

    # ========================================================================
    # SWORD & SHIELD ERA
    # ========================================================================
    "Sword & Shield": {
        "grade": "C",
        "chase": 6, "art": 5, "nostalgia": 3, "fun": 6, "scarcity": 5, "depth": 4,
        "chase_card": "Zacian V (Gold)",
        "notes": "Considered a weak start to the era with no significant chase cards (best card is a Rainbow Snorlax).",
    },
    "Rebel Clash": {
        "grade": "C",
        "chase": 5, "art": 5, "nostalgia": 3, "fun": 5, "scarcity": 5, "depth": 4,
        "chase_card": "Dragapult VMAX",
        "notes": "Often called Rebel Trash. Universally disliked with almost no redeeming chase cards other than a Boss's Orders Full Art.",
    },
    "Darkness Ablaze": {
        "grade": "C",
        "chase": 8, "art": 5, "nostalgia": 4, "fun": 5, "scarcity": 5, "depth": 3,
        "chase_card": "Charizard VMAX",
        "notes": "Once hyped for Charizard VMAX, now seen as boring and lackluster compared to later sets with better art rarities.",
    },
    "Vivid Voltage": {
        "grade": "A",
        "chase": 9, "art": 7, "nostalgia": 7, "fun": 8, "scarcity": 7, "depth": 7,
        "chase_card": "Pikachu VMAX (Rainbow / Fat Pikachu)",
        "notes": "Famous for the Chonkachu (Rainbow Pikachu VMAX), but the rest (Amazing Rares) has failed to hold long-term interest.",
    },
    "Champion's Path": {
        "grade": "B",
        "chase": 8, "art": 7, "nostalgia": 6, "fun": 6, "scarcity": 7, "depth": 5,
        "chase_card": "Charizard VMAX (Shiny)",
        "notes": "A trash set with two massive Charizard chase cards; miserable to open due to lack of other content.",
    },
    "Shining Fates": {
        "grade": "A",
        "chase": 9, "art": 8, "nostalgia": 6, "fun": 8, "scarcity": 8, "depth": 8,
        "chase_card": "Charizard VMAX (Shiny)",
        "notes": "Features a Shiny Charizard VMAX but otherwise filled with forgettable Gen 8 shiny Pokemon; printed heavily.",
    },
    "Battle Styles": {
        "grade": "C",
        "chase": 6, "art": 6, "nostalgia": 5, "fun": 5, "scarcity": 5, "depth": 5,
        "chase_card": "Tyranitar V (Alt Art)",
        "notes": "The first set to introduce Alt Arts (Tyranitar V), but lacks depth and is generally seen as one of the weaker main expansions.",
    },
    "Chilling Reign": {
        "grade": "B",
        "chase": 7, "art": 8, "nostalgia": 6, "fun": 6, "scarcity": 6, "depth": 7,
        "chase_card": "Blaziken VMAX (Alt Art)",
        "notes": "Known as Chilling Pain for brutal difficulty, but respected for a deep roster of Alt Arts (Blaziken, Moltres) that aged very well.",
    },
    "Evolving Skies": {
        "grade": "S",
        "chase": 10, "art": 9, "nostalgia": 8, "fun": 6, "scarcity": 9, "depth": 10,
        "chase_card": "Moonbreon (Umbreon VMAX Alt Art)",
        "notes": "The undisputed King of the era. More value than entire other eras combined despite terrible pull rates.",
    },
    "Fusion Strike": {
        "grade": "C",
        "chase": 7, "art": 7, "nostalgia": 5, "fun": 4, "scarcity": 4, "depth": 5,
        "chase_card": "Gengar VMAX (Alt Art)",
        "notes": "Initially disliked for bad pull rates, but now respected for its stacked top 5 chase cards — Gengar VMAX and Espeon VMAX.",
    },
    "Brilliant Stars": {
        "grade": "A",
        "chase": 9, "art": 8, "nostalgia": 7, "fun": 7, "scarcity": 7, "depth": 8,
        "chase_card": "Charizard VSTAR (Rainbow Secret)",
        "notes": "Changed the game by introducing the Trainer Gallery, making pull rates much better; headlined by a Charizard Alt Art.",
    },
    "Astral Radiance": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 6, "fun": 7, "scarcity": 6, "depth": 7,
        "chase_card": "Origin Forme Dialga VSTAR",
        "notes": "A good set with the Machamp V Alt Art and decent Trainer Gallery, but held back by polarizing Origin Forme Palkia/Dialga designs.",
    },
    "Lost Origin": {
        "grade": "B",
        "chase": 8, "art": 8, "nostalgia": 7, "fun": 6, "scarcity": 6, "depth": 6,
        "chase_card": "Giratina VSTAR (Alt Art)",
        "notes": "Features the Giratina V Alt Art (a top 5 card of the era) and a strong Trainer Gallery, keeping it in high regard.",
    },
    "Silver Tempest": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 6, "fun": 6, "scarcity": 6, "depth": 6,
        "chase_card": "Lugia VSTAR",
        "notes": "Carried almost entirely by the Lugia V Alt Art; a solid mid-tier set that falls off after its main chase.",
    },
    "Crown Zenith": {
        "grade": "S",
        "chase": 9, "art": 9, "nostalgia": 7, "fun": 8, "scarcity": 8, "depth": 9,
        "chase_card": "Giratina VSTAR (Gold)",
        "notes": "The best fun set to open, with the most art we've ever gotten, excellent pull rates, and the Galarian Gallery subset.",
    },
    "Celebrations": {
        "grade": "A",
        "chase": 8, "art": 7, "nostalgia": 10, "fun": 9, "scarcity": 8, "depth": 7,
        "chase_card": "Charizard (Classic Collection)",
        "notes": "Pure 25th-anniversary nostalgia. Extremely fun to open with classic reprints (Charizard, Umbreon Gold Star), though the main set is small.",
    },
    "Pokémon GO": {
        "grade": "C",
        "chase": 6, "art": 5, "nostalgia": 5, "fun": 6, "scarcity": 5, "depth": 4,
        "chase_card": "Mewtwo VSTAR (Rainbow)",
        "notes": "Gimmick-heavy and printed into oblivion; outside of the Mewtwo Alt Art, not viewed as a strong investment or collecting set.",
    },

    # ========================================================================
    # SUN & MOON ERA
    # ========================================================================
    "Sun & Moon": {
        "grade": "C",
        "chase": 6, "art": 5, "nostalgia": 4, "fun": 6, "scarcity": 6, "depth": 4,
        "chase_card": "Solgaleo GX (Full Art)",
        "notes": "GX era debut. Serviceable but not exciting.",
    },
    "Guardians Rising": {
        "grade": "B",
        "chase": 7, "art": 6, "nostalgia": 4, "fun": 6, "scarcity": 7, "depth": 6,
        "chase_card": "Tapu Lele GX (Full Art / Rainbow)",
        "notes": "Tapu Lele was the most sought-after card in the format. Competitive icon.",
    },
    "Burning Shadows": {
        "grade": "A",
        "chase": 9, "art": 7, "nostalgia": 7, "fun": 6, "scarcity": 8, "depth": 7,
        "chase_card": "Charizard GX (Rainbow Secret Rare)",
        "notes": "Rainbow Rare Charizard GX is one of the most iconic modern chase cards.",
    },
    "Crimson Invasion": {
        "grade": "D",
        "chase": 4, "art": 4, "nostalgia": 3, "fun": 4, "scarcity": 6, "depth": 3,
        "chase_card": "Silvally-GX (Full Art)",
        "notes": "Widely considered the worst Sun & Moon main set. Nothing exciting.",
    },
    "Ultra Prism": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 7, "fun": 6, "scarcity": 7, "depth": 6,
        "chase_card": "Cynthia (Full Art)",
        "notes": "Cynthia Full Art alone makes this set relevant. Gen 4 nostalgia is real.",
    },
    "Forbidden Light": {
        "grade": "C",
        "chase": 6, "art": 5, "nostalgia": 4, "fun": 5, "scarcity": 6, "depth": 5,
        "chase_card": "Ultra Necrozma GX",
        "notes": "Middle-of-the-road SM set. Ultra Necrozma is cool but not generational.",
    },
    "Celestial Storm": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 7, "fun": 6, "scarcity": 7, "depth": 6,
        "chase_card": "Rayquaza GX (Full Art / Rainbow)",
        "notes": "Rayquaza is an evergreen chase. Gen 3 nostalgia boosts this.",
    },
    "Dragon Majesty": {
        "grade": "B",
        "chase": 8, "art": 7, "nostalgia": 7, "fun": 7, "scarcity": 8, "depth": 6,
        "chase_card": "Charizard GX",
        "notes": "Mini set with concentrated dragon value. Charizard GX + scarcity = winner.",
    },
    "Lost Thunder": {
        "grade": "B",
        "chase": 7, "art": 6, "nostalgia": 6, "fun": 5, "scarcity": 6, "depth": 6,
        "chase_card": "Lugia GX (Rainbow Secret)",
        "notes": "Lugia GX and Zeraora are solid but the massive set dilutes the fun.",
    },
    "Team Up": {
        "grade": "S",
        "chase": 9, "art": 8, "nostalgia": 9, "fun": 7, "scarcity": 9, "depth": 8,
        "chase_card": "Pikachu & Zekrom GX (Alt Art)",
        "notes": "Legendary set that introduced Tag Team cards; famously underprinted, making it one of the most expensive and desirable modern sets.",
    },
    "Unbroken Bonds": {
        "grade": "A",
        "chase": 8, "art": 8, "nostalgia": 7, "fun": 7, "scarcity": 8, "depth": 8,
        "chase_card": "Reshiram & Charizard GX (Alt Art)",
        "notes": "Underrated but powerful, featuring the Reshiram & Charizard Tag Team; one of the best sets for high-end chase cards.",
    },
    "Unified Minds": {
        "grade": "B",
        "chase": 8, "art": 7, "nostalgia": 7, "fun": 6, "scarcity": 7, "depth": 6,
        "chase_card": "Mewtwo & Mew GX (Alt Art)",
        "notes": "Another strong Tag Team set featuring the Mewtwo & Mew GX, keeping it high on collectors' lists.",
    },
    "Cosmic Eclipse": {
        "grade": "A",
        "chase": 8, "art": 9, "nostalgia": 7, "fun": 7, "scarcity": 8, "depth": 9,
        "chase_card": "Pikachu (Character Rare)",
        "notes": "The finale of the era; beloved for introducing Character Rares (precursors to Trainer Galleries) and having a massive, diverse card list.",
    },
    "Hidden Fates": {
        "grade": "A",
        "chase": 9, "art": 8, "nostalgia": 7, "fun": 8, "scarcity": 9, "depth": 8,
        "chase_card": "Shiny Charizard GX",
        "notes": "The benchmark for shiny sets. The first modern shiny vault set that created massive hype and retains legendary status.",
    },
    "Shining Legends": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 7, "fun": 7, "scarcity": 7, "depth": 6,
        "chase_card": "Mewtwo GX (Rainbow Secret)",
        "notes": "Known for the Mewtube (Mewtwo in a test tube) and Shining Pokemon; fun but small.",
    },

    # ========================================================================
    # XY ERA
    # ========================================================================
    "XY": {
        "grade": "C",
        "chase": 6, "art": 5, "nostalgia": 5, "fun": 5, "scarcity": 7, "depth": 5,
        "chase_card": "Mega Venusaur EX (Full Art)",
        "notes": "Solid XY debut but overshadowed by later sets in the era.",
    },
    "Flashfire": {
        "grade": "A",
        "chase": 9, "art": 7, "nostalgia": 8, "fun": 6, "scarcity": 9, "depth": 6,
        "chase_card": "Mega Charizard EX (Full Art)",
        "notes": "Defined by Mega Charizard X; the closest thing to pulling a Base Set Charizard for that generation.",
    },
    "Furious Fists": {
        "grade": "C",
        "chase": 5, "art": 5, "nostalgia": 5, "fun": 5, "scarcity": 7, "depth": 4,
        "chase_card": "Mega Lucario EX (Full Art)",
        "notes": "Unforgiving with terrible pull rates (sometimes 1 Ultra Rare per box); largely a skippable set.",
    },
    "Phantom Forces": {
        "grade": "B",
        "chase": 7, "art": 6, "nostalgia": 7, "fun": 6, "scarcity": 8, "depth": 6,
        "chase_card": "Gengar EX (Full Art)",
        "notes": "A cult classic with a strong theme (Ghost/Steel), featuring the silver Dialga-EX and Gengar.",
    },
    "Primal Clash": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 7, "fun": 6, "scarcity": 7, "depth": 6,
        "chase_card": "Primal Kyogre EX (Full Art)",
        "notes": "Gen 3 Primal nostalgia. Kyogre and Groudon are always relevant.",
    },
    "Roaring Skies": {
        "grade": "B",
        "chase": 8, "art": 7, "nostalgia": 7, "fun": 6, "scarcity": 8, "depth": 6,
        "chase_card": "Mega Rayquaza EX (Full Art)",
        "notes": "Rayquaza is an evergreen chase. Shaymin EX was format-defining.",
    },
    "Ancient Origins": {
        "grade": "C",
        "chase": 6, "art": 6, "nostalgia": 6, "fun": 5, "scarcity": 7, "depth": 5,
        "chase_card": "Lugia EX (Full Art)",
        "notes": "A top contender for the era, featuring Shiny Primal Kyogre, Groudon, and Rayquaza.",
    },
    "BREAKthrough": {
        "grade": "B",
        "chase": 7, "art": 6, "nostalgia": 7, "fun": 6, "scarcity": 7, "depth": 6,
        "chase_card": "Mewtwo EX (Full Art)",
        "notes": "Mewtwo carries this set. BREAK mechanic was a fun addition.",
    },
    "BREAKpoint": {
        "grade": "C",
        "chase": 6, "art": 5, "nostalgia": 6, "fun": 5, "scarcity": 7, "depth": 4,
        "chase_card": "Greninja BREAK",
        "notes": "Greninja BREAK was a competitive powerhouse but limited collector appeal.",
    },
    "Generations": {
        "grade": "B",
        "chase": 7, "art": 7, "nostalgia": 8, "fun": 7, "scarcity": 8, "depth": 7,
        "chase_card": "Charizard EX (Full Art)",
        "notes": "The 20th-anniversary set; praised for the Radiant Collection subset which added unique charm and nostalgia.",
    },
    "Fates Collide": {
        "grade": "C",
        "chase": 6, "art": 5, "nostalgia": 5, "fun": 5, "scarcity": 7, "depth": 4,
        "chase_card": "Alakazam EX (Full Art)",
        "notes": "Forgettable XY set. Alakazam is cool but can't carry.",
    },
    "Steam Siege": {
        "grade": "D",
        "chase": 4, "art": 4, "nostalgia": 3, "fun": 4, "scarcity": 6, "depth": 3,
        "chase_card": "Gardevoir EX (Full Art)",
        "notes": "Widely considered the worst XY set. Zero excitement.",
    },
    "Evolutions": {
        "grade": "S",
        "chase": 9, "art": 7, "nostalgia": 10, "fun": 8, "scarcity": 9, "depth": 7,
        "chase_card": "Charizard (Holo)",
        "notes": "Heavily printed and initially mocked, but now appreciated for being a near-direct reprint of the original Base Set.",
    },
}


# Sets to explicitly skip (sub-sets, promos, mini collections)
SKIP_NAMES = {
    "sv black star promos",
    "sv energies",
    "swsh black star promos",
    "shining fates shiny vault",
    "brilliant stars trainer gallery",
    "astral radiance trainer gallery",
    "lost origin trainer gallery",
    "silver tempest trainer gallery",
    "crown zenith galarian gallery",
    "celebrations classic collection",
    "hidden fates shiny vault",
    "double crisis",
    "detective pikachu",
}


async def main():
    parser = argparse.ArgumentParser(description="Seed Set Investibility Scores")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--language", default="en", help="Language filter (default: en)")
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    # Get all sets for the language
    resp = db.client.table("sets").select("id, name, code, language").eq(
        "language", args.language
    ).execute()
    db_sets = resp.data
    logger.info(f"Found {len(db_sets)} {args.language} sets in database")

    # Build name→set mapping (case-insensitive)
    name_map = {}
    for s in db_sets:
        name_map[s["name"].lower()] = s

    matched = 0
    skipped = 0
    not_found = 0
    rows_to_upsert = []

    for set_name, scores in SET_SCORES.items():
        key = set_name.lower()
        db_set = name_map.get(key)

        if not db_set:
            logger.warning(f"  NOT FOUND in DB: '{set_name}'")
            not_found += 1
            continue

        if key in SKIP_NAMES:
            logger.info(f"  SKIPPED (sub-set): '{set_name}'")
            skipped += 1
            continue

        grade, avg = compute_grade(scores)

        row = {
            "set_id": db_set["id"],
            "overall_grade": grade,
            "chase_card_score": scores["chase"],
            "art_quality_score": scores["art"],
            "nostalgia_score": scores["nostalgia"],
            "fun_factor_score": scores["fun"],
            "scarcity_score": scores["scarcity"],
            "set_depth_score": scores["depth"],
            "chase_card_name": scores.get("chase_card"),
            "notes": scores.get("notes"),
        }
        rows_to_upsert.append((set_name, row, avg))
        matched += 1

    logger.info(f"\nMatched: {matched} | Skipped: {skipped} | Not found: {not_found}")

    # Sort by weighted average descending for display
    rows_to_upsert.sort(key=lambda x: x[2], reverse=True)

    if args.dry_run:
        logger.info("\n[DRY RUN] Would upsert the following scores:")
        for name, row, avg in rows_to_upsert:
            logger.info(
                f"  {row['overall_grade']} ({avg:.2f}) | {name} | "
                f"Chase:{row['chase_card_score']} Art:{row['art_quality_score']} "
                f"Nost:{row['nostalgia_score']} Fun:{row['fun_factor_score']} "
                f"Scar:{row['scarcity_score']} Dep:{row['set_depth_score']} | "
                f"{row['chase_card_name']}"
            )

        from collections import Counter
        grades = Counter(row['overall_grade'] for _, row, _ in rows_to_upsert)
        logger.info(f"\nGrade distribution: {dict(sorted(grades.items()))}")
        return

    # Upsert in batches
    success = 0
    for name, row, avg in rows_to_upsert:
        try:
            db.client.table("set_scores").upsert(
                row, on_conflict="set_id"
            ).execute()
            logger.info(f"  {row['overall_grade']} ({avg:.2f}) | {name}")
            success += 1
        except Exception as e:
            logger.error(f"  FAILED: {name} — {e}")

    logger.info(f"\nDone! Upserted {success}/{matched} set scores.")

    from collections import Counter
    grades = Counter(row['overall_grade'] for _, row, _ in rows_to_upsert)
    logger.info(f"Grade distribution: {dict(sorted(grades.items()))}")


if __name__ == "__main__":
    asyncio.run(main())
