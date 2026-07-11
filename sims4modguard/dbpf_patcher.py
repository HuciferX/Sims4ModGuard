"""
dbpf_patcher.py
Patches Sims 4 CC .package files to remove broken 1.121 tuning attributes.

The game crashes when CC packages override base game objects and include
tuning attributes that EA restructured in patch 1.121:
  - object_reservation_tests  (script_object.py:1196)
  - provided_posture_type     (utils.py:179)

This patcher:
  1. Parses the DBPF header and index
  2. Decompresses each tuning resource (zlib)
  3. Strips the broken XML attribute nodes
  4. Recompresses and rebuilds the package
  5. Creates a .bak backup before any modification

By Hucifer & Hypatia
"""

import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Tuple

# ── DBPF constants ────────────────────────────────────────────────────────────

DBPF_MAGIC = b"DBPF"
HEADER_SIZE = 96
INDEX_ENTRY_SIZE = 32

# Compression types
COMP_NONE   = 0x0000
COMP_ZLIB   = 0x5A42   # standard zlib
COMP_STREAM = 0x0002   # internal stream compression (we skip these)

# Tuning resource type IDs (XML tuning that may contain broken attributes)
TUNING_TYPES = {
    0x03B33DDF,  # Tuning (general)
    0x62ECC59A,  # Object tuning
    0x02D5DF13,  # Object definition tuning
    0x319E4F1D,  # CAS part tuning
}

# Broken attribute names — EA removed/restructured these in patch 1.121
BROKEN_ATTRS = [
    b"object_reservation_tests",
    b"provided_posture_type",
]

# Regex patterns to strip the broken tuning nodes from XML
# Handles all Sims 4 tuning XML node types: <L>, <V>, <T>, <E>, <U>
_PATTERNS = [
    # List nodes: <L n="attr_name" ...>...</L>
    re.compile(rb'<L\s+n="object_reservation_tests"(?:\s[^>]*)?>.*?</L>', re.DOTALL),
    re.compile(rb'<L\s+n="provided_posture_type"(?:\s[^>]*)?>.*?</L>', re.DOTALL),
    # Variant nodes: <V n="attr_name" ...>...</V>
    re.compile(rb'<V\s+n="object_reservation_tests"(?:\s[^>]*)?>.*?</V>', re.DOTALL),
    re.compile(rb'<V\s+n="provided_posture_type"(?:\s[^>]*)?>.*?</V>', re.DOTALL),
    # Tunable nodes: <T n="attr_name">...</T>
    re.compile(rb'<T\s+n="object_reservation_tests"(?:\s[^>]*)?>.*?</T>', re.DOTALL),
    re.compile(rb'<T\s+n="provided_posture_type"(?:\s[^>]*)?>.*?</T>', re.DOTALL),
    # Self-closing enum nodes: <E n="attr_name" .../>
    re.compile(rb'<E\s+n="object_reservation_tests"[^/]*/>', re.DOTALL),
    re.compile(rb'<E\s+n="provided_posture_type"[^/]*/>', re.DOTALL),
]


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DBPFResource:
    type_id:     int
    group_id:    int
    instance_hi: int
    instance_lo: int
    data:        bytes     # raw bytes (possibly compressed) as stored in file
    comp_type:   int       # compression type
    mem_size:    int       # decompressed size in bytes


# ── Decompress helpers ────────────────────────────────────────────────────────

def _decompress(data: bytes, comp_type: int) -> Optional[bytes]:
    """Decompress resource data. Returns None if not supported or failed."""
    if comp_type == COMP_NONE:
        return data

    if comp_type == COMP_ZLIB:
        # Try standard zlib (wbits=15)
        try:
            return zlib.decompress(data)
        except zlib.error:
            pass
        # Try raw deflate (wbits=-15)
        try:
            return zlib.decompress(data, -15)
        except zlib.error:
            pass
        # Try with automatic header detection
        try:
            return zlib.decompress(data, 47)
        except zlib.error:
            pass

    return None  # unsupported compression or failed


def _compress(data: bytes) -> bytes:
    """Compress data with zlib level 6."""
    return zlib.compress(data, level=6)


# ── XML patcher ───────────────────────────────────────────────────────────────

def patch_xml(xml: bytes) -> Tuple[bytes, int]:
    """
    Strip broken tuning attribute nodes from XML bytes.
    Returns (patched_xml, number_of_removals).
    """
    patched = xml
    total_removed = 0
    for pat in _PATTERNS:
        patched, n = re.subn(pat, b"", patched)
        total_removed += n
    return patched, total_removed


# ── DBPF parser ───────────────────────────────────────────────────────────────

def _read_dbpf(raw: bytes) -> Optional[Tuple[bytes, List[DBPFResource]]]:
    """
    Parse a DBPF file.
    Returns (original_header_96_bytes, list_of_resources) or None if invalid.
    """
    if len(raw) < HEADER_SIZE or raw[:4] != DBPF_MAGIC:
        return None

    major = struct.unpack_from("<I", raw, 4)[0]
    if major not in (1, 2):
        return None

    index_count      = struct.unpack_from("<I", raw, 36)[0]
    index_block_size = struct.unpack_from("<I", raw, 44)[0]  # total size of index block
    # Index is at end of file; 4-byte flags header precedes the entries
    index_offset = len(raw) - index_block_size + 4

    if index_count > 200_000 or index_offset < HEADER_SIZE or index_offset > len(raw):
        return None

    original_header = raw[:HEADER_SIZE]
    resources: List[DBPFResource] = []

    for i in range(index_count):
        base = index_offset + i * INDEX_ENTRY_SIZE
        if base + INDEX_ENTRY_SIZE > len(raw):
            break

        type_id     = struct.unpack_from("<I", raw, base + 0)[0]
        group_id    = struct.unpack_from("<I", raw, base + 4)[0]
        inst_hi     = struct.unpack_from("<I", raw, base + 8)[0]
        inst_lo     = struct.unpack_from("<I", raw, base + 12)[0]
        offset      = struct.unpack_from("<I", raw, base + 16)[0]
        file_size   = struct.unpack_from("<I", raw, base + 20)[0]
        mem_size    = struct.unpack_from("<I", raw, base + 24)[0]
        comp_type   = struct.unpack_from("<H", raw, base + 28)[0]

        # Some DBPF writers set bit 31 of file_size as a compressed flag
        if file_size & 0x80000000:
            file_size &= 0x7FFFFFFF
            if comp_type == COMP_NONE:
                comp_type = COMP_ZLIB

        # Sanity: skip entries with unreasonably large sizes (corrupt index)
        MAX_SIZE = 64 * 1024 * 1024  # 64 MB max per resource
        if file_size > MAX_SIZE or mem_size > MAX_SIZE:
            continue

        if offset + file_size > len(raw):
            continue  # corrupt entry

        try:
            data = raw[offset:offset + file_size]
        except MemoryError:
            continue

        resources.append(DBPFResource(
            type_id=type_id,
            group_id=group_id,
            instance_hi=inst_hi,
            instance_lo=inst_lo,
            data=data,
            comp_type=comp_type,
            mem_size=mem_size,
        ))

    return original_header, resources


def _write_dbpf(original_header: bytes, resources: List[DBPFResource]) -> bytes:
    """
    Rebuild a DBPF file from a list of resources.
    Uses the original header as a template, updating only the index fields.
    """
    # Lay resources out contiguously starting right after the header
    parts = [bytearray(original_header)]  # placeholder for header
    positions = []
    current_pos = HEADER_SIZE

    for res in resources:
        positions.append(current_pos)
        parts.append(res.data)
        current_pos += len(res.data)

    # Build index
    index_parts = []
    for i, res in enumerate(resources):
        entry = struct.pack(
            "<IIIIIII",
            res.type_id,
            res.group_id,
            res.instance_hi,
            res.instance_lo,
            positions[i],
            len(res.data),   # file/compressed size
            res.mem_size,    # memory/decompressed size
        )
        entry += struct.pack("<HH", res.comp_type, 1)  # comp_type + committed
        index_parts.append(entry)

    index_blob = b"".join(index_parts)
    index_offset = current_pos

    # Update header with new index fields
    header = bytearray(original_header)
    struct.pack_into("<I", header, 36, len(resources))           # index entry count
    # index block size = 4 (flags header) + entries
    struct.pack_into("<I", header, 44, len(index_blob) + 4)      # index block size at 44
    # Note: index is at end of file; we write it after all resources

    # The index block = 4-byte flags header (zeros = no constant fields) + index entries
    index_block = b"\x00\x00\x00\x00" + index_blob
    parts[0] = header
    return b"".join(bytes(p) for p in parts) + index_block


# ── Public API ────────────────────────────────────────────────────────────────

def patch_package(pkg_path: Path,
                  dry_run: bool = False,
                  backup: bool = True) -> dict:
    """
    Patch a single .package file to remove broken 1.121 tuning attributes.

    Args:
        pkg_path:  Path to the .package file.
        dry_run:   If True, detect but don't modify.
        backup:    If True, write a .bak file before modifying.

    Returns:
        {
          'found':             bool   – broken attributes were detected
          'patched':           bool   – file was actually modified
          'resources_patched': int    – how many XML resources were fixed
          'error':             str|None
        }
    """
    try:
        raw = pkg_path.read_bytes()
    except Exception as e:
        return {"found": False, "patched": False, "resources_patched": 0, "error": str(e)}

    parsed = _read_dbpf(raw)
    if parsed is None:
        return {"found": False, "patched": False, "resources_patched": 0, "error": "Not a valid DBPF"}

    original_header, resources = parsed
    resources_patched = 0

    for res in resources:
        # Only patch tuning resource types
        if res.type_id not in TUNING_TYPES:
            continue

        # Skip non-zlib compressed (stream compression, etc.)
        if res.comp_type not in (COMP_NONE, COMP_ZLIB):
            continue

        # Decompress
        decompressed = _decompress(res.data, res.comp_type)
        if decompressed is None:
            continue

        # Quick check — skip if no broken attrs present
        if not any(attr in decompressed for attr in BROKEN_ATTRS):
            continue

        # Patch the XML
        patched_xml, removals = patch_xml(decompressed)
        if removals == 0:
            continue

        if not dry_run:
            # Recompress (keep same compression type if was compressed)
            if res.comp_type == COMP_ZLIB:
                new_data = _compress(patched_xml)
            else:
                new_data = patched_xml

            res.data     = new_data
            res.mem_size = len(patched_xml)

        resources_patched += 1

    found = resources_patched > 0

    if found and not dry_run:
        if backup:
            bak = pkg_path.with_suffix(".package.bak")
            if not bak.exists():   # don't overwrite existing backup
                bak.write_bytes(raw)

        patched_raw = _write_dbpf(original_header, resources)
        pkg_path.write_bytes(patched_raw)

    return {
        "found":             found,
        "patched":           found and not dry_run,
        "resources_patched": resources_patched,
        "error":             None,
    }


def scan_and_patch_folder(mods_path: Path,
                           dry_run: bool = False,
                           progress_callback=None) -> dict:
    """
    Scan all .package files in mods_path and patch broken 1.121 tuning.

    Args:
        mods_path:         Root Mods folder.
        dry_run:           Detect but don't modify.
        progress_callback: Optional callable(current: int, total: int).

    Returns:
        {
            'scanned':           int
            'found_files':       int
            'patched_files':     int
            'patched_resources': int
            'failed':            list[str]
            'patched_names':     list[str]
        }
    """
    packages = [
        p for p in mods_path.rglob("*.package")
        if "MODS_DISABLED" not in p.parts
    ]

    total = len(packages)
    scanned = 0
    found_files = 0
    patched_files = 0
    patched_resources = 0
    failed: List[str] = []
    patched_names: List[str] = []

    for i, pkg in enumerate(packages):
        result = patch_package(pkg, dry_run=dry_run)
        scanned += 1

        if result["error"] and result["error"] not in ("Not a valid DBPF",):
            failed.append(f"{pkg.name}: {result['error']}")

        if result["found"]:
            found_files += 1
            patched_resources += result["resources_patched"]
            if result["patched"]:
                patched_files += 1
                patched_names.append(pkg.name)

        if progress_callback and (total <= 50 or i % 50 == 0 or i == total - 1):
            progress_callback(i + 1, total)

    return {
        "scanned":           scanned,
        "found_files":       found_files,
        "patched_files":     patched_files,
        "patched_resources": patched_resources,
        "failed":            failed,
        "patched_names":     patched_names,
    }
