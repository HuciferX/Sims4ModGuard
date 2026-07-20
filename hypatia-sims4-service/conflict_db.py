"""
conflict_db.py
Loads the known Sims 4 mod conflict database.

Sources (in priority order):
1. Local mod_database.py embedded copy (always available, no network needed)
2. GitHub raw JSON overrides fetched at startup (extends / overrides local data)

The DB is loaded once at startup and cached in memory.
Call `get_db()` anywhere to get the current snapshot.
"""

import json
import logging
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# GitHub raw URL for community-submitted conflict overrides JSON
GITHUB_RAW_CONFLICTS_URL = (
    "https://raw.githubusercontent.com/HuciferX/Sims4ModGuard/master/"
    "data/conflicts.json"
)

# ---------------------------------------------------------------------------
# Embedded baseline — mirrors sims4modguard/mod_database.py MOD_REGISTRY
# so the service works completely offline.
# ---------------------------------------------------------------------------
BASELINE_REGISTRY: list[dict[str, Any]] = [
    {
        "id": "wickedwhims",
        "filename_patterns": ["wickedwhims", "wicked_whims", "turbodriver_ww"],
        "display_name": "WickedWhims",
        "author": "TURBODRIVER",
        "update_url": "https://turbodriver.itch.io/wickedwhims",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Adult animations, nudity, and relationship overhaul mod.",
        "free_note": "Public version free on itch.io; Patreon for early access.",
        "known_conflicts": [],
        "broken_since_patch": None,
    },
    {
        "id": "mccc",
        "filename_patterns": ["mc_cmd_center", "mccmdcenter", "mc_woohoo", "mccmdcenter_allmodules"],
        "display_name": "MC Command Center (MCCC)",
        "author": "Deaderpool",
        "update_url": "https://deaderpoolmc.tumblr.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Comprehensive story progression, population, and game control mod.",
        "free_note": "Free on Tumblr and official website.",
        "known_conflicts": [],
        "broken_since_patch": None,
    },
    {
        "id": "basemental_drugs",
        "filename_patterns": ["basemental drugs", "basemental_drugs", "basementaldrugs"],
        "display_name": "Basemental Drugs",
        "author": "Basemental",
        "update_url": "https://basementalcc.com/adult_mods/basemental-drugs/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Drug use, dealing, and addiction gameplay.",
        "free_note": "Free (age verification required on site).",
        "known_conflicts": [],
        "broken_since_patch": None,
    },
    {
        "id": "basemental_gambling",
        "filename_patterns": ["basemental gambling", "basemental_gambling", "basementalgambling"],
        "display_name": "Basemental Gambling",
        "author": "Basemental",
        "update_url": "https://basementalcc.com/mods/basemental-gambling/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Casino and gambling gameplay.",
        "free_note": "Free (age verification required on site).",
        "known_conflicts": [],
        "broken_since_patch": None,
    },
    {
        "id": "nisa_wicked",
        "filename_patterns": ["nisa_k", "nisak_wicked", "wicked_perversions", "nisa wicked"],
        "display_name": "Wicked Perversions by NisaK",
        "author": "NisaK",
        "update_url": "https://nisasims.wordpress.com/",
        "patreon_required": False,
        "ww_dependency": True,
        "description": "Adult gameplay expansion for WickedWhims.",
        "free_note": "Free via WordPress; optional Patreon tier.",
        "known_conflicts": ["wickedwhims"],
        "broken_since_patch": None,
    },
    {
        "id": "wonderful_whims",
        "filename_patterns": ["wonderful_whims", "wonderfulwhims"],
        "display_name": "Wonderful Whims",
        "author": "TURBODRIVER",
        "update_url": "https://turbodriver.itch.io/wonderfulwhims",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Attraction, personality, and relationship system overhaul (SFW alternative to WW).",
        "free_note": "Free on itch.io.",
        "known_conflicts": ["wickedwhims"],
        "broken_since_patch": None,
    },
    {
        "id": "kuttoe_social",
        "filename_patterns": ["kuttoe", "social_activities"],
        "display_name": "Kuttoe's Social Activities",
        "author": "Kuttoe",
        "update_url": "https://kuttoe.itch.io/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Expanded social interactions and activities.",
        "free_note": "Free on itch.io.",
        "known_conflicts": [],
        "broken_since_patch": None,
    },
    {
        "id": "lumpinou_pregnancy",
        "filename_patterns": ["lumpinou", "pregnancy_mega_mod", "pregnancymod"],
        "display_name": "Lumpinou's Pregnancy Mega Mod",
        "author": "Lumpinou",
        "update_url": "https://lumpinou.itch.io/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Overhaul of pregnancy mechanics.",
        "free_note": "Free on itch.io.",
        "known_conflicts": [],
        "broken_since_patch": None,
    },
    {
        "id": "ui_cheats",
        "filename_patterns": ["ui_cheats", "uicheats", "ui cheats extension"],
        "display_name": "UI Cheats Extension",
        "author": "weerbesu",
        "update_url": "https://www.patreon.com/weerbesu",
        "patreon_required": True,
        "ww_dependency": False,
        "description": "Click-to-cheat integration directly in the game UI.",
        "free_note": "Requires Patreon subscription for latest patch-compatible version.",
        "known_conflicts": [],
        "broken_since_patch": None,
    },
    {
        "id": "tmex_overhaul",
        "filename_patterns": ["tmex", "turbodriver_tmex"],
        "display_name": "TMEX Overhaul",
        "author": "TURBODRIVER",
        "update_url": "https://turbodriver.itch.io/tmex-overhaul",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Menu / interaction performance overhaul.",
        "free_note": "Free on itch.io.",
        "known_conflicts": [],
        "broken_since_patch": None,
    },
    {
        "id": "lot51_core",
        "filename_patterns": ["lot51_core", "lot51 core", "lot51core"],
        "display_name": "Lot 51 Core Library",
        "author": "Lot51",
        "update_url": "https://lot51.cc/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Shared core library required by multiple Lot51 mods.",
        "free_note": "Free.",
        "known_conflicts": [],
        "broken_since_patch": None,
    },
]

# In-memory cache
_db: list[dict[str, Any]] = []


def _match(filename: str, patterns: list[str]) -> bool:
    """Return True if any pattern matches (case-insensitive substring or regex)."""
    fname = filename.lower()
    for pat in patterns:
        try:
            if re.search(pat.lower(), fname):
                return True
        except re.error:
            if pat.lower() in fname:
                return True
    return False


async def load_db() -> None:
    """
    Load the conflict database into memory.
    Starts with BASELINE_REGISTRY and tries to extend from GitHub.
    """
    global _db
    _db = list(BASELINE_REGISTRY)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(GITHUB_RAW_CONFLICTS_URL)
            if resp.status_code == 200:
                remote_data: list[dict] = resp.json()
                existing_ids = {e["id"] for e in _db}
                added = 0
                for entry in remote_data:
                    if entry.get("id") not in existing_ids:
                        _db.append(entry)
                        existing_ids.add(entry["id"])
                        added += 1
                    else:
                        # Remote overrides local for same id
                        _db = [entry if e["id"] == entry["id"] else e for e in _db]
                logger.info("Loaded %d remote conflict entries (+%d new).", len(remote_data), added)
            else:
                logger.warning(
                    "Remote conflicts DB returned HTTP %s — using baseline only.",
                    resp.status_code,
                )
    except Exception as exc:
        logger.warning("Could not fetch remote conflicts DB (%s) — using baseline only.", exc)

    logger.info("Conflict DB ready: %d entries total.", len(_db))


def get_db() -> list[dict[str, Any]]:
    """Return the full in-memory conflict database."""
    return _db


def lookup_mod(filename: str) -> Optional[dict[str, Any]]:
    """
    Return the first DB entry whose filename_patterns match *filename*.
    Returns None if no match found.
    """
    for entry in _db:
        if _match(filename, entry.get("filename_patterns", [])):
            return entry
    return None


def db_size() -> int:
    return len(_db)
