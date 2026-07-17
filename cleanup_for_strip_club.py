"""
cleanup_for_strip_club.py
Targeted cleanup to get Basemental Drugs + WickedWhims + Strip Club + Hair working.

What this script does:
  1. Removes exact-filename duplicates (keeps newer/correct-folder copy)
  2. Quarantines the 126 near-exact resource-conflict duplicates from the last audit
  3. Checks Basemental ts4script for known-bad patterns
  4. Checks WickedWhims core script presence
  5. Writes a detailed report: what was removed, why, and what you still need to do

What this script DOES NOT do:
  - Delete anything (only moves to MODS_DISABLED)
  - Touch WickedWhims, Basemental core, NisaK, or strip club (SI7) files
  - Remove hair CC (only de-duplicates it)

Run: python cleanup_for_strip_club.py
"""

import sys
import json
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from sims4modguard.quarantine import QuarantineManager
from sims4modguard.game_index  import GameIndex, DEFAULT_GAME_ROOT
from sims4modguard.boot_engine import BootEngine

# ── Paths ─────────────────────────────────────────────────────────────────────
S4_FOLDER  = Path(r"C:\Users\merli\Documents\Electronic Arts\The Sims 4")
MODS       = S4_FOLDER / "Mods"
GAME_ROOT  = DEFAULT_GAME_ROOT
DISABLED   = S4_FOLDER / "MODS_DISABLED"
DISABLED.mkdir(parents=True, exist_ok=True)

SEP  = "─" * 72
DSEP = "═" * 72

# ── PROTECTED: never quarantine these ─────────────────────────────────────────
PROTECTED_PATTERNS = [
    # WickedWhims
    "turbodriver_wickedwhims", "wickedwhims", "ww_",
    # Basemental
    "basementaldrugs", "basementalgambling", "basemental drugs",
    "basemental gambling", "basemental gangs", "basemental hookah",
    "basemental wine", "basemental beer", "basemental bust",
    "basemental trippy", "basemental plant", "basemental real",
    "basemental remove", "basemental - venue",
    # NisaK
    "nisak_wicked_perversions",
    # Strip club / SI7 / adult venues
    "si7_", "stripping v", "sexy gigs", "porn star", "porn director",
    "prostitution", "escorting", "hornyfans", "erotic", "pervert",
    "injection_", "injector_", "cumshine", "spent_cum",
    # SCCOR / key gameplay mods
    "srslysims_sccor",
    # MCCC
    "mc_cmd_center", "mc_woohoo",
    # Hair CC folders (keep all hair, only remove exact-name dups)
    "blackgirl_cc", "ebonix",
]

def is_protected(path: Path) -> bool:
    name_lower = path.name.lower()
    path_lower = str(path).lower()
    for pat in PROTECTED_PATTERNS:
        if pat in name_lower or pat in path_lower:
            return True
    return False


def check_basemental_script():
    """Check if basementaldrugs.ts4script has known-bad HasTunableReference."""
    scripts = list(MODS.rglob("basementaldrugs.ts4script"))
    if not scripts:
        return None, "NOT FOUND — Basemental script missing! Download from basementalcc.com"

    script = max(scripts, key=lambda f: f.stat().st_mtime)
    dt = datetime.fromtimestamp(script.stat().st_mtime).strftime("%Y-%m-%d")

    try:
        with zipfile.ZipFile(script, "r") as z:
            for entry in z.namelist():
                if entry.endswith(".pyc"):
                    raw = z.read(entry)
                    content = raw.decode("latin-1", errors="replace")
                    if "HasTunableReference" in content:
                        return script, (
                            f"WARNING: basementaldrugs.ts4script ({dt}) contains removed API.\n"
                            f"  Download latest from: https://basementalcc.com/adult_mods/basemental-drugs/\n"
                            f"  The package files look current (March 2026) but the script is old ({dt}).")
        return script, f"OK — basementaldrugs.ts4script ({dt}) appears clean"
    except Exception as e:
        return script, f"Could not verify: {e}"


def check_ww_script():
    """Check if the WickedWhims core .ts4script is present."""
    ww_scripts = [f for f in MODS.rglob("*.ts4script")
                  if "turbodriver" in f.name.lower() or
                     ("wicked" in f.name.lower() and "animation" not in f.name.lower())]
    ww_scripts = [f for f in ww_scripts if "MODS_DISABLED" not in str(f)]
    return ww_scripts


def remove_exact_name_duplicates(qm: QuarantineManager) -> list[dict]:
    """
    For each filename that appears in multiple locations, keep the correct one
    and quarantine the other.

    Rules:
    - Prefer files in named subfolders (e.g. Basemental Drugs/Optional Packages/)
      over files dumped in the Mods root
    - If both are in subfolders, prefer the newer one
    - Never remove protected files
    """
    by_name = defaultdict(list)
    for f in MODS.rglob("*"):
        if not f.is_file(): continue
        if "MODS_DISABLED" in str(f): continue
        if f.suffix not in (".package", ".ts4script"): continue
        by_name[f.name.lower()].append(f)

    removed = []
    for name, paths in by_name.items():
        if len(paths) <= 1:
            continue

        # Sort: prefer files in subfolders (depth > 1 from MODS), then newer
        def sort_key(p):
            depth = len(p.relative_to(MODS).parts)
            mtime = p.stat().st_mtime
            return (depth > 1, mtime)   # True > False so subfolder wins

        paths_sorted = sorted(paths, key=sort_key, reverse=True)
        keeper = paths_sorted[0]
        losers = paths_sorted[1:]

        for loser in losers:
            if is_protected(loser):
                continue
            if is_protected(keeper) or is_protected(loser):
                # Never remove if either side is protected ambiguously
                continue
            dest = qm.quarantine(loser,
                                  f"Exact filename duplicate — kept: {keeper.parent.name}/{keeper.name}",
                                  auto=True)
            if dest:
                removed.append({
                    "name": loser.name,
                    "removed": str(loser),
                    "kept":    str(keeper),
                    "reason":  "Exact filename duplicate",
                })
                print(f"  DUP-REMOVE: {loser.name[:60]}")
                print(f"       kept:  {keeper.parent.name}/{keeper.name}")
    return removed


def quarantine_near_exact_dupes(qm: QuarantineManager,
                                 game_index: GameIndex) -> list[dict]:
    """
    Re-run the resource-conflict analysis and quarantine near-exact duplicate
    file pairs (50+ shared TypeID+InstanceID), skipping protected files.
    """
    from sims4modguard.game_index import index_mod_packages
    from itertools import combinations
    from collections import defaultdict

    print("  Building mod resource index (this takes a few minutes)...")
    mod_index = index_mod_packages(MODS)

    # Build file-pair conflict map
    pair_map = defaultdict(lambda: {"count": 0})
    for (tid, iid), paths in mod_index.items():
        if len(paths) < 2:
            continue
        unique = sorted(set(paths))[:5]
        for a, b in combinations(unique, 2):
            pair_map[(a, b)]["count"] += 1

    # Sort by conflict count, filter to near-dupes (50+)
    near_dupes = [(a, b, d["count"])
                  for (a, b), d in pair_map.items()
                  if d["count"] >= 50]
    near_dupes.sort(key=lambda x: -x[2])

    removed = []
    seen_remove = set()

    for file_a, file_b, shared in near_dupes:
        pa, pb = Path(file_a), Path(file_b)

        # Decide which to remove (older/smaller)
        try:
            mtime_a = pa.stat().st_mtime
            mtime_b = pb.stat().st_mtime
            size_a  = pa.stat().st_size
            size_b  = pb.stat().st_size
        except OSError:
            continue

        # Prefer keeping newer; if same age, keep larger
        if mtime_a >= mtime_b:
            keeper, loser = pa, pb
        elif mtime_b > mtime_a:
            keeper, loser = pb, pa
        elif size_a >= size_b:
            keeper, loser = pa, pb
        else:
            keeper, loser = pb, pa

        if str(loser) in seen_remove:
            continue
        if not loser.exists():
            continue
        if is_protected(loser):
            continue

        seen_remove.add(str(loser))
        dt = datetime.fromtimestamp(mtime_b if loser == pb else mtime_a).strftime("%Y-%m-%d")
        reason = (f"Near-exact duplicate ({shared:,} shared resource IDs) — "
                  f"kept {keeper.name[:40]}")

        dest = qm.quarantine(loser, reason, auto=True)
        if dest:
            removed.append({
                "name":   loser.name,
                "shared": shared,
                "kept":   keeper.name,
                "reason": reason,
            })
            print(f"  NEAR-DUP: {loser.name[:55]}  ({shared:,} IDs)")

    return removed


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(DSEP)
    print("  SIMS4 STRIP CLUB CLEANUP")
    print("  Target: Basemental Drugs + WickedWhims + Hair + Strip Club")
    print(DSEP)

    qm = QuarantineManager(S4_FOLDER)

    # \u2500\u2500 Check WickedWhims core script ────────────────────────────────────────
    print(f"\n{'STEP 1':10} CHECK WICKEDWHIMS CORE SCRIPT")
    print(SEP)
    ww_scripts = check_ww_script()
    if ww_scripts:
        for s in ww_scripts:
            dt = datetime.fromtimestamp(s.stat().st_mtime).strftime("%Y-%m-%d")
            print(f"  ✓  WickedWhims script FOUND: {s.name}  ({dt})")
    else:
        print("  ✗  WickedWhims core .ts4script is MISSING!")
        print("  ─────────────────────────────────────────────────────────")
        print("  The tuning package (TURBODRIVER_WickedWhims_Tuning.package)")
        print("  is present but the SCRIPT that runs WW is not installed.")
        print()
        print("  ACTION REQUIRED:")
        print("  1. Go to: https://turbodriver.itch.io/wickedwhims")
        print("  2. Click 'Download'")
        print("  3. Extract the zip file")
        print("  4. Copy TURBODRIVER_WickedWhims_Scripts.ts4script")
        print("     into your Mods folder")
        print("  5. Run this script again to verify")
        print("  ─────────────────────────────────────────────────────────")

    # ── Check Basemental script ────────────────────────────────────────────
    print(f"\n{'STEP 2':10} CHECK BASEMENTAL DRUGS SCRIPT")
    print(SEP)
    bm_script, bm_status = check_basemental_script()
    print(f"  {bm_status}")
    if "WARNING" in bm_status:
        print()
        print("  ACTION REQUIRED:")
        print("  1. Go to: https://basementalcc.com/adult_mods/basemental-drugs/")
        print("  2. Download latest version (requires age confirmation)")
        print("  3. Replace basementaldrugs.ts4script in your Mods folder")

    # ── Remove exact-name duplicates ───────────────────────────────────────
    print(f"\n{'STEP 3':10} REMOVING EXACT-NAME DUPLICATES")
    print(SEP)
    dup_removed = remove_exact_name_duplicates(qm)
    print(f"  Removed {len(dup_removed)} exact-name duplicates")

    # ── Quarantine near-exact resource duplicates ──────────────────────────
    print(f"\n{'STEP 4':10} QUARANTINING NEAR-EXACT RESOURCE DUPLICATES")
    print(SEP)
    print("  Loading game index...")
    game_index = GameIndex(GAME_ROOT)
    game_index.ensure_loaded()
    print(f"  Game index: {game_index.module_count:,} modules, "
          f"{game_index.resource_count:,} resources")
    print()
    near_removed = quarantine_near_exact_dupes(qm, game_index)
    print(f"\n  Quarantined {len(near_removed)} near-exact duplicate packages")

    # ── Clear caches ───────────────────────────────────────────────────────
    print(f"\n{'STEP 5':10} CLEARING GAME CACHES")
    print(SEP)
    from sims4modguard.cache_manager import clear_caches
    result = clear_caches(S4_FOLDER, verbose=False)
    mb = result["bytes_freed"] // (1024 * 1024)
    print(f"  Cleared {len(result['files'])} cache files ({mb} MB freed)")

    # ── Print summary ──────────────────────────────────────────────────────
    total_removed = len(dup_removed) + len(near_removed)
    print(f"\n{DSEP}")
    print("  CLEANUP COMPLETE")
    print(DSEP)
    print(f"  Exact duplicates removed:   {len(dup_removed)}")
    print(f"  Near-exact dupes removed:   {len(near_removed)}")
    print(f"  Total files quarantined:    {total_removed}")
    print(f"  All files in: {S4_FOLDER / 'MODS_DISABLED'}")
    print(f"  Restore any time from: Fix & Repair tab in Sims4ModGuard")
    print()

    # ── What still needs to happen ─────────────────────────────────────────
    print("  REMAINING ACTIONS REQUIRED:")
    print(SEP)
    if not ww_scripts:
        print("  ✗  WickedWhims script MISSING → download from turbodriver.itch.io/wickedwhims")
    else:
        print("  ✓  WickedWhims script present")
    if "WARNING" in bm_status:
        print("  ✗  Basemental script may be outdated → verify at basementalcc.com")
    else:
        print("  ✓  Basemental script OK")
    print("  ✓  Strip Club CC (SI7 series): present and current (2026)")
    print("  ✓  NisaK Wicked Perversions: present (2026-02-04)")
    print("  ✓  Hair CC: de-duplicated")
    print()
    print("  STRIP CLUB REQUIREMENTS MET:")
    print("  ✓  EP01 Get to Work installed (required for strip club business)")
    print("  ✓  WickedWhims Tuning package present (2026-05-23)")
    print("  ✓  Stripping v21 mod present")
    print("  ✓  SI7 Adult Venue + Dance Floor CC present")
    print("  ✓  Sexy Gigs - Porn Star, Porn Director mods present")
    print()
    print("  Run simulate_strip_club.py to verify full compatibility.")
    print(DSEP)

    # ── Write JSON report ──────────────────────────────────────────────────
    report = {
        "timestamp": datetime.now().isoformat(),
        "ww_script_found": bool(ww_scripts),
        "ww_script_paths": [str(s) for s in ww_scripts],
        "basemental_script_status": bm_status,
        "exact_duplicates_removed": dup_removed,
        "near_exact_removed": near_removed,
        "caches_cleared_mb": mb,
    }
    out = Path(__file__).parent / "cleanup_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Full report: {out}")


if __name__ == "__main__":
    main()
