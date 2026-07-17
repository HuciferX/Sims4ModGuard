"""
mod_database.py
Curated registry of known Sims 4 mods with official update URLs.

Every entry has:
  filename_patterns  : list of lowercase substrings or regex patterns to match
                       against a .package / .ts4script filename
  display_name       : human-readable mod name shown in reports
  author             : creator name
  update_url         : official public download/update page (verified 2026-07)
  patreon_required   : True if the latest version requires a Patreon subscription
  ww_dependency      : True if this mod requires WickedWhims core to function
  description        : one-line description shown in the report
  free_note          : extra note about free vs paid (shown in report)

Use lookup_mod(filename) to get the best-matching entry for any file.
"""

import re
from pathlib import Path
from typing import Optional

# ── Mod registry ──────────────────────────────────────────────────────────────
# Each entry: patterns are tested as case-insensitive substring matches.
# First match wins, so put more specific entries BEFORE generic ones.

MOD_REGISTRY: list[dict] = [

    # ── Gameplay / script mods ────────────────────────────────────────────────

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
        "free_note": "Free on Tumblr and official website. No Patreon required.",
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
    },
    {
        "id": "nisa_wicked",
        "filename_patterns": ["nisa_k", "nisak_wicked", "wicked_perversions", "nisa wicked"],
        "display_name": "Wicked Perversions by NisaK",
        "author": "NisaK",
        "update_url": "https://nisasims.wordpress.com/",
        "patreon_required": False,
        "ww_dependency": True,
        "description": "Adult content expansion for WickedWhims.",
        "free_note": "Free on WordPress. Requires WickedWhims.",
    },
    {
        "id": "ellanoir",
        "filename_patterns": ["ellanoir", "ella_noir", "flirtyfetishes", "bdsim"],
        "display_name": "EllaNoir BDSM & Fetish Mods",
        "author": "EllaNoir",
        "update_url": "https://www.patreon.com/ellanoir",
        "patreon_required": True,
        "ww_dependency": True,
        "description": "BDSM and adult roleplay content for WickedWhims.",
        "free_note": "Patreon required for latest version.",
    },
    {
        "id": "sccor",
        "filename_patterns": ["sccor", "srslysims_sccor", "srslysims-sccor"],
        "display_name": "SCCOR (SrslySims CC Override Resources)",
        "author": "SrslySims",
        "update_url": "https://srslysims.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "EA CAS and Build/Buy content override and enhancement pack.",
        "free_note": "Free on official site.",
    },
    {
        "id": "tmex_bbb",
        "filename_patterns": ["tmex-betterbuildbu", "tmex_bbb", "tmex_betterbuildbuy"],
        "display_name": "Better Build/Buy by Tmex",
        "author": "Tmex",
        "update_url": "https://www.patreon.com/c/tmex/posts",
        "patreon_required": True,
        "ww_dependency": False,
        "description": "Enhanced Build/Buy mode with search, filters, and sorting.",
        "free_note": "Patreon required.",
    },
    {
        "id": "tmex_betterexceptions",
        "filename_patterns": ["tmex-betterexceptions", "tmex_betterexceptions"],
        "display_name": "Better Exceptions by Tmex",
        "author": "Tmex",
        "update_url": "https://www.patreon.com/c/tmex/posts",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Enhanced error reporting and last-exception formatting.",
        "free_note": "Free tier available on Patreon.",
    },
    {
        "id": "tmex_modguard",
        "filename_patterns": ["tmex-modguard", "tmex_modguard"],
        "display_name": "ModGuard by Tmex",
        "author": "Tmex",
        "update_url": "https://www.patreon.com/c/tmex/posts",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Mod conflict and error detection tool.",
        "free_note": "Free tier available on Patreon.",
    },
    {
        "id": "tmex_lifetimeskills",
        "filename_patterns": ["tmex-lifetimeskills", "tmex_lifetimeskills"],
        "display_name": "Lifetime Skills by Tmex",
        "author": "Tmex",
        "update_url": "https://www.patreon.com/c/tmex/posts",
        "patreon_required": True,
        "ww_dependency": False,
        "description": "Skills that persist and grow across a Sim's lifetime.",
        "free_note": "Patreon required.",
    },
    {
        "id": "littlemssam",
        "filename_patterns": ["littlemssam", "lms_", "lms-"],
        "display_name": "LittleMsSam Mods",
        "author": "LittleMsSam",
        "update_url": "https://lms-mods.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Large collection of quality-of-life and gameplay improvement mods.",
        "free_note": "All mods free on official site.",
    },
    {
        "id": "xmlinjector",
        "filename_patterns": ["xmlinjector", "xml_injector"],
        "display_name": "XML Injector",
        "author": "Scumbumbo (maintained by community)",
        "update_url": "https://scumbumbomods.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Required dependency for many XML-based tuning mods.",
        "free_note": "Free.",
    },
    {
        "id": "andrew_poseplayer",
        "filename_patterns": ["andrew_poseplayer", "andrew_pose", "poseplayer"],
        "display_name": "Andrew's Pose Player",
        "author": "Andrew",
        "update_url": "https://www.modthesims.info/d/501895/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "In-game pose player and animator tool.",
        "free_note": "Free on ModTheSims.",
    },
    {
        "id": "kuttoe",
        "filename_patterns": ["kuttoe", "[kuttoe]"],
        "display_name": "Kuttoe Mods",
        "author": "Kuttoe",
        "update_url": "https://kuttoe.itch.io/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Trait and career expansion mods.",
        "free_note": "All mods free on itch.io.",
    },
    {
        "id": "meaningful_stories",
        "filename_patterns": ["meaningfulstories", "meaningful_stories", "roburky"],
        "display_name": "Meaningful Stories",
        "author": "roBurky",
        "update_url": "https://roburky.itch.io/sims4-meaningful-stories",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Emotional depth overhaul — mood persistence and emotion logic.",
        "free_note": "Free on itch.io.",
    },
    {
        "id": "realistic_cooking",
        "filename_patterns": ["rcm_", "realisticcooking", "realistic_cooking", "[ss] realisticcooking"],
        "display_name": "Realistic Cooking Mod (RCM)",
        "author": "simmingwithstripes",
        "update_url": "https://simmingwithstripes.tumblr.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Expanded recipe list and cooking skill overhaul.",
        "free_note": "Free on Tumblr.",
    },
    {
        "id": "life_tragedies",
        "filename_patterns": ["lifetragedies", "life_tragedies", "life's drama", "lifesdrama"],
        "display_name": "Life's Drama / Life Tragedies",
        "author": "Vitorpiresa",
        "update_url": "https://vitorpiresa.itch.io/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Random life events, tragedies, and dramatic gameplay.",
        "free_note": "Free on itch.io.",
    },
    {
        "id": "extreme_violence",
        "filename_patterns": ["extremeviolence", "extreme_violence", "ts4_extremeviolence"],
        "display_name": "Extreme Violence",
        "author": "Sacrificial",
        "update_url": "https://sacrificial-mods.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Adult violence interactions, murder, and crime gameplay.",
        "free_note": "Free on official site.",
    },
    {
        "id": "hoe_it_up",
        "filename_patterns": ["hoeitup", "hoe_it_up", "hoe it up"],
        "display_name": "Hoe It Up",
        "author": "Sacrificial",
        "update_url": "https://sacrificial-mods.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Adult escort / prostitution gameplay.",
        "free_note": "Free on official site.",
    },
    {
        "id": "cult_mod",
        "filename_patterns": ["cultmod", "cult_mod", "pimpmysims4"],
        "display_name": "Cult Mod",
        "author": "PimpMySims4",
        "update_url": "https://pimpmysims4.tumblr.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Cult leadership and control gameplay.",
        "free_note": "Free on Tumblr.",
    },
    {
        "id": "royalty_mod",
        "filename_patterns": ["royalty mod", "royaltymod", "llazyneiph"],
        "display_name": "Royalty Mod",
        "author": "llazyneiph",
        "update_url": "https://llazyneiph.tumblr.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Noble titles, monarchy, and royalty gameplay.",
        "free_note": "Free on Tumblr.",
    },
    {
        "id": "deadlystingnyc",
        "filename_patterns": ["deadlystingnyc", "deadly_sting"],
        "display_name": "DeadlystingNYC Mods",
        "author": "DeadlystingNYC",
        "update_url": "https://www.patreon.com/deadlystingNYC",
        "patreon_required": True,
        "ww_dependency": False,
        "description": "Lifestyle and adult career mods.",
        "free_note": "Patreon for latest; some free on site.",
    },
    {
        "id": "social_distancing",
        "filename_patterns": ["social_distancing", "socialdistancing", "rvsn_social"],
        "display_name": "Social Distancing Mod",
        "author": "RVSN",
        "update_url": "https://www.patreon.com/RVSN",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Sims maintain physical distance from each other.",
        "free_note": "Free.",
    },
    {
        "id": "drink_snack",
        "filename_patterns": ["drink_snack", "drinksnack", "ohmysims_mod_drink"],
        "display_name": "Drink & Snack Mod",
        "author": "OhMySims",
        "update_url": "https://www.patreon.com/OhMySims",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Expanded food and drink interactions.",
        "free_note": "Free.",
    },
    {
        "id": "nightlife_entertainer",
        "filename_patterns": ["nightlife", "entertainer", "velouramods"],
        "display_name": "Nightlife Entertainer Career",
        "author": "VelouraMods",
        "update_url": "https://www.patreon.com/VelouraMods",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Nightclub performer and entertainer career.",
        "free_note": "Free tier available.",
    },
    {
        "id": "kpop_mod",
        "filename_patterns": ["kpop mod", "kpopmod", "ks - kpop"],
        "display_name": "K-Pop Mod",
        "author": "KS",
        "update_url": "https://www.patreon.com/kssims",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "K-Pop idol career and group system.",
        "free_note": "Free tier available.",
    },
    {
        "id": "military_careers",
        "filename_patterns": ["military_career", "militarycareer", "military career"],
        "display_name": "Military Careers",
        "author": "Various",
        "update_url": "https://www.modthesims.info/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Military service careers and interactions.",
        "free_note": "Free.",
    },
    {
        "id": "sex_addict",
        "filename_patterns": ["sex_addict", "sexaddict"],
        "display_name": "Sex Addict Aspiration",
        "author": "Various",
        "update_url": "https://www.loverslab.com/",
        "patreon_required": False,
        "ww_dependency": True,
        "description": "Adult aspiration requiring WickedWhims.",
        "free_note": "Free on LoversLab. Requires WickedWhims.",
    },
    {
        "id": "turbodriver_clubs",
        "filename_patterns": ["turbodriver_clubsimprovementmods", "clubsimprovement"],
        "display_name": "Clubs Improvement Mods",
        "author": "TURBODRIVER",
        "update_url": "https://turbodriver.itch.io/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Club system improvements and expanded invite limits.",
        "free_note": "Free on itch.io.",
    },
    {
        "id": "ebonix_cc",
        "filename_patterns": ["ebonix", "ebonix_"],
        "display_name": "Ebonix CC",
        "author": "Ebonix",
        "update_url": "https://ebonixsims.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Diverse CAS hair, makeup, and clothing for dark-skinned Sims.",
        "free_note": "Free on official site.",
    },
    {
        "id": "felixandre",
        "filename_patterns": ["felixandre", "felix_estate", "felix_soho"],
        "display_name": "Felixandre Build/Buy CC",
        "author": "Felixandre",
        "update_url": "https://www.patreon.com/felixandre",
        "patreon_required": True,
        "ww_dependency": False,
        "description": "High-quality furniture and build sets.",
        "free_note": "Patreon required.",
    },
    {
        "id": "midnitetech",
        "filename_patterns": ["midnitetech", "midnite_tech"],
        "display_name": "MidniteTech Career Mods",
        "author": "MidniteTech",
        "update_url": "https://midnitetech.tumblr.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Custom career and career event overhauls.",
        "free_note": "Free on Tumblr.",
    },
    {
        "id": "qol_mods",
        "filename_patterns": ["qol_", "qol-", "qualityoflife"],
        "display_name": "Quality of Life Mods",
        "author": "Various",
        "update_url": "https://www.modthesims.info/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "General quality-of-life gameplay improvements.",
        "free_note": "Free.",
    },
    {
        "id": "thepancake1",
        "filename_patterns": ["thepancake1", "the_pancake1", "pancake1_"],
        "display_name": "thepancake1 Mods (BedCuddle, etc.)",
        "author": "thepancake1",
        "update_url": "https://www.patreon.com/thepancake1",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Comfort, cuddle, and social interaction expansions.",
        "free_note": "Free tier available on Patreon.",
    },
    {
        "id": "nc4t",
        "filename_patterns": ["nc4t_", "nc4t-", "lifetime_aspirations"],
        "display_name": "NC4T Lifetime Aspirations",
        "author": "NC4T",
        "update_url": "https://nc4t.tumblr.com/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Expanded aspiration system with elder and ghost variants.",
        "free_note": "Free on Tumblr.",
    },
    {
        "id": "vampire_cheats",
        "filename_patterns": ["vampirecheats", "vampire_cheats"],
        "display_name": "Vampire Cheats",
        "author": "MathCope",
        "update_url": "https://www.modthesims.info/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Expanded vampire power and cheat options.",
        "free_note": "Free.",
    },
    {
        "id": "rom_no_free_samples",
        "filename_patterns": ["rom_no_free_samples", "romnofreesamples"],
        "display_name": "RoM No Free Samples",
        "author": "Various",
        "update_url": "https://www.modthesims.info/",
        "patreon_required": False,
        "ww_dependency": False,
        "description": "Realm of Magic potion system adjustment.",
        "free_note": "Free.",
    },
]


# ── Lookup function ────────────────────────────────────────────────────────────

def lookup_mod(filename: str) -> Optional[dict]:
    """
    Match a package or script filename against the registry.
    Returns the first matching entry or None.
    Matching is case-insensitive substring search against filename_patterns.
    """
    name_lower = Path(filename).name.lower()
    for entry in MOD_REGISTRY:
        for pat in entry["filename_patterns"]:
            if pat.lower() in name_lower:
                return entry
    return None


def lookup_mods_in_list(filenames: list[str]) -> list[tuple[str, dict]]:
    """
    Return [(filename, mod_entry)] for every file that matches a known mod.
    """
    results = []
    for fn in filenames:
        entry = lookup_mod(fn)
        if entry:
            results.append((fn, entry))
    return results


def format_update_badge(entry: dict) -> str:
    """Return a short text badge for reports: 'Get update → URL (free/Patreon)'"""
    tag = "Patreon" if entry.get("patreon_required") else "Free"
    ww  = " | Requires WickedWhims" if entry.get("ww_dependency") else ""
    return f"→ {entry['display_name']} by {entry['author']} ({tag}{ww}): {entry['update_url']}"


def format_update_html(entry: dict) -> str:
    """Return an HTML update badge for use in the report."""
    tag   = "Patreon" if entry.get("patreon_required") else "Free"
    color = "#9d00ff" if entry.get("patreon_required") else "#00ff9f"
    ww    = " <span style='color:var(--amber)'>(Requires WickedWhims)</span>" \
            if entry.get("ww_dependency") else ""
    return (
        f"<div style='margin-top:6px;font-size:11px'>"
        f"  <span style='color:var(--dim)'>→ Get update:</span> "
        f"  <a href='{entry['update_url']}' style='color:var(--cyan)'>"
        f"    {entry['display_name']}</a>"
        f"  <span style='color:{color};margin-left:6px'>[{tag}]</span>"
        f"  {ww}"
        f"</div>"
    )
