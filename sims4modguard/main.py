"""
Sims4ModGuard — main.py
Full mod compatibility scanner and cleaner for Sims 4 patch 1.121+.

Usage:
  python -m sims4modguard               # auto-detect, interactive
  python -m sims4modguard --scan-only   # scan and report, no changes
  python -m sims4modguard --fix         # scan and auto-quarantine critical issues
  python -m sims4modguard --clear-cache # clear caches only
  python -m sims4modguard --restore     # restore all quarantined files
  python -m sims4modguard --cc-scan     # run CC package scan (slower)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .cache_manager  import find_s4_folder, read_game_version, get_cache_state, clear_caches
from .scanner        import scan_all_scripts, SEVERITY_CRITICAL
from .cc_cleaner     import scan_all_packages
from .log_parser     import parse_log
from .quarantine     import QuarantineManager

BANNER = """
╔══════════════════════════════════════════════════════╗
║         Sims4ModGuard  v1.0  (patch 1.121+)          ║
║  Automated mod scanner, cleaner & conflict detector  ║
╚══════════════════════════════════════════════════════╝
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _yn(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        ans = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not ans:
        return default
    return ans.startswith("y")


def _section(title: str):
    width = 54
    print(f"\n{'─' * width}")
    print(f"  {title}")
    print(f"{'─' * width}")


# ── Display helpers ───────────────────────────────────────────────────────────

def _print_script_results(results):
    critical = [r for r in results if r.severity == SEVERITY_CRITICAL]
    clean    = [r for r in results if r.is_clean]
    ww_dep   = [r for r in results if any(i.ww_dep for i in r.issues)]
    patchable = [r for r in critical if any(i.patchable for i in r.issues)]

    print(f"\n  Total scripts scanned : {len(results)}")
    print(f"  Clean                 : {len(clean)}")
    print(f"  Critical (will break) : {len(critical)}")
    print(f"    WickedWhims deps    : {len(ww_dep)}")
    print(f"    Patchable (.py src) : {len(patchable)}")
    print(f"    Pyc-only (no fix)   : {len([r for r in critical if r.pyc_only])}")

    if critical:
        print(f"\n  Critical scripts:")
        for r in critical:
            ww = " [WW-dep]" if any(i.ww_dep for i in r.issues) else ""
            p  = " [patchable?]" if any(i.patchable for i in r.issues) else ""
            print(f"    ✗ {r.name}{ww}{p}")
            for issue in r.issues[:2]:
                print(f"        {issue.message}")


def _print_cc_summary(cc_data):
    s = cc_data["summary"]
    print(f"\n  Total packages scanned  : {s['total']:,}")
    print(f"  Corrupt (invalid DBPF)  : {s['corrupt']}")
    print(f"  Duplicate filenames     : {s['duplicate_names']}")
    print(f"  Identical content dups  : {s['duplicate_hashes']}")
    print(f"  Tuning conflict suspects: {s['tuning_conflicts']}")
    print(f"  WW animation packages   : {s['ww_packages']}")
    print(f"  With any issues         : {s['with_issues']}")
    print(f"  Fully clean             : {s['clean']:,}")

    if cc_data["corrupt"]:
        print(f"\n  Corrupt packages:")
        for r in cc_data["corrupt"][:10]:
            print(f"    ✗ {r.name}")

    if cc_data["tuning_conflicts"]:
        print(f"\n  Tuning conflict suspects (check if EA objects are broken):")
        for r in cc_data["tuning_conflicts"][:10]:
            print(f"    ⚠ {r.name}  ({r.file_size//1024} KB)")

    if cc_data["duplicate_names"]:
        print(f"\n  Duplicate filenames (only 1 will load):")
        for name, paths in list(cc_data["duplicate_names"].items())[:5]:
            print(f"    ⚠ {name}  ({len(paths)} copies)")


def _print_log_summary(log_summary):
    print(f"\n  Game version : {log_summary.game_version}")
    print(f"  Total errors : {log_summary.total_errors}")
    if not log_summary.tuning_finished:
        print(f"  ⚠  Tuning load FAILED — this caused the crash")

    if log_summary.grouped:
        print(f"\n  Error categories:")
        for cat, errors in log_summary.grouped.items():
            total_count = sum(e.count for e in errors)
            print(f"    {cat}: {total_count} occurrences across {len(errors)} unique errors")

    if log_summary.root_causes:
        print(f"\n  Top root causes:")
        for err in log_summary.root_causes[:5]:
            ct = f" (×{err.count})" if err.count > 1 else ""
            print(f"    • {err.description[:90]}{ct}")
            if err.explanation:
                print(f"      → {err.explanation}")


# ── Fix actions ───────────────────────────────────────────────────────────────

def _auto_quarantine_scripts(results, qm: QuarantineManager) -> int:
    """Quarantine all critical scripts. Returns count moved."""
    to_quarantine = []
    for r in results:
        if r.severity != SEVERITY_CRITICAL:
            continue
        for issue in r.issues:
            reason = issue.message
            if issue.detail:
                reason += f" — {issue.detail[:100]}"
            to_quarantine.append((r.path, reason))
            break  # one reason per file

    if not to_quarantine:
        print("  Nothing to quarantine.")
        return 0

    result = qm.quarantine_many(to_quarantine, auto=True)
    moved = len(result["success"])
    failed = len(result["failed"])
    print(f"  Quarantined: {moved} scripts")
    if failed:
        print(f"  Failed:      {failed} (check permissions)")
    return moved


def _quarantine_corrupt_packages(cc_data, qm: QuarantineManager) -> int:
    """Quarantine corrupt CC packages."""
    to_q = [(r.path, "Corrupt DBPF header — not a valid .package file")
            for r in cc_data["corrupt"]]
    if not to_q:
        return 0
    result = qm.quarantine_many(to_q, auto=True)
    n = len(result["success"])
    print(f"  Quarantined: {n} corrupt packages")
    return n


# ── Main ──────────────────────────────────────────────────────────────────────

def run(args):
    print(BANNER)

    # 1. Find Sims 4 folder
    s4 = find_s4_folder()
    if not s4:
        print("ERROR: Could not find Sims 4 data folder.")
        print("  Expected: Documents/Electronic Arts/The Sims 4")
        sys.exit(1)

    mods = s4 / "Mods"
    version = read_game_version(s4)
    cache_state = get_cache_state(s4)

    print(f"  Sims 4 folder : {s4}")
    print(f"  Game version  : {version}")
    print(f"  Mods folder   : {mods}")

    scripts_count  = sum(1 for _ in mods.rglob("*.ts4script") if "MODS_DISABLED" not in str(_))
    packages_count = sum(1 for _ in mods.rglob("*.package")   if "MODS_DISABLED" not in str(_))
    disabled_count = sum(1 for _ in (s4 / "MODS_DISABLED").rglob("*") if _.is_file()) if (s4 / "MODS_DISABLED").exists() else 0

    print(f"  Active scripts  : {scripts_count}")
    print(f"  Active packages : {packages_count:,}")
    print(f"  Disabled files  : {disabled_count}")
    print(f"  Thumb cache     : {cache_state['thumbnail_cache_mb']} MB")

    qm = QuarantineManager(s4)

    # ── Handle --restore ─────────────────────────────────────────────────────
    if args.restore:
        _section("RESTORE QUARANTINED FILES")
        active = qm.get_quarantined()
        if not active:
            print("  No quarantined files to restore.")
        else:
            print(f"  {len(active)} quarantined files found.")
            qm.print_manifest()
            if _yn("\nRestore ALL quarantined files?"):
                for e in active:
                    qm.restore(e["destination"])
                print("Done. Clear caches and relaunch the game.")
        return

    # ── Handle --clear-cache ─────────────────────────────────────────────────
    if args.clear_cache:
        _section("CLEARING CACHES")
        clear_caches(s4)
        return

    # ── Log parsing ──────────────────────────────────────────────────────────
    _section("PARSING LAST EXCEPTION LOG")
    log_summary = parse_log(s4 / "lastException.txt")
    _print_log_summary(log_summary)

    # ── Script scan ──────────────────────────────────────────────────────────
    _section("SCANNING SCRIPT MODS (.ts4script)")
    print("  Scanning scripts...", flush=True)
    script_results = scan_all_scripts(mods)
    _print_script_results(script_results)

    critical_scripts = [r for r in script_results if r.severity == SEVERITY_CRITICAL]

    # ── CC scan (optional — slow on 10k+ files) ───────────────────────────────
    cc_data = None
    if args.cc_scan or args.full:
        _section("SCANNING CC PACKAGES (.package)")
        cc_data = scan_all_packages(mods)
        _print_cc_summary(cc_data)

    # ── Summary ──────────────────────────────────────────────────────────────
    _section("SUMMARY")
    print(f"  Critical scripts       : {len(critical_scripts)}")
    if cc_data:
        print(f"  Corrupt packages       : {cc_data['summary']['corrupt']}")
        print(f"  Duplicate package names: {cc_data['summary']['duplicate_names']}")
        print(f"  Tuning conflict suspects: {cc_data['summary']['tuning_conflicts']}")

    if args.scan_only:
        print("\n  [Scan-only mode — no changes made]")
        return

    # ── Fix prompt ────────────────────────────────────────────────────────────
    _section("FIX OPTIONS")

    total_fixable = len(critical_scripts)
    if total_fixable == 0 and (not cc_data or cc_data["summary"]["corrupt"] == 0):
        print("  Everything looks clean! No automatic fixes needed.")
    else:
        if critical_scripts:
            print(f"\n  {len(critical_scripts)} broken scripts found.")
            do_scripts = args.fix or _yn("  Quarantine all broken scripts?", default=True)
            if do_scripts:
                moved = _auto_quarantine_scripts(script_results, qm)
                if moved > 0:
                    print(f"  → {moved} scripts moved to MODS_DISABLED/")

        if cc_data and cc_data["corrupt"]:
            print(f"\n  {cc_data['summary']['corrupt']} corrupt packages found.")
            do_cc = args.fix or _yn("  Quarantine corrupt packages?", default=True)
            if do_cc:
                _quarantine_corrupt_packages(cc_data, qm)

    # ── Cache clear ───────────────────────────────────────────────────────────
    _section("CACHE")
    do_cache = args.fix or _yn("Clear Sims 4 caches?", default=True)
    if do_cache:
        clear_caches(s4)

    # ── Save report ───────────────────────────────────────────────────────────
    report_path = s4 / "Sims4ModGuard_Report.txt"
    _write_text_report(report_path, version, script_results, cc_data, log_summary, qm)
    print(f"\n  Full report saved: {report_path}")
    print("\n  Done. Relaunch the game and check if it loads cleanly.")


def _write_text_report(path: Path, version: str, script_results, cc_data, log_summary, qm):
    lines = [
        f"Sims4ModGuard Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Game version: {version}",
        "=" * 60,
        "",
        "SCRIPT SCAN RESULTS",
        "─" * 40,
    ]
    for r in script_results:
        if r.issues:
            lines.append(f"  [{r.severity or 'OK'}] {r.name}")
            for iss in r.issues:
                lines.append(f"    • {iss.message}")
                if iss.detail:
                    lines.append(f"      {iss.detail[:120]}")

    if cc_data:
        lines += ["", "CC PACKAGE SCAN RESULTS", "─" * 40]
        s = cc_data["summary"]
        lines.append(f"  Total: {s['total']:,}  Corrupt: {s['corrupt']}  "
                     f"Dup-names: {s['duplicate_names']}  "
                     f"Tuning-conflicts: {s['tuning_conflicts']}")
        for r in cc_data["corrupt"]:
            lines.append(f"  [CORRUPT] {r.name}")
        for r in cc_data["tuning_conflicts"]:
            lines.append(f"  [TUNING?] {r.name}")

    lines += ["", "LOG SUMMARY", "─" * 40]
    lines.append(log_summary.plain_summary)

    lines += ["", "QUARANTINE MANIFEST", "─" * 40]
    for e in qm.get_quarantined():
        lines.append(f"  {e['name']}")
        lines.append(f"    {e['reason'][:100]}")

    path.write_text("\n".join(lines), encoding="utf-8")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="sims4modguard",
        description="Sims 4 mod compatibility scanner for patch 1.121+",
    )
    parser.add_argument("--scan-only",   action="store_true", help="Scan and report only, no changes")
    parser.add_argument("--fix",         action="store_true", help="Auto-quarantine all critical issues")
    parser.add_argument("--cc-scan",     action="store_true", help="Include CC package scan (slower)")
    parser.add_argument("--full",        action="store_true", help="Full scan: scripts + CC packages")
    parser.add_argument("--clear-cache", action="store_true", help="Clear Sims 4 caches only")
    parser.add_argument("--restore",     action="store_true", help="Restore all quarantined files")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
