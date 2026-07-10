"""
scanner.py
Scans .ts4script files for corruption, broken injection patterns,
WickedWhims dependencies, and whether they can be auto-patched.
"""

import re
import zipfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from .known_patterns import (
    REMOVED_APIS,
    BROKEN_INJECT_PATTERNS,
    WW_DEPENDENCY_MARKERS,
    WW_FILENAME_PATTERNS,
    KNOWN_DEAD_MODS,
    KNOWN_SAFE_SCRIPTS,
)

SEVERITY_CRITICAL  = "CRITICAL"   # Causes game to not load
SEVERITY_WARNING   = "WARNING"    # Causes broken features but loads
SEVERITY_INFO      = "INFO"       # Informational only

@dataclass
class ScriptIssue:
    severity:     str
    category:     str
    message:      str
    detail:       str = ""
    patchable:    bool = False
    has_py_files: bool = False
    ww_dep:       bool = False

@dataclass
class ScriptScanResult:
    path:     Path
    name:     str
    corrupt:  bool = False
    issues:   list = field(default_factory=list)
    entries:  list = field(default_factory=list)   # ZIP entry names
    py_files: list = field(default_factory=list)   # readable .py source files
    pyc_only: bool = False

    @property
    def severity(self) -> Optional[str]:
        if self.corrupt:
            return SEVERITY_CRITICAL
        severities = [i.severity for i in self.issues]
        if SEVERITY_CRITICAL in severities:
            return SEVERITY_CRITICAL
        if SEVERITY_WARNING in severities:
            return SEVERITY_WARNING
        if self.issues:
            return SEVERITY_INFO
        return None

    @property
    def is_clean(self) -> bool:
        return not self.corrupt and not self.issues


def _check_ww_filename(name: str) -> bool:
    for pat in WW_FILENAME_PATTERNS:
        if re.search(pat, name, re.IGNORECASE):
            return True
    return False


def _scan_text_content(content: str, name: str) -> list:
    """Return list of ScriptIssue for a single Python file's text content."""
    issues = []

    # 1. Removed APIs — cannot fix
    for api in REMOVED_APIS:
        if api in content:
            issues.append(ScriptIssue(
                severity=SEVERITY_CRITICAL,
                category="removed_api",
                message=f"Uses removed EA API: {api}",
                detail=f"Found in {name} — this API was deleted in patch 1.121. Not auto-fixable.",
                patchable=False,
            ))

    # 2. WickedWhims dependency markers
    for marker in WW_DEPENDENCY_MARKERS:
        if marker.lower() in content.lower():
            issues.append(ScriptIssue(
                severity=SEVERITY_CRITICAL,
                category="ww_dependency",
                message=f"Requires WickedWhims: '{marker}' found",
                detail=f"Found in {name}. Install WickedWhims core .ts4script to enable.",
                ww_dep=True,
            ))
            break

    # 3. Old injection patterns — possibly patchable if .py source available
    matched_inject = []
    for pat in BROKEN_INJECT_PATTERNS:
        if re.search(pat, content):
            matched_inject.append(pat)

    if matched_inject:
        is_patchable = name.endswith(".py")  # .py source = patchable
        issues.append(ScriptIssue(
            severity=SEVERITY_CRITICAL,
            category="broken_inject",
            message=f"Old injection pattern detected",
            detail=f"Patterns: {', '.join(matched_inject[:3])} in {name}",
            patchable=is_patchable,
            has_py_files=is_patchable,
        ))

    return issues


def scan_script(path: Path) -> ScriptScanResult:
    """Scan a single .ts4script file and return a ScriptScanResult."""
    result = ScriptScanResult(path=path, name=path.name)

    # 0. Whitelist check — skip known-safe scripts entirely
    if path.name.lower() in KNOWN_SAFE_SCRIPTS:
        return result   # clean, no issues

    # 1. WW filename check (before even opening)
    if _check_ww_filename(path.name):
        result.issues.append(ScriptIssue(
            severity=SEVERITY_CRITICAL,
            category="ww_dependency",
            message="Filename indicates WickedWhims dependency",
            detail=f"{path.name} appears to be a WickedWhims addon.",
            ww_dep=True,
        ))

    # 2. Known dead mod?
    dead_reason = KNOWN_DEAD_MODS.get(path.name.lower())
    if dead_reason:
        result.issues.append(ScriptIssue(
            severity=SEVERITY_CRITICAL,
            category="known_dead",
            message=f"Known broken mod",
            detail=dead_reason,
            patchable=False,
        ))

    # 3. Try to open as ZIP
    try:
        z = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile:
        result.corrupt = True
        result.issues.append(ScriptIssue(
            severity=SEVERITY_CRITICAL,
            category="corrupt",
            message="Corrupt archive — ZIP cannot be opened",
            detail="File is not a valid ZIP/ts4script. Delete or re-download.",
        ))
        return result
    except Exception as e:
        result.corrupt = True
        result.issues.append(ScriptIssue(
            severity=SEVERITY_CRITICAL,
            category="corrupt",
            message=f"Cannot read archive: {e}",
        ))
        return result

    result.entries = [e.filename for e in z.infolist()]

    # 4. Separate .py source files from .pyc compiled-only
    py_names  = [e for e in result.entries if e.endswith(".py")]
    pyc_names = [e for e in result.entries if e.endswith(".pyc")]
    result.py_files = py_names
    result.pyc_only = bool(pyc_names) and not bool(py_names)

    all_issues = []

    # 5. Scan readable .py files
    for entry_name in py_names:
        try:
            with z.open(entry_name) as f:
                content = f.read().decode("utf-8", errors="replace")
            entry_issues = _scan_text_content(content, entry_name)
            all_issues.extend(entry_issues)
        except Exception:
            pass

    # 6. Scan .pyc files (compiled — we can still grep the byte string)
    for entry_name in pyc_names:
        try:
            with z.open(entry_name) as f:
                raw = f.read()
            # Decode as latin-1 to preserve byte values for regex
            content = raw.decode("latin-1", errors="replace")
            entry_issues = _scan_text_content(content, entry_name)
            # Mark pyc issues as NOT patchable
            for issue in entry_issues:
                issue.patchable = False
                issue.has_py_files = False
            all_issues.extend(entry_issues)
        except Exception:
            pass

    z.close()

    # 7. Deduplicate issues by (category, message)
    seen = set()
    for issue in all_issues:
        key = (issue.category, issue.message[:60])
        if key not in seen:
            seen.add(key)
            result.issues.append(issue)

    return result


def scan_all_scripts(mods_path: Path) -> list:
    """Scan every .ts4script in mods_path (recursively). Returns list of ScriptScanResult."""
    results = []
    scripts = sorted(mods_path.rglob("*.ts4script"))
    for script in scripts:
        # Skip MODS_DISABLED folder
        if "MODS_DISABLED" in script.parts or "Patched_Scripts" in str(script):
            continue
        results.append(scan_script(script))
    return results
