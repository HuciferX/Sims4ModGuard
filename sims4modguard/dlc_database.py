"""
dlc_database.py
Complete catalog of all The Sims 4 DLC packs.
Maps folder codes (EP01, GP01, etc.) to pack names, types, and metadata.
"""

from pathlib import Path
from typing import Optional

# ── Master DLC catalog ────────────────────────────────────────────────────────
# Format: folder_code -> {name, type, release, adds_gameplay}
DLC_CATALOG: dict[str, dict] = {

    # ── Free Pack ──────────────────────────────────────────────────────────────
    "FP01": {
        "name": "Holiday Celebration Pack",
        "type": "Free Pack",
        "release": "2015-12-10",
        "adds_gameplay": False,
    },

    # ── Expansion Packs ────────────────────────────────────────────────────────
    "EP01": {
        "name": "Get to Work",
        "type": "Expansion Pack",
        "release": "2015-03-31",
        "adds_gameplay": True,
        "notes": "Active careers: Doctor, Scientist, Detective. Retail system.",
    },
    "EP02": {
        "name": "Get Together",
        "type": "Expansion Pack",
        "release": "2015-12-08",
        "adds_gameplay": True,
        "notes": "Clubs system, Windenburg world.",
    },
    "EP03": {
        "name": "City Living",
        "type": "Expansion Pack",
        "release": "2016-11-01",
        "adds_gameplay": True,
        "notes": "Apartment system, festivals, San Myshuno.",
    },
    "EP04": {
        "name": "Cats & Dogs",
        "type": "Expansion Pack",
        "release": "2017-11-10",
        "adds_gameplay": True,
        "notes": "Pet system, Vet career, Brindleton Bay.",
    },
    "EP05": {
        "name": "Seasons",
        "type": "Expansion Pack",
        "release": "2018-06-22",
        "adds_gameplay": True,
        "notes": "Weather system, holidays, Gardener career.",
    },
    "EP06": {
        "name": "Get Famous",
        "type": "Expansion Pack",
        "release": "2018-11-16",
        "adds_gameplay": True,
        "notes": "Fame system, acting career, Del Sol Valley.",
    },
    "EP07": {
        "name": "Island Living",
        "type": "Expansion Pack",
        "release": "2019-06-21",
        "adds_gameplay": True,
        "notes": "Mermaid occult, conservationist career, Sulani.",
    },
    "EP08": {
        "name": "Discover University",
        "type": "Expansion Pack",
        "release": "2019-11-15",
        "adds_gameplay": True,
        "notes": "University system, Foxbury/Britechester, law/engineering careers.",
    },
    "EP09": {
        "name": "Eco Lifestyle",
        "type": "Expansion Pack",
        "release": "2020-06-05",
        "adds_gameplay": True,
        "notes": "Community voting, eco footprint, fabricator, Evergreen Harbor.",
    },
    "EP10": {
        "name": "Snowy Escape",
        "type": "Expansion Pack",
        "release": "2020-11-13",
        "adds_gameplay": True,
        "notes": "Skiing/snowboarding, Lifestyles system, Mt. Komorebi.",
    },
    "EP11": {
        "name": "Cottage Living",
        "type": "Expansion Pack",
        "release": "2021-07-22",
        "adds_gameplay": True,
        "notes": "Animal husbandry, farming, Henford-on-Bagley.",
    },
    "EP12": {
        "name": "High School Years",
        "type": "Expansion Pack",
        "release": "2022-07-28",
        "adds_gameplay": True,
        "notes": "Teen high school system, prom, Copperdale.",
    },
    "EP13": {
        "name": "Growing Together",
        "type": "Expansion Pack",
        "release": "2023-03-16",
        "adds_gameplay": True,
        "notes": "Infant stage, milestones, family dynamics, San Sequoia.",
    },
    "EP14": {
        "name": "Horse Ranch",
        "type": "Expansion Pack",
        "release": "2023-07-20",
        "adds_gameplay": True,
        "notes": "Horses, nectar making, Chestnut Ridge.",
    },
    "EP15": {
        "name": "For Rent",
        "type": "Expansion Pack",
        "release": "2023-12-07",
        "adds_gameplay": True,
        "notes": "Landlord system, Tomarang world.",
    },
    "EP16": {
        "name": "Lovestruck",
        "type": "Expansion Pack",
        "release": "2024-07-25",
        "adds_gameplay": True,
        "notes": "Attraction system, dating app, Ciudad Enamorada.",
    },
    "EP17": {
        "name": "Life & Death",
        "type": "Expansion Pack",
        "release": "2024-10-31",
        "adds_gameplay": True,
        "notes": "Reaper career, ghost overhaul, Ravenwood.",
    },
    "EP18": {
        "name": "Businesses & Hobbies",
        "type": "Expansion Pack",
        "release": "2025-03-06",
        "adds_gameplay": True,
        "notes": "New business system, Hobbies skill, Ignis Oasis.",
    },
    "EP19": {
        "name": "Tales of Thornwood",
        "type": "Expansion Pack",
        "release": "2025-06-26",
        "adds_gameplay": True,
        "notes": "Woodland witchcraft, Thornwood Vale.",
    },
    "EP20": {
        "name": "Haunted By The Past",
        "type": "Expansion Pack",
        "release": "2025-10-30",
        "adds_gameplay": True,
        "notes": "Ancestral memory, spirit possession.",
    },
    "EP21": {
        "name": "Royalty & Legacy",
        "type": "Expansion Pack",
        "release": "2026-02-03",
        "adds_gameplay": True,
        "notes": "Dynasty system, nobility, EP that shipped with patch 1.121.",
    },

    # ── Game Packs ─────────────────────────────────────────────────────────────
    "GP01": {
        "name": "Outdoor Retreat",
        "type": "Game Pack",
        "release": "2015-07-16",
        "adds_gameplay": True,
        "notes": "Granite Falls vacation, herbalism skill.",
    },
    "GP02": {
        "name": "Spa Day",
        "type": "Game Pack",
        "release": "2015-09-24",
        "adds_gameplay": True,
        "notes": "Wellness skill, spa lot type.",
    },
    "GP03": {
        "name": "Dine Out",
        "type": "Game Pack",
        "release": "2016-06-07",
        "adds_gameplay": True,
        "notes": "Restaurant system, chef/host NPCs.",
    },
    "GP04": {
        "name": "Vampires",
        "type": "Game Pack",
        "release": "2017-01-24",
        "adds_gameplay": True,
        "notes": "Vampire occult, Forgotten Hollow.",
    },
    "GP05": {
        "name": "Parenthood",
        "type": "Game Pack",
        "release": "2017-05-30",
        "adds_gameplay": True,
        "notes": "Parenting skill, character values, teen/child behavior.",
    },
    "GP06": {
        "name": "Jungle Adventure",
        "type": "Game Pack",
        "release": "2018-03-06",
        "adds_gameplay": True,
        "notes": "Selvadorada vacation, archaeology skill, temple exploration.",
    },
    "GP07": {
        "name": "StrangerVille",
        "type": "Game Pack",
        "release": "2019-02-26",
        "adds_gameplay": True,
        "notes": "Mystery gameplay, StrangerVille world.",
    },
    "GP08": {
        "name": "Realm of Magic",
        "type": "Game Pack",
        "release": "2019-09-10",
        "adds_gameplay": True,
        "notes": "Spellcaster occult, The Magic Realm.",
    },
    "GP09": {
        "name": "Star Wars: Journey to Batuu",
        "type": "Game Pack",
        "release": "2020-09-08",
        "adds_gameplay": True,
        "notes": "Batuu vacation, Star Wars story content.",
    },
    "GP10": {
        "name": "Dream Home Decorator",
        "type": "Game Pack",
        "release": "2021-06-01",
        "adds_gameplay": True,
        "notes": "Interior design career, client tasks.",
    },
    "GP11": {
        "name": "My Wedding Stories",
        "type": "Game Pack",
        "release": "2022-02-17",
        "adds_gameplay": True,
        "notes": "Wedding planning, Tartosa world.",
    },
    "GP12": {
        "name": "Werewolves",
        "type": "Game Pack",
        "release": "2022-06-16",
        "adds_gameplay": True,
        "notes": "Werewolf occult, Moonwood Mill.",
    },

    # ── Stuff Packs ────────────────────────────────────────────────────────────
    "SP01": {
        "name": "Luxury Party Stuff",
        "type": "Stuff Pack",
        "release": "2015-08-06",
        "adds_gameplay": False,
    },
    "SP02": {
        "name": "Perfect Patio Stuff",
        "type": "Stuff Pack",
        "release": "2016-01-07",
        "adds_gameplay": False,
    },
    "SP03": {
        "name": "Cool Kitchen Stuff",
        "type": "Stuff Pack",
        "release": "2015-08-06",
        "adds_gameplay": False,
    },
    "SP04": {
        "name": "Spooky Stuff",
        "type": "Stuff Pack",
        "release": "2015-09-29",
        "adds_gameplay": False,
    },
    "SP05": {
        "name": "Movie Hangout Stuff",
        "type": "Stuff Pack",
        "release": "2016-04-07",
        "adds_gameplay": False,
    },
    "SP06": {
        "name": "Romantic Garden Stuff",
        "type": "Stuff Pack",
        "release": "2016-01-07",
        "adds_gameplay": False,
    },
    "SP07": {
        "name": "Kids Room Stuff",
        "type": "Stuff Pack",
        "release": "2016-06-28",
        "adds_gameplay": False,
    },
    "SP08": {
        "name": "Backyard Stuff",
        "type": "Stuff Pack",
        "release": "2016-07-19",
        "adds_gameplay": False,
    },
    "SP09": {
        "name": "Vintage Glamour Stuff",
        "type": "Stuff Pack",
        "release": "2016-11-15",
        "adds_gameplay": False,
    },
    "SP10": {
        "name": "Bowling Night Stuff",
        "type": "Stuff Pack",
        "release": "2017-03-29",
        "adds_gameplay": False,
    },
    "SP11": {
        "name": "Fitness Stuff",
        "type": "Stuff Pack",
        "release": "2017-06-06",
        "adds_gameplay": False,
    },
}

# ── Type display helpers ───────────────────────────────────────────────────────
TYPE_ABBREV = {
    "Expansion Pack": "EP",
    "Game Pack":      "GP",
    "Stuff Pack":     "SP",
    "Free Pack":      "FP",
}

TYPE_COLOR = {
    "Expansion Pack": "#00ff9f",   # neon green
    "Game Pack":      "#00e5ff",   # neon cyan
    "Stuff Pack":     "#ffaa00",   # neon amber
    "Free Pack":      "#9d00ff",   # neon purple
}


def get_all_codes() -> list[str]:
    """Return all DLC codes sorted by type then number."""
    return sorted(DLC_CATALOG.keys())


def get_by_type(pack_type: str) -> list[tuple[str, dict]]:
    """Return [(code, info)] for a given type."""
    return [(k, v) for k, v in DLC_CATALOG.items() if v["type"] == pack_type]


def inventory_installed(game_root: Path) -> dict[str, bool]:
    """
    Check which DLC folders are present in the game installation.
    Returns {code: is_installed} for all known DLC codes.
    """
    result: dict[str, bool] = {}
    for code in DLC_CATALOG:
        folder = game_root / code
        result[code] = folder.exists() and any(folder.iterdir())
    return result


def dlc_summary(game_root: Path) -> dict:
    """Return a summary dict with installed/missing counts and lists."""
    installed_map = inventory_installed(game_root)
    installed = [c for c, v in installed_map.items() if v]
    missing   = [c for c, v in installed_map.items() if not v]
    return {
        "total":     len(DLC_CATALOG),
        "installed": len(installed),
        "missing":   len(missing),
        "installed_codes": installed,
        "missing_codes":   missing,
        "installed_map":   installed_map,
    }
