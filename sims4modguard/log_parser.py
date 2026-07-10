"""
log_parser.py
Parses Sims 4 lastException.txt (XML format) into grouped,
plain-English error summaries with likely file identification.
"""

import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .known_patterns import ERROR_EXPLANATIONS


@dataclass
class ParsedError:
    session_id:   str
    error_type:   str        # desync / crash / etc.
    category:     str        # script file + line, e.g. "mc_utils.py:217"
    description:  str        # the actual error text
    create_time:  str
    mod_hint:     str = ""   # guessed file name
    explanation:  str = ""   # plain English from ERROR_EXPLANATIONS
    count:        int = 1


@dataclass
class LogSummary:
    game_version:    str = "Unknown"
    total_errors:    int = 0
    sessions:        int = 0
    tuning_finished: bool = True
    grouped:         dict = field(default_factory=dict)   # category -> list[ParsedError]
    root_causes:     list = field(default_factory=list)   # top issues sorted by count
    plain_summary:   str = ""


def _extract_desyncdata(text: str) -> tuple:
    """Extract error description and hint from desyncdata block."""
    # Get the first meaningful line of the error
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    description = lines[0] if lines else text[:200]

    # Try to find the actual exception line
    for line in lines:
        if ("Error" in line or "Exception" in line or
                "AttributeError" in line or "ImportError" in line or
                "TypeError" in line):
            description = line
            break

    # Guess mod file hint from traceback
    mod_hint = ""
    file_matches = re.findall(
        r'File "([^"]+\.py)", line \d+',
        text
    )
    for fm in file_matches:
        p = Path(fm)
        # Skip EA engine files
        if "InGame" not in str(p) and "Gameplay" not in str(p):
            mod_hint = p.name
            break

    return description.strip(), mod_hint


def _find_explanation(description: str) -> str:
    for key, explanation in ERROR_EXPLANATIONS.items():
        if key.lower() in description.lower():
            return explanation
    return ""


def parse_log(log_path: Path) -> LogSummary:
    """Parse lastException.txt and return a LogSummary."""
    summary = LogSummary()

    if not log_path.exists():
        summary.plain_summary = "No lastException.txt found — game launched cleanly."
        return summary

    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        summary.plain_summary = f"Could not read lastException.txt: {e}"
        return summary

    # BetterExceptions header check
    if "<BetterExceptions>" in content:
        be_match = re.search(r"<TuningLoadFinished>(.*?)</TuningLoadFinished>", content)
        if be_match and be_match.group(1).lower() == "false":
            summary.tuning_finished = False

    # Wrap in a root element for parsing (file has multiple root reports)
    try:
        wrapped = f"<root>{content}</root>"
        root = ET.fromstring(wrapped)
    except ET.ParseError:
        # Fall back to regex on raw content
        summary.total_errors = content.count("<report>")
        summary.plain_summary = (
            f"Detected {summary.total_errors} error reports in log "
            f"(XML parse failed — regex fallback)."
        )
        return summary

    sessions = set()
    raw_errors: list[ParsedError] = []

    for report in root.findall("report"):
        session = report.findtext("sessionid", "")
        sessions.add(session)

        version_elem = report.findtext("buildsignature", "")
        if version_elem and summary.game_version == "Unknown":
            m = re.search(r"(\d+\.\d+\.\d+)", version_elem)
            if m:
                summary.game_version = m.group(1)

        create_time = report.findtext("createtime", "")
        category    = report.findtext("categoryid", "")
        error_type  = report.findtext("type", "desync")

        desync_elem = report.find("desyncdata")
        raw_text = desync_elem.text if desync_elem is not None and desync_elem.text else ""

        description, mod_hint = _extract_desyncdata(raw_text)
        explanation = _find_explanation(description)

        raw_errors.append(ParsedError(
            session_id=session,
            error_type=error_type,
            category=category,
            description=description,
            create_time=create_time,
            mod_hint=mod_hint,
            explanation=explanation,
        ))

    summary.total_errors = len(raw_errors)
    summary.sessions     = len(sessions)

    # Group by (category + description truncated) to count repeats
    grouped: dict[str, ParsedError] = {}
    for err in raw_errors:
        key = (err.category, err.description[:80])
        if key in grouped:
            grouped[key].count += 1
        else:
            grouped[key] = err

    # Sort by count descending
    root_causes = sorted(grouped.values(), key=lambda e: e.count, reverse=True)
    summary.root_causes = root_causes[:20]   # top 20

    # Group by category type for report sections
    by_category: dict[str, list] = defaultdict(list)
    for err in root_causes:
        kind = _categorize_error(err.description)
        by_category[kind].append(err)
    summary.grouped = dict(by_category)

    summary.plain_summary = _build_plain_summary(summary)
    return summary


def _categorize_error(description: str) -> str:
    desc_lower = description.lower()
    if "hastunable" in desc_lower or "genealogy_caching" in desc_lower:
        return "Removed API (1.121)"
    if "wickedwhims" in desc_lower or "turbolib2" in desc_lower:
        return "WickedWhims Dependency"
    if "takes 2 positional" in desc_lower or "inject" in desc_lower:
        return "Broken Injection Pattern"
    if "object_reservation_tests" in desc_lower or "provided_posture_type" in desc_lower:
        return "CC Tuning Conflict"
    if "has_instanced_phases" in desc_lower or "gardening_component" in desc_lower:
        return "Save Object Corruption"
    if "import" in desc_lower and "no module" in desc_lower:
        return "Missing Module"
    return "Other"


def _build_plain_summary(summary: LogSummary) -> str:
    lines = []
    lines.append(f"Game version: {summary.game_version}")
    lines.append(f"Sessions in log: {summary.sessions}")
    lines.append(f"Total error reports: {summary.total_errors}")

    if not summary.tuning_finished:
        lines.append("⚠  Tuning did NOT finish loading — this caused the household load failure.")

    lines.append("")
    lines.append("Top issues:")

    for err in summary.root_causes[:10]:
        hint = f" [file: {err.mod_hint}]" if err.mod_hint else ""
        count_str = f" (×{err.count})" if err.count > 1 else ""
        lines.append(f"  • {err.description[:100]}{count_str}{hint}")
        if err.explanation:
            lines.append(f"    → {err.explanation}")

    return "\n".join(lines)
