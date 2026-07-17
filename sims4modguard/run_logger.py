"""
run_logger.py
Saves every Sims4ModGuard audit run as a timestamped HTML + text log.

Each log explains:
  - What was scanned and when
  - Every issue found, severity, and WHY it's a problem
  - What was quarantined (if anything) and why that helps
  - Stats comparison vs previous run (if a previous log exists)

Logs are saved to: <app_dir>/logs/
Named:             audit_YYYY-MM-DD_HH-MM-SS.html  +  .txt
The 20 most recent are kept; older ones are archived to logs/archive/.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from .boot_engine import BootReport, BootIssue, PhaseResult, DuplicateFilePair

# ── Log directory ─────────────────────────────────────────────────────────────
APP_DIR  = Path(__file__).parent.parent
LOG_DIR  = APP_DIR / "logs"
ARC_DIR  = LOG_DIR / "archive"
MAX_LOGS = 20

# ── Severity colors ───────────────────────────────────────────────────────────
SEV_HTML_COLOR = {
    "CRITICAL": "#ff003c",
    "WARNING":  "#ffaa00",
    "INFO":     "#00e5ff",
    "OK":       "#00ff9f",
}

STATUS_HTML_COLOR = {
    "PASS":    "#00ff9f",
    "WARN":    "#ffaa00",
    "FAIL":    "#ff003c",
    "SKIP":    "#5a6080",
    "PENDING": "#5a6080",
}

# ── Plain-English explanations for common issue categories ────────────────────
WHY_EXPLANATIONS = {
    "removed_api":
        "EA deleted this Python function in a game update. "
        "When the game loads this mod, Python raises an AttributeError "
        "and the game crashes before the main menu.",
    "broken_inject":
        "This mod uses an old injection technique that EA changed. "
        "The game now passes an extra 'manager' argument that old mods "
        "don't expect, causing a TypeError crash on load.",
    "corrupt":
        "The mod file cannot be opened as a ZIP archive. "
        "The game will silently skip it, but corrupt files can also "
        "slow down loading and cause cache issues.",
    "known_dead":
        "This mod is confirmed broken on the current game patch. "
        "It has not been updated by its author and will not work.",
    "ww_dependency":
        "This mod requires WickedWhims core to be installed. "
        "Without WW, Python raises an ImportError on load.",
    "depth_violation":
        "The Sims 4 only loads mods up to 5 subfolder levels deep. "
        "This file is buried too deep and will be completely ignored "
        "by the game — it simply won't load at all.",
    "resource_conflict":
        "Two mods are trying to override the same game resource. "
        "The last one loaded wins, but behavior is unpredictable and "
        "can cause crashes or broken gameplay.",
    "tuning_conflict":
        "This package overrides bed/seat posture or object reservation "
        "tuning that EA changed in patch 1.121. The game expects a "
        "different format and will raise an exception when loading the lot.",
}

def _why(issue: BootIssue) -> str:
    """Return a plain-English explanation for this issue."""
    # Match by category keyword in message
    msg_lower = issue.message.lower()
    for key, text in WHY_EXPLANATIONS.items():
        if key.replace("_", " ") in msg_lower or key in msg_lower:
            return text
    if issue.detail:
        return issue.detail
    return "This file caused an error during the boot simulation."


# ── HTML template ─────────────────────────────────────────────────────────────

_HTML_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sims4ModGuard Audit — {timestamp}</title>
<style>
  :root {{
    --bg:      #050510;
    --panel:   #0a0a1a;
    --card:    #0f0f25;
    --header:  #070718;
    --green:   #00ff9f;
    --cyan:    #00e5ff;
    --amber:   #ffaa00;
    --red:     #ff003c;
    --pink:    #ff00dd;
    --purple:  #9d00ff;
    --dim:     #5a6080;
    --text:    #d0d8f0;
    --white:   #ffffff;
    --mono:    "Courier New", Courier, monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--mono);
    font-size: 13px;
    line-height: 1.6;
    padding: 24px;
  }}
  h1 {{ color: var(--green); font-size: 22px; margin-bottom: 4px; }}
  h2 {{ color: var(--cyan);  font-size: 15px; margin: 24px 0 8px; border-bottom: 1px solid #1a1a3a; padding-bottom: 4px; }}
  h3 {{ color: var(--amber); font-size: 13px; margin: 12px 0 4px; }}
  a  {{ color: var(--cyan);  text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  .verdict-box {{
    border: 2px solid {verdict_color};
    border-radius: 8px;
    padding: 16px 24px;
    margin: 16px 0;
    background: {verdict_bg};
    display: flex;
    align-items: center;
    gap: 24px;
  }}
  .verdict-label {{
    font-size: 26px;
    font-weight: bold;
    color: {verdict_color};
  }}
  .verdict-prob {{
    font-size: 18px;
    color: {verdict_color};
  }}
  .verdict-counts {{
    font-size: 13px;
    color: var(--dim);
  }}

  .nav {{
    background: var(--panel);
    border: 1px solid #1a1a3a;
    border-radius: 6px;
    padding: 10px 16px;
    margin-bottom: 24px;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }}

  .phase-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0;
  }}
  .phase-table th, .phase-table td {{
    padding: 6px 12px;
    text-align: left;
    border-bottom: 1px solid #1a1a3a;
  }}
  .phase-table th {{ color: var(--dim); font-size: 11px; text-transform: uppercase; }}

  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
  }}

  .issue-card {{
    background: var(--card);
    border-left: 3px solid var(--dim);
    border-radius: 0 4px 4px 0;
    padding: 10px 14px;
    margin: 6px 0;
  }}
  .issue-card.critical {{ border-left-color: var(--red); }}
  .issue-card.warning  {{ border-left-color: var(--amber); }}
  .issue-card.info     {{ border-left-color: var(--cyan); }}

  .issue-file  {{ color: var(--cyan); font-size: 12px; margin-bottom: 4px; }}
  .issue-msg   {{ color: var(--white); font-weight: bold; margin-bottom: 4px; }}
  .issue-why   {{ color: var(--dim); font-size: 11px; margin-bottom: 4px; }}
  .issue-fix   {{ color: var(--green); font-size: 11px; }}
  .issue-fix::before {{ content: "✓ FIX: "; }}

  .stat-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px;
    margin: 10px 0;
  }}
  .stat-card {{
    background: var(--card);
    border: 1px solid #1a1a3a;
    border-radius: 6px;
    padding: 10px 14px;
  }}
  .stat-label {{ color: var(--dim); font-size: 10px; text-transform: uppercase; }}
  .stat-value {{ color: var(--cyan); font-size: 20px; font-weight: bold; }}

  .quarantine-item {{
    background: var(--card);
    border-left: 3px solid var(--amber);
    padding: 8px 12px;
    margin: 4px 0;
    border-radius: 0 4px 4px 0;
  }}
  .qt-file  {{ color: var(--amber); }}
  .qt-why   {{ color: var(--dim); font-size: 11px; }}

  .clean-tag {{
    background: var(--card);
    border: 1px solid var(--green);
    border-radius: 6px;
    padding: 16px;
    color: var(--green);
    font-size: 15px;
    text-align: center;
    margin: 12px 0;
  }}

  .dup-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
    margin: 8px 0;
  }}
  .dup-table th {{
    color: var(--dim);
    text-align: left;
    padding: 4px 10px;
    border-bottom: 1px solid #1a1a3a;
    text-transform: uppercase;
    font-size: 10px;
  }}
  .dup-table td {{
    padding: 6px 10px;
    border-bottom: 1px solid #0d0d20;
    vertical-align: top;
  }}
  .dup-table tr:hover td {{ background: #0d0d28; }}
  .dup-near {{ color: var(--red); font-weight: bold; }}
  .dup-minor {{ color: var(--amber); }}
  .dup-file {{ color: var(--cyan); word-break: break-all; }}
  .dup-remove {{ color: var(--red); word-break: break-all; }}
  .dup-rec {{ color: var(--dim); font-size: 10px; }}

  footer {{
    margin-top: 48px;
    color: var(--dim);
    font-size: 11px;
    border-top: 1px solid #1a1a3a;
    padding-top: 12px;
  }}
</style>
</head>
<body>
"""

_HTML_FOOT = """
<footer>
  Generated by <strong>Sims4ModGuard</strong> by Hucifer &amp; 🦉 Hypatia &mdash;
  {timestamp} &mdash; Game patch {game_version}
</footer>
</body>
</html>
"""


# ── Core logger class ─────────────────────────────────────────────────────────

class RunLogger:
    """
    Saves every boot audit as a timestamped HTML + text log.
    Call save(report) after a BootEngine.run() completes.
    """

    def __init__(self, log_dir: Path = LOG_DIR):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        ARC_DIR.mkdir(parents=True, exist_ok=True)

    def save(self, report: BootReport,
             quarantined: Optional[list[dict]] = None,
             label: str = "") -> tuple[Path, Path]:
        """
        Save audit as HTML + text.
        quarantined: list of {"name": str, "reason": str} dicts (files moved)
        Returns (html_path, txt_path).
        """
        ts = datetime.now()
        stamp = ts.strftime("%Y-%m-%d_%H-%M-%S")
        base  = self.log_dir / f"audit_{stamp}"
        html_path = base.with_suffix(".html")
        txt_path  = base.with_suffix(".txt")

        html = self._build_html(report, quarantined or [], ts, label)
        txt  = self._build_txt(report, quarantined or [], ts, label)

        html_path.write_text(html, encoding="utf-8")
        txt_path.write_text(txt,  encoding="utf-8")

        self._rotate_logs()
        return html_path, txt_path

    # ── HTML builder ──────────────────────────────────────────────────────────

    def _build_html(self, report: BootReport, quarantined: list,
                    ts: datetime, label: str) -> str:
        timestamp    = ts.strftime("%Y-%m-%d %H:%M:%S")
        verdict_color = report.verdict_color
        verdict_bg    = _hex_tint(verdict_color, 0.06)
        crit = report.critical_count
        warn = report.warning_count

        criticals = [i for i in report.all_issues if i.severity == "CRITICAL"]
        warnings  = [i for i in report.all_issues if i.severity == "WARNING"]

        parts = []

        # Head
        parts.append(_HTML_HEAD.format(
            timestamp=timestamp,
            verdict_color=verdict_color,
            verdict_bg=verdict_bg,
        ))

        # Title + nav
        parts.append(f"<h1>🦉 Sims4ModGuard Audit Report</h1>")
        parts.append(f"<p style='color:var(--dim)'>{timestamp}"
                     + (f" &mdash; {label}" if label else "") + "</p>")

        parts.append("<div class='nav'>")
        parts.append("<a href='#verdict'>Verdict</a>")
        parts.append("<a href='#phases'>Phases</a>")
        if criticals:
            parts.append(f"<a href='#critical'>Critical ({len(criticals)})</a>")
        if warnings:
            parts.append(f"<a href='#warnings'>Warnings ({len(warnings)})</a>")
        if quarantined:
            parts.append(f"<a href='#quarantine'>Quarantined ({len(quarantined)})</a>")
        if report.dup_file_pairs:
            near = sum(1 for d in report.dup_file_pairs if d.is_near_duplicate)
            parts.append(f"<a href='#duplicates'>Duplicates ({len(report.dup_file_pairs)}, "
                         f"{near} near-exact)</a>")
        parts.append("<a href='#stats'>Stats</a>")
        parts.append("</div>")

        # Verdict box
        parts.append("<h2 id='verdict'>Verdict</h2>")
        depth_color = "var(--red)" if report.total_depth_violations else "var(--green)"
        parts.append(f"""
<div class='verdict-box'>
  <div>
    <div class='verdict-label'>{report.verdict_label}</div>
    <div class='verdict-prob'>{report.crash_probability}% crash probability</div>
  </div>
  <div class='verdict-counts'>
    Critical issues: <strong style='color:var(--red)'>{crit}</strong><br>
    Warnings:        <strong style='color:var(--amber)'>{warn}</strong><br>
    Scripts scanned: <strong>{report.total_scripts:,}</strong><br>
    Packages scanned:<strong>{report.total_packages:,}</strong><br>
    Depth violations:<strong style='color:{depth_color}'>{report.total_depth_violations}</strong>
  </div>
</div>""")

        # Phase summary
        parts.append("<h2 id='phases'>Phase-by-Phase Results</h2>")
        parts.append("<table class='phase-table'>")
        parts.append("<tr><th>#</th><th>Phase</th><th>Status</th>"
                     "<th>Issues Found</th><th>Key Stat</th></tr>")
        for i, ph in enumerate(report.phases, 1):
            color = STATUS_HTML_COLOR.get(ph.status, "#5a6080")
            key_stat = _phase_key_stat(ph)
            iss_color = "var(--red)" if ph.issues else "var(--dim)"
            parts.append(
                f"<tr>"
                f"<td style='color:var(--dim)'>{i}</td>"
                f"<td><strong>{ph.name}</strong></td>"
                f"<td><span class='badge' style='background:{_hex_tint(color,0.15)};color:{color}'>"
                f"{ph.status}</span></td>"
                f"<td style='color:{iss_color}'>{len(ph.issues)}</td>"
                f"<td style='color:var(--dim);font-size:11px'>{key_stat}</td>"
                f"</tr>")
        parts.append("</table>")

        # Critical issues
        if criticals:
            parts.append(f"<h2 id='critical' style='color:var(--red)'>"
                         f"⚠ Critical Issues ({len(criticals)}) — these WILL cause crashes</h2>")
            parts.append("<p style='color:var(--dim);font-size:11px;margin-bottom:12px'>"
                         "These mods will prevent the game from loading correctly. "
                         "Quarantine them before launching.</p>")
            for iss in criticals:
                why = _why(iss)
                parts.append(f"""
<div class='issue-card critical'>
  <div class='issue-file'>📄 {_esc(iss.file)}</div>
  <div class='issue-msg'>{_esc(iss.message)}</div>
  <div class='issue-why'><strong>Why this crashes:</strong> {_esc(why)}</div>
  {f"<div class='issue-fix'>{_esc(iss.fix)}</div>" if iss.fix else ""}
  <div style='color:var(--dim);font-size:10px;margin-top:4px'>Phase: {iss.phase}</div>
</div>""")
        else:
            parts.append("<h2 id='critical'>Critical Issues</h2>")
            parts.append("<div class='clean-tag'>✓ No critical issues found!</div>")

        # Warnings
        if warnings:
            parts.append(f"<h2 id='warnings' style='color:var(--amber)'>"
                         f"Warnings ({len(warnings)})</h2>")
            parts.append("<p style='color:var(--dim);font-size:11px;margin-bottom:12px'>"
                         "These mods have potential problems but may not crash the game immediately. "
                         "Review and update where possible.</p>")
            for iss in warnings:
                why = _why(iss)
                parts.append(f"""
<div class='issue-card warning'>
  <div class='issue-file'>📄 {_esc(iss.file)}</div>
  <div class='issue-msg'>{_esc(iss.message)}</div>
  <div class='issue-why'>{_esc(why)}</div>
  {f"<div class='issue-fix'>{_esc(iss.fix)}</div>" if iss.fix else ""}
</div>""")

        # Duplicate CC file pairs
        if report.dup_file_pairs:
            near_dups = [d for d in report.dup_file_pairs if d.is_near_duplicate]
            all_dups  = report.dup_file_pairs
            parts.append(f"<h2 id='duplicates' style='color:var(--pink)'>"
                         f"📦 Duplicate CC Files — {len(all_dups)} conflicting pairs "
                         f"({len(near_dups)} near-exact)</h2>")
            parts.append(
                "<p style='color:var(--dim);font-size:11px;margin-bottom:8px'>"
                "These file pairs share large numbers of the same resource IDs, "
                "meaning the same CC content is installed twice. "
                "The <strong style='color:var(--red)'>REMOVE</strong> column shows "
                "which file to quarantine (older or smaller). "
                "The game loads whichever is alphabetically last, so duplicates "
                "waste load time without adding content."
                "</p>")

            # Near-duplicate table (50+ shared IDs)
            if near_dups:
                parts.append(f"<h3>Near-Exact Duplicates ({len(near_dups)}) "
                             f"— same CC installed twice</h3>")
                parts.append("<table class='dup-table'>")
                parts.append("<tr><th>#</th><th>Keep (File A)</th>"
                             "<th>Remove (File B)</th>"
                             "<th>Shared IDs</th><th>Type</th>"
                             "<th>Size A / Size B</th>"
                             "<th>Date A / Date B</th></tr>")
                for rank, dup in enumerate(near_dups[:100], 1):
                    parts.append(
                        f"<tr>"
                        f"<td style='color:var(--dim)'>{rank}</td>"
                        f"<td class='dup-file'>{_esc(dup.name_a)}</td>"
                        f"<td class='dup-remove'>⛔ {_esc(dup.name_b)}</td>"
                        f"<td class='dup-near'>{dup.shared_ids:,}</td>"
                        f"<td style='color:var(--dim)'>{_esc(dup.dominant_type)}</td>"
                        f"<td style='color:var(--dim)'>{dup.size_a_kb:,} KB / {dup.size_b_kb:,} KB</td>"
                        f"<td style='color:var(--dim)'>{dup.date_a} / {dup.date_b}</td>"
                        f"</tr>"
                        f"<tr><td></td><td colspan='6' class='dup-rec'>"
                        f"Recommendation: {_esc(dup.recommendation)}</td></tr>"
                    )
                if len(near_dups) > 100:
                    parts.append(f"<tr><td colspan='7' style='color:var(--dim)'>"
                                 f"... and {len(near_dups)-100} more near-exact duplicates</td></tr>")
                parts.append("</table>")

            # Minor overlap table (< 50 shared IDs)
            minor_dups = [d for d in all_dups if not d.is_near_duplicate]
            if minor_dups:
                parts.append(f"<h3>Minor Overlaps ({len(minor_dups)}) "
                             f"— partial shared resources</h3>")
                parts.append("<table class='dup-table'>")
                parts.append("<tr><th>#</th><th>File A</th><th>File B</th>"
                             "<th>Shared IDs</th><th>Type</th></tr>")
                for rank, dup in enumerate(minor_dups[:50], 1):
                    parts.append(
                        f"<tr>"
                        f"<td style='color:var(--dim)'>{rank}</td>"
                        f"<td class='dup-file'>{_esc(dup.name_a)}</td>"
                        f"<td class='dup-file'>{_esc(dup.name_b)}</td>"
                        f"<td class='dup-minor'>{dup.shared_ids:,}</td>"
                        f"<td style='color:var(--dim)'>{_esc(dup.dominant_type)}</td>"
                        f"</tr>"
                    )
                if len(minor_dups) > 50:
                    parts.append(f"<tr><td colspan='5' style='color:var(--dim)'>"
                                 f"... and {len(minor_dups)-50} more minor overlaps</td></tr>")
                parts.append("</table>")

        # Quarantined files
        if quarantined:
            parts.append(f"<h2 id='quarantine' style='color:var(--amber)'>"
                         f"🔒 Quarantined This Run ({len(quarantined)} files)</h2>")
            parts.append("<p style='color:var(--dim);font-size:11px;margin-bottom:12px'>"
                         "These files were safely moved to MODS_DISABLED. "
                         "They are NOT deleted and can be restored any time from the Fix &amp; Repair tab.</p>")
            for q in quarantined:
                parts.append(f"""
<div class='quarantine-item'>
  <div class='qt-file'>🚫 {_esc(q.get('name',''))}</div>
  <div class='qt-why'>Reason: {_esc(q.get('reason',''))}</div>
</div>""")
        elif criticals:
            parts.append("<h2 id='quarantine'>Quarantined This Run</h2>")
            parts.append("<p style='color:var(--dim)'>No files were auto-quarantined during this run. "
                         "Use the Wizard or Fix &amp; Repair tab to quarantine the critical mods listed above.</p>")

        # Stats
        parts.append("<h2 id='stats'>Scan Statistics</h2>")
        parts.append("<div class='stat-grid'>")
        stat_items = [
            ("Total Scripts",      str(report.total_scripts),      "var(--green)"),
            ("Total Packages",     f"{report.total_packages:,}",   "var(--green)"),
            ("Depth Violations",   str(report.total_depth_violations),
             ("var(--red)" if report.total_depth_violations else "var(--green)")),
            ("Critical Issues",    str(crit), "var(--red)" if crit else "var(--green)"),
            ("Warnings",           str(warn), "var(--amber)" if warn else "var(--green)"),
            ("Crash Probability",  f"{report.crash_probability}%", verdict_color),
        ]
        for ph in report.phases:
            for k, v in ph.stats.items():
                if isinstance(v, (int, float)) and k != "installed_map":
                    label = f"{ph.name} / {k.replace('_',' ')}"
                    stat_items.append((label, f"{v:,}" if isinstance(v, int) else str(v),
                                       "var(--cyan)"))
        for label, value, color in stat_items:
            parts.append(f"""
<div class='stat-card'>
  <div class='stat-label'>{label}</div>
  <div class='stat-value' style='color:{color}'>{value}</div>
</div>""")
        parts.append("</div>")  # end stat-grid

        # Footer
        parts.append(_HTML_FOOT.format(
            timestamp=timestamp,
            game_version=report.game_version or "Unknown",
        ))

        return "\n".join(parts)

    # ── Plain text builder ────────────────────────────────────────────────────

    def _build_txt(self, report: BootReport, quarantined: list,
                   ts: datetime, label: str) -> str:
        SEP  = "─" * 70
        DSEP = "═" * 70
        lines = []
        timestamp = ts.strftime("%Y-%m-%d %H:%M:%S")

        def h(text):
            lines.append(f"\n{DSEP}")
            lines.append(f"  {text}")
            lines.append(DSEP)

        def s(text):
            lines.append(f"\n{SEP}")
            lines.append(f"  {text}")
            lines.append(SEP)

        h("SIMS4 MOD GUARDIAN — FULL BOOT AUDIT")
        lines.append(f"  Run: {timestamp}" + (f"  |  {label}" if label else ""))
        lines.append(f"  Game: {report.game_version or 'Unknown'}")
        lines.append(f"  Mods: {report.mods_folder}")

        s("VERDICT")
        lines.append(f"  Result:           {report.verdict_label}")
        lines.append(f"  Crash probability:{report.crash_probability}%")
        lines.append(f"  Critical issues:  {report.critical_count}")
        lines.append(f"  Warnings:         {report.warning_count}")
        lines.append(f"  Scripts scanned:  {report.total_scripts:,}")
        lines.append(f"  Packages scanned: {report.total_packages:,}")
        lines.append(f"  Depth violations: {report.total_depth_violations}")

        s("PHASE SUMMARY")
        lines.append(f"  {'Phase':<22} {'Status':<12} {'Issues':>7}")
        lines.append(f"  {'─'*22} {'─'*12} {'─'*7}")
        for ph in report.phases:
            lines.append(f"  {ph.name:<22} {ph.status:<12} {len(ph.issues):>7}"
                         f"  {_phase_key_stat(ph)}")

        criticals = [i for i in report.all_issues if i.severity == "CRITICAL"]
        warnings  = [i for i in report.all_issues if i.severity == "WARNING"]

        if criticals:
            s(f"CRITICAL ISSUES ({len(criticals)}) — WILL CAUSE CRASHES")
            lines.append("  Quarantine these before launching the game.")
            for iss in criticals:
                lines.append(f"\n  FILE:  {iss.file}")
                lines.append(f"  [!!]   {iss.message}")
                lines.append(f"  WHY:   {_why(iss)}")
                if iss.fix:
                    lines.append(f"  FIX:   {iss.fix}")
        else:
            s("CRITICAL ISSUES")
            lines.append("  ✓ None found — no critical issues detected.")

        if warnings:
            s(f"WARNINGS ({len(warnings)})")
            for iss in warnings:
                lines.append(f"\n  FILE:  {iss.file}")
                lines.append(f"  [!]    {iss.message}")
                lines.append(f"  WHY:   {_why(iss)}")
        else:
            s("WARNINGS")
            lines.append("  ✓ None found.")

        # Duplicate CC files section
        if report.dup_file_pairs:
            near_dups  = [d for d in report.dup_file_pairs if d.is_near_duplicate]
            minor_dups = [d for d in report.dup_file_pairs if not d.is_near_duplicate]
            s(f"DUPLICATE CC FILES ({len(report.dup_file_pairs)} pairs, "
              f"{len(near_dups)} near-exact)")
            lines.append("  Near-exact duplicates: same CC installed twice. Remove the older file.")
            lines.append("  Minor overlaps: partial shared IDs between different CC sets.")
            lines.append("")

            if near_dups:
                lines.append(f"  NEAR-EXACT DUPLICATES ({len(near_dups)}) — 50+ shared IDs:")
                lines.append(f"  {'#':<4} {'Shared':>7}  {'Type':<18}  Remove (quarantine this file)")
                lines.append(f"  {'─'*4} {'─'*7}  {'─'*18}  {'─'*40}")
                for rank, dup in enumerate(near_dups[:50], 1):
                    keep = dup.name_a if dup.remove_path == dup.file_b else dup.name_b
                    remove = Path(dup.remove_path).name
                    lines.append(f"  {rank:<4} {dup.shared_ids:>7,}  {dup.dominant_type:<18}  {remove}")
                    lines.append(f"       Keep: {keep}")
                    lines.append(f"       {dup.recommendation}")
                    lines.append("")
                if len(near_dups) > 50:
                    lines.append(f"  ... and {len(near_dups)-50} more near-exact pairs (see HTML report)")

            if minor_dups:
                lines.append(f"\n  MINOR OVERLAPS ({len(minor_dups)}) — <50 shared IDs:")
                lines.append(f"  {'#':<4} {'Shared':>7}  {'Type':<18}  File A  vs  File B")
                lines.append(f"  {'─'*4} {'─'*7}  {'─'*18}  {'─'*50}")
                for rank, dup in enumerate(minor_dups[:20], 1):
                    lines.append(f"  {rank:<4} {dup.shared_ids:>7,}  {dup.dominant_type:<18}  "
                                 f"{dup.name_a[:25]}  vs  {dup.name_b[:25]}")
                if len(minor_dups) > 20:
                    lines.append(f"  ... and {len(minor_dups)-20} more (see HTML report)")

        if quarantined:
            s(f"QUARANTINED THIS RUN ({len(quarantined)} files)")
            lines.append("  Files moved to MODS_DISABLED. Restore from Fix & Repair tab.")
            for q in quarantined:
                lines.append(f"\n  FILE:   {q.get('name','')}")
                lines.append(f"  REASON: {q.get('reason','')}")
        elif criticals:
            s("QUARANTINED THIS RUN")
            lines.append("  No files quarantined this run.")
            lines.append("  Use Wizard Step 4 or Fix & Repair to quarantine critical mods.")

        s("STATS")
        lines.append(f"  {'Metric':<35} {'Value':>10}")
        lines.append(f"  {'─'*35} {'─'*10}")
        for ph in report.phases:
            for k, v in ph.stats.items():
                if isinstance(v, (int, float)) and k != "installed_map":
                    label = f"{ph.name}/{k}"
                    lines.append(f"  {label:<35} "
                                 f"{ f'{v:,}' if isinstance(v,int) else str(v):>10}")

        lines.append(f"\n{'═'*70}")
        lines.append(f"  Generated by Sims4ModGuard — {timestamp}")
        lines.append("═" * 70)
        return "\n".join(lines)

    # ── Log rotation ──────────────────────────────────────────────────────────

    def _rotate_logs(self):
        """Keep only the MAX_LOGS most recent logs; archive the rest."""
        all_logs = sorted(self.log_dir.glob("audit_*.html"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        old = all_logs[MAX_LOGS:]
        for old_html in old:
            old_txt = old_html.with_suffix(".txt")
            try:
                shutil.move(str(old_html), str(ARC_DIR / old_html.name))
                if old_txt.exists():
                    shutil.move(str(old_txt), str(ARC_DIR / old_txt.name))
            except Exception:
                pass

    def list_logs(self) -> list[Path]:
        """Return all HTML logs sorted newest first."""
        return sorted(self.log_dir.glob("audit_*.html"),
                      key=lambda p: p.stat().st_mtime, reverse=True)

    def open_latest(self) -> Optional[Path]:
        """Return path to the most recent HTML log."""
        logs = self.list_logs()
        return logs[0] if logs else None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hex_tint(hex_color: str, alpha: float) -> str:
    """Mix hex_color with black at given alpha (0–1) — returns 6-char hex."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "#0a0a1a"
    r = int(int(h[0:2], 16) * alpha)
    g = int(int(h[2:4], 16) * alpha)
    b = int(int(h[4:6], 16) * alpha)
    return f"#{r:02x}{g:02x}{b:02x}"


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


def _phase_key_stat(ph: PhaseResult) -> str:
    """Return a single representative stat string for a phase."""
    s = ph.stats
    if "scripts_probed" in s:
        return f"{s['scripts_probed']:,} scripts probed"
    if "packages_scanned" in s:
        return f"{s['packages_scanned']:,} packages"
    if "total_mod_resources" in s:
        return f"{s['total_mod_resources']:,} mod resources"
    if "scripts" in s and "packages" in s:
        return f"{s['scripts']:,} scripts, {s['packages']:,} packages"
    if "installed" in s and "total" in s:
        return f"{s['installed']}/{s['total']} DLC installed"
    if "module_count" in s:
        return f"{s['module_count']:,} game modules loaded"
    if "crash_probability" in s:
        return f"{s['crash_probability']}% crash probability"
    if s:
        k, v = next(iter(s.items()))
        if isinstance(v, (int, float)):
            return f"{k}: {v:,}" if isinstance(v, int) else f"{k}: {v}"
    return ""
