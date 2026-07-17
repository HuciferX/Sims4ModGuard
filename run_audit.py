"""
run_audit.py
CLI runner: full boot simulation + HTML/text audit log.

Usage:
  python run_audit.py               # run and auto-open HTML report
  python run_audit.py --no-open     # run but don't open browser
"""
import sys
import os
import subprocess
from pathlib import Path
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from sims4modguard.game_index  import GameIndex, DEFAULT_GAME_ROOT
from sims4modguard.boot_engine import BootEngine, SEV_CRITICAL, SEV_WARNING
from sims4modguard.run_logger  import RunLogger

S4_FOLDER  = Path(r"C:\Users\merli\Documents\Electronic Arts\The Sims 4")
GAME_ROOT  = DEFAULT_GAME_ROOT

SEP  = "-" * 72
DSEP = "=" * 72


def run(open_html: bool = True):
    ts_start = datetime.now()
    print(DSEP)
    print("  SIMS4 MOD GUARDIAN  \u2014  FULL BOOT AUDIT")
    print(f"  {ts_start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(DSEP)

    # ── Build game index ──────────────────────────────────────────────────
    print("\n[1/2]  Loading game index ...")
    idx = GameIndex(GAME_ROOT)
    idx.ensure_loaded(progress_cb=lambda m: print(f"       {m}"))
    print(f"       Modules  : {idx.module_count:,}")
    print(f"       Resources: {idx.resource_count:,}")

    # ── Run simulation ────────────────────────────────────────────────────
    print(f"\n[2/2]  Running 7-phase boot simulation ...")
    print(f"       Mods: {S4_FOLDER / 'Mods'}\n")

    last_phase = [None]

    def cb(phase, pct, msg, sev="INFO"):
        if phase != last_phase[0]:
            print(f"\n  \u2500\u2500 PHASE: {phase} \u2500\u2500")
            last_phase[0] = phase
        tag = {"CRITICAL": "[!!]", "WARNING": "[!] ", "OK": "[OK]", "INFO": "    "}.get(sev, "    ")
        bar  = int(pct * 20)
        pbar = f"[{'#'*bar}{'.'*(20-bar)}] {int(pct*100):3d}%"
        print(f"  {tag} {pbar}  {msg[:68]}")

    engine = BootEngine(S4_FOLDER, GAME_ROOT, game_index=idx)
    report = engine.run(progress_cb=cb)

    # ── Surface any internal phase crashes ────────────────────────────────
    print(f"\n")
    any_internal = False
    for ph in report.phases:
        for iss in ph.issues:
            if iss.phase == "INTERNAL":
                if not any_internal:
                    print(f"{SEP}")
                    print(f"  INTERNAL ERRORS (phase code crashed \u2014 these are bugs)")
                    print(SEP)
                    any_internal = True
                print(f"  [{ph.name}] {iss.message}")
                print(f"     {iss.detail[:120]}")

    # ── Verdict ───────────────────────────────────────────────────────────
    print(f"\n{DSEP}")
    print(f"  VERDICT:  {report.verdict_label}   ({report.crash_probability}% crash probability)")
    print(f"  Critical: {report.critical_count}   Warnings: {report.warning_count}")
    print(DSEP)

    # ── Phase summary ─────────────────────────────────────────────────────
    print("\nPHASE SUMMARY:")
    print(f"  {'Phase':<22} {'Status':<12} {'Issues':>7}  Key stat")
    print(f"  {'-'*22} {'-'*12} {'-'*7}  {'-'*28}")
    for ph in report.phases:
        from sims4modguard.run_logger import _phase_key_stat
        print(f"  {ph.name:<22} {ph.status:<12} {len(ph.issues):>7}  {_phase_key_stat(ph)}")

    # ── Critical issues ───────────────────────────────────────────────────
    criticals = [i for i in report.all_issues if i.severity == SEV_CRITICAL]
    if criticals:
        print(f"\n{SEP}")
        print(f"  CRITICAL ISSUES ({len(criticals)}) \u2014 these WILL cause crashes")
        print(SEP)
        by_file = defaultdict(list)
        for issue in criticals:
            by_file[issue.file.split("::")[0]].append(issue)
        for fname, issues in sorted(by_file.items(), key=lambda x: -len(x[1])):
            short = Path(fname).name if len(fname) > 60 else fname
            print(f"\n  FILE: {short}")
            seen = set()
            for iss in issues:
                if iss.message not in seen:
                    seen.add(iss.message)
                    print(f"    [!!] {iss.message}")
                    if iss.fix:
                        print(f"         FIX: {iss.fix}")
    else:
        print(f"\n  \u2713 No critical issues found.")

    # ── Warnings (top 40) ─────────────────────────────────────────────────
    warnings = [i for i in report.all_issues if i.severity == SEV_WARNING]
    if warnings:
        print(f"\n{SEP}")
        print(f"  WARNINGS ({len(warnings)}) \u2014 top 40 shown")
        print(SEP)
        by_file_w = defaultdict(list)
        for w in warnings:
            by_file_w[w.file.split("::")[0]].append(w)
        shown = 0
        for fname, issues in sorted(by_file_w.items(), key=lambda x: -len(x[1])):
            if shown >= 40:
                print(f"\n  ... and {len(by_file_w) - shown} more files with warnings")
                break
            short = Path(fname).name if len(fname) > 60 else fname
            print(f"\n  FILE: {short}")
            seen = set()
            for iss in issues[:3]:
                if iss.message not in seen:
                    seen.add(iss.message)
                    print(f"    [!]  {iss.message}")
            shown += 1

    # ── Stats ─────────────────────────────────────────────────────────────
    print(f"\n{DSEP}")
    print(f"  STATS")
    print(DSEP)
    print(f"  Total scripts    : {report.total_scripts:,}")
    print(f"  Total packages   : {report.total_packages:,}")
    print(f"  Depth violations : {report.total_depth_violations:,}")
    for ph in report.phases:
        for k, v in ph.stats.items():
            if isinstance(v, (int, float)) and k not in ("installed_map",):
                val = f"{v:,}" if isinstance(v, int) else str(v)
                print(f"  {ph.name}/{k:<32}: {val}")

    # ── Duplicate CC files ───────────────────────────────────────────────────
    if report.dup_file_pairs:
        near_dups  = [d for d in report.dup_file_pairs if d.is_near_duplicate]
        minor_dups = [d for d in report.dup_file_pairs if not d.is_near_duplicate]
        print(f"\n{SEP}")
        print(f"  DUPLICATE CC FILES  ({len(report.dup_file_pairs)} pairs, "
              f"{len(near_dups)} near-exact)")
        print(SEP)
        print(f"  Near-exact (≥50 shared IDs): same CC installed twice — quarantine the REMOVE file.")
        print(f"  Minor overlap (<50 shared IDs): different CC packs sharing a few resources.")

        if near_dups:
            print(f"\n  NEAR-EXACT DUPLICATES — top {min(20, len(near_dups))} of {len(near_dups)}:")
            print(f"  {'#':<4} {'Shared':>7}  {'Type':<18}  {'Date':^10}  Action")
            print(f"  {'-'*4} {'-'*7}  {'-'*18}  {'-'*10}  {'-'*50}")
            for rank, dup in enumerate(near_dups[:20], 1):
                remove_name = Path(dup.remove_path).name
                keep_name   = dup.name_a if dup.remove_path == dup.file_b else dup.name_b
                date_str    = f"{dup.date_a}/{dup.date_b}"
                print(f"  {rank:<4} {dup.shared_ids:>7,}  {dup.dominant_type:<18}  {date_str:<10}  "
                      f"REMOVE: {remove_name[:50]}")
                print(f"       KEEP:   {keep_name[:60]}")
                print(f"       WHY:    {dup.recommendation}")
                print()
            if len(near_dups) > 20:
                print(f"  ... {len(near_dups)-20} more in HTML report.")

        if minor_dups:
            print(f"\n  MINOR OVERLAPS — top {min(10, len(minor_dups))} of {len(minor_dups)}:")
            print(f"  {'#':<4} {'Shared':>7}  {'Type':<18}  File A  vs  File B")
            print(f"  {'-'*4} {'-'*7}  {'-'*18}  {'-'*60}")
            for rank, dup in enumerate(minor_dups[:10], 1):
                print(f"  {rank:<4} {dup.shared_ids:>7,}  {dup.dominant_type:<18}  "
                      f"{dup.name_a[:28]}  vs  {dup.name_b[:28]}")

    # ── Save HTML + text logs ─────────────────────────────────────────────
    elapsed = (datetime.now() - ts_start).seconds
    label   = f"Scan duration: {elapsed//60}m {elapsed%60}s"
    logger  = RunLogger()
    html_path, txt_path = logger.save(report, quarantined=[], label=label)

    print(f"\n{DSEP}")
    print(f"  LOGS SAVED")
    print(DSEP)
    print(f"  HTML report : {html_path}")
    print(f"  Text report : {txt_path}")
    print(f"  Log history : {logger.log_dir}  ({len(logger.list_logs())} runs saved)")
    print(DSEP)

    # ── Auto-open HTML in browser ─────────────────────────────────────────
    if open_html and html_path.exists():
        try:
            os.startfile(str(html_path))   # Windows
        except Exception:
            try:
                subprocess.Popen(["start", str(html_path)], shell=True)
            except Exception:
                pass
        print(f"\n  Opening report in browser...")


if __name__ == "__main__":
    no_open = "--no-open" in sys.argv
    run(open_html=not no_open)
