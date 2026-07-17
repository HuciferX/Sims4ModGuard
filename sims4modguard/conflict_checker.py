"""
conflict_checker.py
Checks mod filenames against the known conflicts database.
The database is seeded with mods discovered to cause issues on patch 1.121+
and grows via community contributions (GitHub PRs/Issues).
"""

import json
import fnmatch
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent / "known_conflicts.json"
_db: Optional[dict] = None


def _load_db() -> dict:
    global _db
    if _db is None:
        try:
            _db = json.loads(_DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            _db = {"schema_version": "1.0", "conflicts": []}
    return _db


def get_all_conflicts() -> list:
    """Return all known conflict entries."""
    return _load_db().get("conflicts", [])


def check_file(filename: str) -> Optional[dict]:
    """
    Check a filename against all known conflict patterns.
    Returns the conflict entry if matched, None if clean.

    Uses fnmatch glob patterns so 'WW_*.package' matches 'WW_GreyNaya.package'.
    """
    name = Path(filename).name
    for conflict in get_all_conflicts():
        for pattern in conflict.get("file_patterns", []):
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(name.lower(), pattern.lower()):
                return conflict
    return None


def is_broken(filename: str) -> bool:
    """Return True if filename matches a known broken/incompatible/critical conflict."""
    conflict = check_file(filename)
    if conflict is None:
        return False
    return conflict.get("severity") == "critical" or conflict.get("status") in ("broken", "incompatible")


def is_outdated(filename: str) -> bool:
    """Return True if filename matches a known outdated mod that has an update available."""
    conflict = check_file(filename)
    if conflict is None:
        return False
    return conflict.get("status") == "outdated"


def get_update_url(filename: str) -> Optional[str]:
    """Return the update URL for a known mod, if available."""
    conflict = check_file(filename)
    if conflict:
        return conflict.get("update_url")
    return None


def get_replacement(filename: str) -> Optional[str]:
    """Return the recommended replacement for an outdated/broken mod."""
    conflict = check_file(filename)
    if conflict:
        return conflict.get("replacement")
    return None


def scan_directory(mods_path: Path, exclude_disabled: bool = True) -> list:
    """
    Scan a directory for known conflicts.
    Returns a list of (Path, conflict_dict) tuples for flagged files.
    """
    results = []
    for p in mods_path.rglob("*.package"):
        if exclude_disabled and "MODS_DISABLED" in p.parts:
            continue
        conflict = check_file(p.name)
        if conflict:
            results.append((p, conflict))
    for p in mods_path.rglob("*.ts4script"):
        if exclude_disabled and "MODS_DISABLED" in p.parts:
            continue
        conflict = check_file(p.name)
        if conflict:
            results.append((p, conflict))
    # Sort: critical first, then by filename
    results.sort(key=lambda x: (0 if x[1].get("severity") == "critical" else 1, x[0].name.lower()))
    return results


def get_db_stats() -> dict:
    """Return stats about the conflict database."""
    conflicts = get_all_conflicts()
    return {
        "total": len(conflicts),
        "critical": sum(1 for c in conflicts if c.get("severity") == "critical"),
        "warning": sum(1 for c in conflicts if c.get("severity") == "warning"),
        "broken": sum(1 for c in conflicts if c.get("status") == "broken"),
        "outdated": sum(1 for c in conflicts if c.get("status") == "outdated"),
        "incompatible": sum(1 for c in conflicts if c.get("status") == "incompatible"),
        "last_updated": _load_db().get("last_updated", "unknown"),
    }
