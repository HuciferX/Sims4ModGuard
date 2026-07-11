"""
cc_cleaner.py
Scans .package files (CC) for:
  - Corrupt DBPF headers
  - Duplicate files (by name and by MD5 hash)
  - Suspiciously tiny files (< 1 KB)
  - WW-filename packages (not functional without WW core)
  - Tuning conflict signatures (posture/reservation system)
  - Pre-patch modification date warnings
"""

import hashlib
import re
import struct
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .known_patterns import WW_FILENAME_PATTERNS, TUNING_CONFLICT_SIGNATURES

DBPF_MAGIC = b"DBPF"
PATCH_1121_DATE = datetime(2026, 2, 3, tzinfo=timezone.utc)

# Resource type IDs used in Sims 4 DBPF packages
# These types contain XML tuning that can cause conflicts
TUNING_TYPE_IDS = {
    0x03B33DDF: "Tuning",
    0x62ECC59A: "Tuning (Object)",
    0x545AC67A: "SimData",
    0xE882D22F: "SimData (Object)",
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class PackageIssue:
    severity: str          # CRITICAL / WARNING / INFO
    category: str
    message:  str
    detail:   str = ""

@dataclass
class PackageScanResult:
    path:           Path
    name:           str
    corrupt:        bool = False
    file_size:      int  = 0
    md5:            str  = ""
    issues:         list = field(default_factory=list)
    resource_count: int  = 0
    has_tuning:     bool = False   # contains tuning resources
    ww_filename:    bool = False
    mod_time:       Optional[datetime] = None

    @property
    def severity(self) -> Optional[str]:
        if self.corrupt:
            return "CRITICAL"
        sev = [i.severity for i in self.issues]
        if "CRITICAL" in sev: return "CRITICAL"
        if "WARNING"  in sev: return "WARNING"
        if sev:               return "INFO"
        return None

    @property
    def is_clean(self) -> bool:
        return not self.corrupt and not self.issues


# ── DBPF header reader ────────────────────────────────────────────────────────

def _read_dbpf_header(data: bytes) -> Optional[dict]:
    """
    Parse a DBPF 2.x header.
    Returns dict or None if the file is not valid DBPF.

    Header layout (bytes 0-95, relevant fields):
      0-3:   Magic "DBPF"
      4-7:   Major version (uint32)
      8-11:  Minor version (uint32)
      36-39: Index entry count (uint32)
      40-43: Index first offset (uint32)  [v2.x]
      44-47: Index size in bytes (uint32) [v2.x]
    """
    if len(data) < 96:
        return None
    if data[:4] != DBPF_MAGIC:
        return None

    major = struct.unpack_from("<I", data, 4)[0]
    minor = struct.unpack_from("<I", data, 8)[0]

    if major not in (1, 2):
        return None   # Unknown DBPF version

    try:
        index_count  = struct.unpack_from("<I", data, 36)[0]
        index_offset = struct.unpack_from("<I", data, 40)[0]
        index_size   = struct.unpack_from("<I", data, 44)[0]
    except struct.error:
        return None

    # Basic sanity checks
    if index_count > 100_000:
        return None
    if index_offset > len(data):
        return None

    return {
        "major":        major,
        "minor":        minor,
        "index_count":  index_count,
        "index_offset": index_offset,
        "index_size":   index_size,
    }


def _scan_resource_types(data: bytes, header: dict) -> dict:
    """
    Read index entries and return a dict with:
      type_ids: set of type IDs found
      has_tuning_types: bool
      has_tuning_signatures: bool (byte-level scan)
    """
    result = {
        "type_ids":              set(),
        "has_tuning_types":      False,
        "has_tuning_signatures": False,
    }

    # Parse index entries (version 2.1, 32 bytes each)
    offset = header["index_offset"]
    count  = header["index_count"]
    entry_size = 32

    for i in range(min(count, 5000)):   # cap at 5000 for performance
        entry_start = offset + i * entry_size
        if entry_start + 4 > len(data):
            break
        try:
            type_id = struct.unpack_from("<I", data, entry_start)[0]
            result["type_ids"].add(type_id)
            if type_id in TUNING_TYPE_IDS:
                result["has_tuning_types"] = True
        except struct.error:
            break

    # Byte-level scan for tuning conflict signatures (fast grep)
    for sig in TUNING_CONFLICT_SIGNATURES:
        if sig in data:
            result["has_tuning_signatures"] = True
            break

    return result


# ── Per-file scanner ──────────────────────────────────────────────────────────

def scan_package(path: Path) -> PackageScanResult:
    """Scan a single .package file. Returns PackageScanResult."""
    result = PackageScanResult(path=path, name=path.name)

    # File size
    result.file_size = path.stat().st_size

    # Modification time
    mt = path.stat().st_mtime
    result.mod_time = datetime.fromtimestamp(mt, tz=timezone.utc)

    # WW filename check
    for pat in WW_FILENAME_PATTERNS:
        if re.search(pat, path.name, re.IGNORECASE):
            result.ww_filename = True
            result.issues.append(PackageIssue(
                severity="WARNING",
                category="ww_filename",
                message="WickedWhims animation/addon package",
                detail="This package provides WW content. It won't function until WW core is installed.",
            ))
            break

    # Tiny file check (< 512 bytes)
    if result.file_size < 512:
        result.issues.append(PackageIssue(
            severity="WARNING",
            category="tiny_file",
            message=f"Suspiciously small file ({result.file_size} bytes)",
            detail="Files under 512 bytes are often broken downloads or stubs.",
        ))
        if result.file_size < 16:
            result.corrupt = True
            return result

    # Read file content
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        result.corrupt = True
        result.issues.append(PackageIssue(
            severity="CRITICAL",
            category="read_error",
            message=f"Cannot read file: {e}",
        ))
        return result

    # MD5 for duplicate detection
    result.md5 = hashlib.md5(data).hexdigest()

    # DBPF header validation
    header = _read_dbpf_header(data)
    if header is None:
        result.corrupt = True
        result.issues.append(PackageIssue(
            severity="CRITICAL",
            category="invalid_dbpf",
            message="Invalid DBPF header — not a valid .package file",
            detail="The file does not start with the DBPF magic bytes or has an unknown version.",
        ))
        return result

    result.resource_count = header["index_count"]

    # Resource type scan
    res = _scan_resource_types(data, header)
    result.has_tuning = res["has_tuning_types"]

    # Tuning conflict check (posture/reservation system)
    if res["has_tuning_signatures"]:
        result.issues.append(PackageIssue(
            severity="WARNING",
            category="tuning_conflict",
            message="Contains posture/reservation tuning (possible 1.121 conflict)",
            detail=(
                "This package contains 'provided_posture_type' or 'object_reservation_tests' "
                "tuning. If EA objects like beds or chairs are broken, this may be a culprit."
            ),
        ))

    # Pre-patch date warning (if file predates 1.121 and has tuning)
    if result.has_tuning and result.mod_time < PATCH_1121_DATE:
        result.issues.append(PackageIssue(
            severity="INFO",
            category="old_package",
            message=f"Package predates patch 1.121 ({result.mod_time.date()}) and contains tuning",
            detail="Old packages with tuning overrides may conflict with 1.121 changes.",
        ))

    return result


# ── Batch scanner ─────────────────────────────────────────────────────────────

def scan_all_packages(mods_path: Path, max_files: int = 0,
                      progress_callback=None) -> dict:
    """
    Scan all .package files in mods_path (recursively).

    Returns dict with:
      results:           list[PackageScanResult]
      duplicate_names:   dict { name: [paths] }  — filename duplicates
      duplicate_hashes:  dict { md5: [paths] }   — identical content
      corrupt:           list[PackageScanResult]
      tuning_conflicts:  list[PackageScanResult]
      ww_packages:       list[PackageScanResult]
      summary:           dict
    """
    all_packages = [
        p for p in mods_path.rglob("*.package")
        if "MODS_DISABLED" not in p.parts
        and "Patched_Scripts" not in str(p)
    ]

    if max_files and len(all_packages) > max_files:
        all_packages = all_packages[:max_files]

    results = []
    name_map     = defaultdict(list)   # name  -> [paths]
    hash_map     = defaultdict(list)   # md5   -> [paths]
    total = len(all_packages)

    print(f"  Scanning {total:,} .package files...", flush=True)

    for i, pkg in enumerate(all_packages):
        if i % 500 == 0 and i > 0:
            print(f"    {i:,}/{total:,} scanned...", flush=True)

        r = scan_package(pkg)
        results.append(r)
        name_map[pkg.name].append(pkg)
        if r.md5:
            hash_map[r.md5].append(pkg)

        # Report real progress every 50 files (or always for small sets)
        if progress_callback and (total <= 50 or i % 50 == 0 or i == total - 1):
            progress_callback(i + 1, total)

    # Find actual duplicates
    dup_names   = {n: ps for n, ps in name_map.items()  if len(ps) > 1}
    dup_hashes  = {h: ps for h, ps in hash_map.items()  if len(ps) > 1}

    # Tag results with duplicate info
    dup_name_set = set()
    for paths in dup_names.values():
        for p in paths:
            dup_name_set.add(str(p))
    dup_hash_set = set()
    for paths in dup_hashes.values():
        for p in paths:
            dup_hash_set.add(str(p))

    for r in results:
        if str(r.path) in dup_name_set:
            r.issues.append(PackageIssue(
                severity="WARNING",
                category="duplicate_name",
                message=f"Duplicate filename: '{r.name}'",
                detail="Multiple files with this name exist. Only one will load. Remove extras.",
            ))
        if str(r.path) in dup_hash_set:
            r.issues.append(PackageIssue(
                severity="WARNING",
                category="duplicate_content",
                message="Identical file content found elsewhere",
                detail="This exact file exists in multiple locations. Remove the extras.",
            ))

    corrupt           = [r for r in results if r.corrupt]
    tuning_conflicts  = [r for r in results if any(i.category == "tuning_conflict" for i in r.issues)]
    ww_packages       = [r for r in results if r.ww_filename]
    has_issues        = [r for r in results if r.issues]

    summary = {
        "total":          len(results),
        "corrupt":        len(corrupt),
        "duplicate_names": len(dup_names),
        "duplicate_hashes": len(dup_hashes),
        "tuning_conflicts": len(tuning_conflicts),
        "ww_packages":    len(ww_packages),
        "with_issues":    len(has_issues),
        "clean":          len(results) - len(has_issues),
    }

    return {
        "results":          results,
        "duplicate_names":  dup_names,
        "duplicate_hashes": dup_hashes,
        "corrupt":          corrupt,
        "tuning_conflicts": tuning_conflicts,
        "ww_packages":      ww_packages,
        "summary":          summary,
    }
