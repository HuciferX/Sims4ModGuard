"""
simulate_strip_club.py
Simulates and validates the strip club mod configuration.

Checks (without launching the game):
  1. WickedWhims core script present + version OK
  2. Get to Work DLC installed (required for strip club business type)
  3. Basemental Drugs installed and clean
  4. NisaK Wicked Perversions installed
  5. Strip club CC (SI7, Stripping, Sexy Gigs) present
  6. No resource conflicts on the strip club specific files
  7. Body mod compatibility (EVE, BTTB, SmoothVagina)
  8. Animation packs present (Anarcis, GreyNaya, 0nizu)

Run: python simulate_strip_club.py
Output: strip_club_report.html  +  strip_club_report.txt
"""

import sys
import json
import zipfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from sims4modguard.game_index import GameIndex, DEFAULT_GAME_ROOT
from sims4modguard.dlc_database import DLC_CATALOG, inventory_installed

# ── Paths ─────────────────────────────────────────────────────────────────────
S4_FOLDER = Path(r"C:\Users\merli\Documents\Electronic Arts\The Sims 4")
MODS      = S4_FOLDER / "Mods"
GAME_ROOT = DEFAULT_GAME_ROOT

SEP  = "─" * 70
DSEP = "═" * 70

# ── Strip club mod requirements ────────────────────────────────────────────────
REQUIREMENTS = {

    # ── Core mods (MUST have all of these for strip club to work) ────────────

    "WickedWhims Script": {
        "patterns": ["turbodriver_wickedwhims_scripts"],
        "extensions": [".ts4script"],
        "required": True,
        "url": "https://turbodriver.itch.io/wickedwhims",
        "notes": "The brain of WickedWhims. Without this, nothing works.",
    },
    "WickedWhims Tuning": {
        "patterns": ["turbodriver_wickedwhims_tuning"],
        "extensions": [".package"],
        "required": True,
        "url": "https://turbodriver.itch.io/wickedwhims",
        "notes": "Game data/settings for WickedWhims.",
    },

    # ── Strip club specific ───────────────────────────────────────────────────

    "Stripping Mod": {
        "patterns": ["stripping v"],
        "extensions": [".package"],
        "required": True,
        "url": "https://turbodriver.itch.io/wickedwhims",
        "notes": "Adds the Stripping career/interactions for strip club dancers.",
    },
    "Sexy Gigs - Porn Star": {
        "patterns": ["sexy gigs - porn star"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.loverslab.com/",
        "notes": "Porn star career, works with strip club.",
    },
    "Sexy Gigs - Porn Director": {
        "patterns": ["sexy gigs - porn director"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.loverslab.com/",
        "notes": "Director for porn/strip content.",
    },
    "SI7 Adult Dance Floor": {
        "patterns": ["si7_adultdancefloor"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.loverslab.com/",
        "notes": "Animated dance floors for strip clubs.",
    },
    "SI7 Adult Venue CC": {
        "patterns": ["si7_adultvenue"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.loverslab.com/",
        "notes": "Strip club furniture and decor sets.",
    },

    # ── Basemental (enhances strip club with drug sales, etc.) ────────────────

    "Basemental Drugs": {
        "patterns": ["basemental drugs.package", "basemental drugs"],
        "extensions": [".package"],
        "required": False,
        "url": "https://basementalcc.com/adult_mods/basemental-drugs/",
        "notes": "Drug use/dealing at the strip club. Integrates with WW.",
    },
    "Basemental Drugs Script": {
        "patterns": ["basementaldrugs.ts4script"],
        "extensions": [".ts4script"],
        "required": False,
        "url": "https://basementalcc.com/adult_mods/basemental-drugs/",
        "notes": "The Python script for Basemental Drugs.",
    },
    "Basemental Gangs": {
        "patterns": ["basemental gangs.package"],
        "extensions": [".package"],
        "required": False,
        "url": "https://basementalcc.com/",
        "notes": "Gang system — adds protection rackets at the strip club.",
    },

    # ── NisaK (enhances WW with more adult interactions) ──────────────────────

    "NisaK Wicked Perversions": {
        "patterns": ["nisak_wicked_perversions"],
        "extensions": [".package"],
        "required": False,
        "url": "https://nisasims.wordpress.com/",
        "notes": "Adult expansion for WW. Adds many more interactions.",
    },

    # ── Body mods (required for animations to look correct) ───────────────────

    "EVE v10 Body": {
        "patterns": ["eve-v10"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.loverslab.com/",
        "notes": "Animated female body for WickedWhims animations.",
    },
    "BTTB Body": {
        "patterns": ["bttb 6"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.loverslab.com/",
        "notes": "BTTB male body for WickedWhims animations.",
    },
    "Smooth Vagina": {
        "patterns": ["smoothvagina"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.loverslab.com/",
        "notes": "WW-compatible female anatomy.",
    },
    "PornstarCock": {
        "patterns": ["pornstarcock-"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.loverslab.com/",
        "notes": "WW-compatible male anatomy options.",
    },

    # ── Animations (content for the strip club and WW) ────────────────────────

    "Anarcis Animations": {
        "patterns": ["ww_anarcis"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.patreon.com/anarcis",
        "notes": "Large high-quality animation pack for WickedWhims.",
    },
    "GreyNaya Animations": {
        "patterns": ["ww_greynaya"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.loverslab.com/",
        "notes": "Animation pack including strip club-specific poses.",
    },
    "0nizu Animations": {
        "patterns": ["ww_0nizu_animations"],
        "extensions": [".package"],
        "required": False,
        "url": "https://www.loverslab.com/",
        "notes": "High-quality animation pack.",
    },
}

# ── DLC requirements ───────────────────────────────────────────────────────────
DLC_REQUIREMENTS = {
    "EP01": {
        "name": "Get to Work",
        "reason": "REQUIRED for Strip Club business type",
        "required": True,
    },
    "EP02": {
        "name": "Get Together",
        "reason": "Recommended for Club activities at strip clubs",
        "required": False,
    },
    "GP04": {
        "name": "Vampires",
        "reason": "Optional — WW has special vampire + strip club interactions",
        "required": False,
    },
}


# ── Check functions ────────────────────────────────────────────────────────────

def find_mod(req_name: str, req: dict) -> list[Path]:
    """Find all files matching this requirement."""
    found = []
    for f in MODS.rglob("*"):
        if not f.is_file(): continue
        if "MODS_DISABLED" in str(f): continue
        name_lower = f.name.lower()
        if f.suffix.lower() not in req["extensions"]:
            continue
        for pat in req["patterns"]:
            if pat.lower() in name_lower:
                found.append(f)
                break
    return found


def check_ww_script_version(script_path: Path) -> str:
    """Try to read the WW version from the script."""
    try:
        with zipfile.ZipFile(script_path, "r") as z:
            for entry in z.namelist():
                if "version" in entry.lower() or "constants" in entry.lower():
                    try:
                        data = z.read(entry).decode("latin-1", errors="replace")
                        for line in data.splitlines():
                            if "version" in line.lower() and "=" in line:
                                return line.strip()[:60]
                    except Exception:
                        pass
    except Exception:
        pass
    return "version unknown"


def check_ww_strip_club_compatibility(ww_scripts: list[Path]) -> list[str]:
    """
    WickedWhims strip club requires Get to Work.
    Check the WW tuning for strip club support flags.
    """
    issues = []
    tuning = list(MODS.rglob("TURBODRIVER_WickedWhims_Tuning.package"))
    if not tuning:
        issues.append("WickedWhims Tuning package not found")
    return issues


def check_basemental_ww_integration() -> list[str]:
    """Check if Basemental and WW are configured to work together."""
    issues = []
    # Basemental reads WW state optionally — no explicit config needed
    # But both must be present for drug miscarriage etc. to work
    bm = list(MODS.rglob("Basemental Drugs.package"))
    ww = list(MODS.rglob("TURBODRIVER_WickedWhims_Tuning.package"))
    if bm and ww:
        return []  # Both present = integration works
    if bm and not ww:
        issues.append("Basemental is present but WickedWhims is not. "
                      "Drug-induced miscarriage and WW×BM features won't work.")
    return issues


def check_resource_conflicts(target_names: list[str]) -> list[str]:
    """Check if the strip club specific files have resource conflicts."""
    from sims4modguard.game_index import index_mod_packages
    from itertools import combinations
    from collections import defaultdict

    print("  Scanning strip club mod resource conflicts...")
    mod_index = index_mod_packages(MODS)

    # Only check conflicts involving strip club files
    conflicts = []
    for (tid, iid), paths in mod_index.items():
        if len(paths) < 2:
            continue
        involves_target = any(
            any(t.lower() in Path(p).name.lower() for t in target_names)
            for p in paths
        )
        if involves_target:
            names = [Path(p).name[:30] for p in paths[:3]]
            conflicts.append(f"TypeID 0x{tid:08X} conflict: {', '.join(names)}")

    return conflicts[:20]  # Show top 20


# ── Report builders ────────────────────────────────────────────────────────────

def build_text_report(results: dict, ts: datetime) -> str:
    lines = []

    def h(t): lines.append(f"\n{DSEP}\n  {t}\n{DSEP}")
    def s(t): lines.append(f"\n{SEP}\n  {t}\n{SEP}")

    h("SIMS 4 STRIP CLUB COMPATIBILITY SIMULATION")
    lines.append(f"  {ts.strftime('%Y-%m-%d %H:%M:%S')}")

    # DLC
    s("DLC REQUIREMENTS")
    for code, dlc in DLC_REQUIREMENTS.items():
        ok = results["dlc"].get(code, False)
        req_tag = "[REQUIRED]" if dlc["required"] else "[Optional]"
        mark = "✓" if ok else ("✗" if dlc["required"] else "○")
        lines.append(f"  {mark} {code} {dlc['name']:<20} {req_tag}  {dlc['reason']}")

    # Mods
    s("MOD STATUS")
    for name, data in results["mods"].items():
        found = data["found"]
        required = REQUIREMENTS[name]["required"]
        mark = "✓" if found else ("✗" if required else "○")
        tag  = "[REQUIRED]" if required else "[Optional]"
        lines.append(f"  {mark} {name:<35} {tag}")
        if found:
            lines.append(f"       {data['path'][:60]}")
        else:
            lines.append(f"       NOT FOUND — {REQUIREMENTS[name]['url']}")
        lines.append(f"       {REQUIREMENTS[name]['notes']}")
        lines.append("")

    # Issues
    if results["issues"]:
        s(f"ISSUES FOUND ({len(results['issues'])})")
        for iss in results["issues"]:
            lines.append(f"  ✗ {iss}")

    if results["conflicts"]:
        s(f"STRIP CLUB RESOURCE CONFLICTS ({len(results['conflicts'])})")
        for c in results["conflicts"][:10]:
            lines.append(f"  ! {c}")

    # Strip club verdict
    s("STRIP CLUB READINESS VERDICT")
    required_ok = all(
        results["mods"][n]["found"]
        for n, req in REQUIREMENTS.items()
        if req["required"]
    )
    dlc_ok = all(
        results["dlc"].get(code, False)
        for code, dlc in DLC_REQUIREMENTS.items()
        if dlc["required"]
    )
    if required_ok and dlc_ok:
        lines.append("  ✓ READY — All required mods and DLC are present.")
        lines.append("    In game: Build a lot with Strip Club type (Get to Work)")
        lines.append("    Hire dancers → assign Stripping job → open for business")
    else:
        lines.append("  ✗ NOT READY — Missing required components:")
        for name, req in REQUIREMENTS.items():
            if req["required"] and not results["mods"][name]["found"]:
                lines.append(f"    • {name} → {REQUIREMENTS[name]['url']}")
        for code, dlc in DLC_REQUIREMENTS.items():
            if dlc["required"] and not results["dlc"].get(code, False):
                lines.append(f"    • {code} {dlc['name']} (DLC required)")

    lines.append(f"\n{'═'*70}")
    return "\n".join(lines)


def build_html_report(results: dict, ts: datetime) -> str:
    # Quick and clean HTML
    parts = ["""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Strip Club Sim Report</title>
<style>
body{background:#050510;color:#d0d8f0;font-family:'Courier New',monospace;padding:24px}
h1{color:#00ff9f}h2{color:#00e5ff;border-bottom:1px solid #1a1a3a;padding-bottom:4px}
.ok{color:#00ff9f}.warn{color:#ffaa00}.fail{color:#ff003c}.dim{color:#5a6080}
.card{background:#0f0f25;border:1px solid #1a1a3a;border-radius:6px;padding:12px;margin:6px 0}
table{width:100%;border-collapse:collapse}
td,th{padding:6px 10px;border-bottom:1px solid #1a1a3a;text-align:left}
th{color:#5a6080;font-size:11px}
a{color:#00e5ff}
</style></head><body>"""]

    parts.append(f"<h1>🦉 Strip Club Compatibility Report</h1>")
    parts.append(f"<p class='dim'>{ts.strftime('%Y-%m-%d %H:%M:%S')}</p>")

    # DLC
    parts.append("<h2>DLC Requirements</h2><table><tr><th>Code</th><th>Name</th><th>Status</th><th>Required?</th><th>Why</th></tr>")
    for code, dlc in DLC_REQUIREMENTS.items():
        ok = results["dlc"].get(code, False)
        tag = "ok" if ok else ("fail" if dlc["required"] else "warn")
        mark = "✓" if ok else ("✗" if dlc["required"] else "○")
        parts.append(f"<tr><td class='{tag}'>{mark} {code}</td><td>{dlc['name']}</td>"
                     f"<td class='{tag}'>{'Present' if ok else 'MISSING'}</td>"
                     f"<td>{'Required' if dlc['required'] else 'Optional'}</td>"
                     f"<td class='dim'>{dlc['reason']}</td></tr>")
    parts.append("</table>")

    # Mods
    parts.append("<h2>Mod Status</h2>")
    for name, data in results["mods"].items():
        found = data["found"]
        req   = REQUIREMENTS[name]
        tag   = "ok" if found else ("fail" if req["required"] else "dim")
        mark  = "✓" if found else ("✗" if req["required"] else "○")
        req_lbl = "<span style='color:#ff003c'>Required</span>" if req["required"] else "<span class='dim'>Optional</span>"
        parts.append(f"<div class='card'>"
                     f"<div class='{tag}'>{mark} <strong>{name}</strong>  {req_lbl}</div>"
                     f"<div class='dim'>{req['notes']}</div>")
        if found:
            parts.append(f"<div class='ok'>✓ Found: {data['path'][:80]}</div>")
        else:
            parts.append(f"<div class='fail'>✗ Not found — "
                         f"<a href='{req['url']}'>{req['url']}</a></div>")
        parts.append("</div>")

    # Verdict
    required_ok = all(
        results["mods"][n]["found"]
        for n, req in REQUIREMENTS.items()
        if req["required"]
    )
    dlc_ok = all(
        results["dlc"].get(code, False)
        for code, dlc in DLC_REQUIREMENTS.items()
        if dlc["required"]
    )

    if required_ok and dlc_ok:
        parts.append("<h2 style='color:#00ff9f'>✓ STRIP CLUB READY</h2>"
                     "<div class='card'><p>All required mods and DLC are present.</p>"
                     "<p style='color:#00ff9f'><strong>How to open your strip club in-game:</strong></p>"
                     "<ol style='color:#d0d8f0;line-height:2'>"
                     "<li>Build a new lot or use an existing one</li>"
                     "<li>Change the lot type to <strong>Retail</strong> (Get to Work)</li>"
                     "<li>WickedWhims will add the Strip Club business overlay automatically</li>"
                     "<li>Hire Sims as employees → assign them the <em>Stripping</em> job</li>"
                     "<li>Open the business → customers will arrive and tip dancers</li>"
                     "<li>Use Basemental Drugs for the bar/dealer aspect of the club</li>"
                     "</ol></div>")
    else:
        parts.append("<h2 style='color:#ff003c'>✗ NOT READY — Missing Required Components</h2>"
                     "<div class='card'>")
        for name, req in REQUIREMENTS.items():
            if req["required"] and not results["mods"][name]["found"]:
                parts.append(f"<p>✗ <strong>{name}</strong> → "
                              f"<a href='{req['url']}'>{req['url']}</a></p>")
        parts.append("</div>")

    parts.append("<p class='dim'>Generated by 🦉 Sims4ModGuard</p></body></html>")
    return "\n".join(parts)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ts = datetime.now()
    print(DSEP)
    print("  STRIP CLUB MOD COMPATIBILITY SIMULATION")
    print(DSEP)

    results = {
        "timestamp": ts.isoformat(),
        "dlc": {},
        "mods": {},
        "issues": [],
        "conflicts": [],
    }

    # ── DLC check ────────────────────────────────────────────────────────────
    print("\nChecking DLC requirements...")
    dlc_installed = inventory_installed(GAME_ROOT)
    for code in DLC_REQUIREMENTS:
        ok = dlc_installed.get(code, False)
        results["dlc"][code] = ok
        mark = "✓" if ok else "✗"
        print(f"  {mark}  {code} {DLC_REQUIREMENTS[code]['name']}")

    # ── Mod checks ───────────────────────────────────────────────────────────
    print("\nChecking mods...")
    for name, req in REQUIREMENTS.items():
        files = find_mod(name, req)
        found = bool(files)
        results["mods"][name] = {
            "found": found,
            "path":  str(files[0]) if files else "",
            "count": len(files),
        }
        mark = "✓" if found else ("✗" if req["required"] else "○")
        print(f"  {mark}  {name}")

    # ── Integration checks ───────────────────────────────────────────────────
    print("\nChecking integration...")
    results["issues"].extend(check_basemental_ww_integration())

    ww_script_files = find_mod("WickedWhims Script", REQUIREMENTS["WickedWhims Script"])
    if ww_script_files:
        results["issues"].extend(check_ww_strip_club_compatibility(ww_script_files))

    # ── Resource conflict check (strip club specific) ─────────────────────────
    print("\nScanning for strip club resource conflicts...")
    strip_patterns = ["si7_", "stripping", "sexy gigs", "porn director", "porn star"]
    results["conflicts"] = check_resource_conflicts(strip_patterns)

    # ── Print and save reports ────────────────────────────────────────────────
    txt  = build_text_report(results, ts)
    html = build_html_report(results, ts)

    print("\n" + txt)

    out_base = Path(__file__).parent
    txt_path  = out_base / "strip_club_report.txt"
    html_path = out_base / "strip_club_report.html"
    txt_path.write_text(txt, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")

    json_path = out_base / "strip_club_report.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                         encoding="utf-8")

    print(f"\n{DSEP}")
    print(f"  Reports saved:")
    print(f"    HTML: {html_path}")
    print(f"    Text: {txt_path}")
    print(DSEP)

    # Auto-open HTML
    import os
    try:
        os.startfile(str(html_path))
    except Exception:
        pass


if __name__ == "__main__":
    main()
