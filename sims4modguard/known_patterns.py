"""
known_patterns.py
All detection rules learned from patch 1.121 breakage.
Add new rules here as more patches break more things.
"""

# ── Patch-removed Python APIs (quarantine-only, cannot fix) ──────────────────
REMOVED_APIS = [
    "HasTunableReference",          # Removed in 1.121 — affects r3m, Kuttoe, Scumbumbo
    "HasTunableFactory",            # Related removal
    "genealogy_caching",            # Family tree overhaul in 1.121
    "genealogy_tracker",            # Deprecated
    "TunableLocalizedString",       # Changed signature
]

# ── Broken injection patterns (quarantine or patch) ──────────────────────────
BROKEN_INJECT_PATTERNS = [
    # Old-style 2-arg wrapper — EA now passes 3 args (added manager param)
    r"new_function\(target_function, \*args",
    r"def _inject\(",
    r"_inject\(",
    r"lmsinjector",
    r"inject_load_data_into_class_instances",
    r"inject_to_top_of_class_list",
    r"inject_list_to_top",
    r"add_super_affordances",
    r"add_superaffordances",
    r"AddMixer_\d+",
    r"inject_interactions",
]

# ── WickedWhims dependency markers ───────────────────────────────────────────
WW_DEPENDENCY_MARKERS = [
    "wickedwhims",
    "wicked_whims",
    "turbolib2",
    "turbolib",
    "ww_injections",
    "ww_overrides",
    "add_wicked_attributes",
]

# ── WW-dependent filenames (package and script) ───────────────────────────────
WW_FILENAME_PATTERNS = [
    r"^WW_",
    r"^AEP_",
    r"NisaK_Wicked",
    r"EllaNoir.*BDSM",
    r"EllaNoir.*Fetish",
    r"WickedWhims_LP",
]

# ── TUNING CONFLICT SIGNATURES (posture/reservation system) ───────────────────
# CC packages that contain these tuning references may break EA objects
# when patch 1.121 changed provided_posture_type and object_reservation_tests
TUNING_CONFLICT_SIGNATURES = [
    b"provided_posture_type",
    b"object_reservation_tests",
    b"SLEEPING",
    b"PostureStateMachine",
]

# ── Known corrupt/broken script names ─────────────────────────────────────────
KNOWN_DEAD_MODS = {
    # Format: filename_lower: reason
    "basementaldrugs.ts4script":        "Old version — HasTunableReference removed in 1.121",
    "basementalgambling.ts4script":     "Old version — HasTunableReference removed in 1.121",
    "r3m_spellbook_injector.ts4script": "HasTunableReference removed, creator inactive",
    "r3m_ufo_hotspot.ts4script":        "HasTunableReference removed, creator inactive",
    "r3m_ufo_investigator.ts4script":   "HasTunableReference removed, creator inactive",
}

# ── Known updatable mods — stable public download pages ──────────────────────
KNOWN_UPDATE_URLS = {
    "basemental_drugs": {
        "display": "Basemental Drugs (public)",
        "url": "https://basementalcc.com/adult_mods/basemental-drugs/",
        "age_cookie": True,
        "install_folder": "Basemental_Drugs",
    },
    "basemental_gambling": {
        "display": "Basemental Gambling (public)",
        "url": "https://basementalcc.com/mods/basemental-gambling/",
        "age_cookie": True,
        "install_folder": "Basemental_Gambling",
    },
    "basemental_venue_list": {
        "display": "Basemental Universal Venue List",
        "url": "https://basementalcc.com/mods/universal-venue-list/",
        "age_cookie": True,
        "direct_package": "https://basementalcc.com/wp-content/uploads/2026/06/Basemental-Venue-List.package",
        "install_folder": "Basemental_Drugs",
    },
    "meaningful_stories": {
        "display": "MeaningfulStories by roBurky",
        "url": "https://roburky.itch.io/sims4-meaningful-stories",
        "install_folder": "MeaningfulStories",
    },
    "kuttoe_enlistinwar": {
        "display": "EnlistInWar by Kuttoe",
        "url": "https://kuttoe.itch.io/enlist-in-war-mod",
        "install_folder": "Kuttoe_EnlistInWar",
    },
    "kuttoe_newspadaday": {
        "display": "NewSpaDayTraits by Kuttoe",
        "url": "https://kuttoe.itch.io/new-spa-day-traits",
        "install_folder": "Kuttoe_NewSpaDayTraits",
    },
    "mccc_2026_1_1": {
        "display": "MCCC 2026.1.1 (for game patch 1.121.x)",
        "url": "https://modsfire.com/n1X8R6z9CHY432f",
        "manual": True,
        "install_folder": "MCCC_2026_1_1",
    },
}

# ── Game version compatibility matrix ─────────────────────────────────────────
GAME_PATCHES = {
    "1.121": {
        "release": "2026-02-03",
        "expansion": "Royalty & Legacy (EP21)",
        "broke": [
            "HasTunableReference",
            "HasTunableFactory",
            "genealogy_caching",
            "inject_load_data_into_class_instances (2-arg form)",
            "add_super_affordances (2-arg form)",
            "inject_interactions (2-arg form)",
        ],
        "mccc_min": "2026.1.1",
        "basemental_min": "8.18.182",
    },
    "1.122": {
        "release": "2026-03-17",
        "expansion": None,
        "broke": [],
        "mccc_min": "2026.2.0",
    },
    "1.123": {
        "release": "2026-04-16",
        "expansion": None,
        "broke": [],
        "mccc_min": "2026.3.0",
    },
}

# ── Known-safe scripts (whitelist — skip injection pattern checks) ────────────
# These mods are safe even if they contain inject-looking patterns.
KNOWN_SAFE_SCRIPTS = {
    # Error/utility tools
    "tmex-betterexceptions.ts4script",
    "xmlinjector_script_v4.2.ts4script",
    "turbodriver_clubsimprovementmods_invitelimit.ts4script",
    "vampirecheats_mathcope.ts4script",
    "andrew_poseplayer.ts4script",
    "littlemssam_morebuyablevenues.ts4script",
    # MCCC 2026.1.1 — verified working on patch 1.121.x
    "mc_cmd_center.ts4script",
    "mc_woohoo.ts4script",
    "mc_career.ts4script",
    "mc_cas.ts4script",
    "mc_cheats.ts4script",
    "mc_cleaner.ts4script",
    "mc_clubs.ts4script",
    "mc_control.ts4script",
    "mc_dresser.ts4script",
    "mc_gedcom.ts4script",
    "mc_occult.ts4script",
    "mc_population.ts4script",
    "mc_pregnancy.ts4script",
    "mc_tuner.ts4script",
    # Basemental 8.18.x — verified working on patch 1.121.x
    # (has optional WW references but does not require WW)
    "basementaldrugs.ts4script",
    "basementalgambling.ts4script",
    # Kuttoe ForbiddenSpells — verified clean
    "[kuttoe] forbiddenspells.ts4script",
}

# ── Exception message -> plain English explanations ───────────────────────────
ERROR_EXPLANATIONS = {
    "HasTunableReference":
        "This mod uses a Python class EA removed in patch 1.121. It cannot be auto-fixed.",
    "genealogy_caching":
        "This mod hooks into genealogy/family tree code removed in patch 1.121.",
    "No module named 'wickedwhims'":
        "This mod requires WickedWhims core (.ts4script) which is not installed.",
    "No module named 'turbolib2'":
        "This mod requires TurboLib2, bundled inside WickedWhims. Install WickedWhims core.",
    "takes 2 positional arguments but 3 were given":
        "This mod uses old injection code. EA added a 'manager' argument in patch 1.121.",
    "object_reservation_tests":
        "A CC package overrides object interaction tuning in a way incompatible with patch 1.121.",
    "provided_posture_type":
        "A CC package overrides bed/seat posture data incompatible with patch 1.121.",
    "has_instanced_phases":
        "A CC crafting/recipe object uses tuning that changed in patch 1.121.",
    "gardening_component":
        "A CC gardening object overrides tuning changed in patch 1.121.",
    "inject_load_data_into_class_instances":
        "Old injection wrapper. EA changed the calling convention in patch 1.121.",
}
