"""
save_analyzer.py
Analyzes Sims 4 save files (.save) for broken mod references.

Sims 4 saves are DBPF archives.  When mods are removed after a save was
created, the save retains references to those mod resources.  On next load
the game tries to find those references, fails, and either crashes or
corrupts game state.

This module:
  1. PARSE  — reads the save DBPF index to collect all embedded resource IDs
  2. CROSS-REFERENCE — compares against the base-game resource table and
                       installed mod package indexes (from game_index)
  3. CLASSIFY — labels each orphaned resource by type (trait, interaction, etc.)
  4. REPAIR  — rewrites the save DBPF omitting broken resource entries
               and patches the index.  Original is backed up to .save.bak

IMPORTANT: Save cleaning is lossy.  Sims may lose custom traits, careers,
or relationships that were added by removed mods.  Always back up saves
before cleaning.
"""

import io
import json
import shutil
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Set, Tuple

from .game_index import GameIndex, DEFAULT_GAME_ROOT, index_mod_packages

# ── Resource type labels for save content ─────────────────────────────────────
SAVE_TYPE_LABELS = {
    0x03B33DDF: "XML Tuning",
    0x62ECC59A: "Object Tuning",
    0x02D5DF13: "Object Definition",
    0x545AC67A: "SimData",
    0xE882D22F: "SimData (Alt)",
    0x814AF95D: "Trait Tuning",
    0xAA1E1E3E: "Interaction Tuning",
    0x6F9B3B46: "Social Tuning",
    0x0C772E27: "Aspiration Tuning",
    0x16CCF748: "Career Tuning",
    0x6017E896: "Buff Tuning",
    0x51C21B1B: "Reward Tuning",
    0x034AEECB: "CAS Part (hair/clothing)",
    0x0166038C: "Build/Buy Object",
    0x9063660B: "Snippet (XmlInjector)",
    0x7DF2169C: "Snippet",
    0x5B16B687: "Combined Tuning",
    # Save-specific types
    0x6BE2C1F4: "Slot (Lot/Household Data)",
    0xB61DE6B7: "Neighborhood Data",
    0x8C870AFF: "Game Setup",
    0xCF9A4ACE: "Swatch",
    0x2C81F764: "Swatch Specular",
    0xBD31E1F3: "RLE2 Texture",
    0x00B2D882: "GEOM Mesh",
    0x736884F1: "LOD Mesh",
    0x015A1849: "Texture (IMG)",
    0x2F7D0004: "CAS Thumbnail",
    0x8B18AE2E: "CAS Overlay",
}

# Types that are "safe" to have as orphans (they're embedded in the save itself)
SAVE_INTERNAL_TYPES = {
    0x6BE2C1F4,  # Slot data — this IS the save
    0xB61DE6B7,  # Neighborhood data
    0x8C870AFF,  # Game setup
}

# Types whose orphans represent actual missing CC or mods
ORPHAN_CRITICAL_TYPES = {
    0x814AF95D,  # Trait — Sim will lose trait
    0x16CCF748,  # Career — Sim may lose career progress
    0x0C772E27,  # Aspiration — Sim loses aspiration
    0x6017E896,  # Buff — Sim loses active buffs
    0x51C21B1B,  # Reward — Sim loses rewards
    0xAA1E1E3E,  # Interaction — interaction breaks
}
ORPHAN_WARNING_TYPES = {
    0x03B33DDF,  # Tuning override — gameplay behavior change
    0x62ECC59A,  # Object tuning — lot object behavior
    0x034AEECB,  # CAS part — sim appearance change (gray swatches)
    0x0166038C,  # Build/Buy object — lot object disappears
}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class SaveResource:
    type_id:     int
    group_id:    int
    instance_id: int
    data_offset: int     # byte offset of resource data in save file
    data_size:   int     # compressed size
    flags:       int = 0

    @property
    def type_label(self) -> str:
        return SAVE_TYPE_LABELS.get(self.type_id, f"Unknown (0x{self.type_id:08X})")

    @property
    def key(self) -> tuple:
        return (self.type_id, self.instance_id)


@dataclass
class OrphanedRef:
    resource: SaveResource
    severity: str            # CRITICAL / WARNING / INFO
    reason:   str            # why it's orphaned
    impact:   str            # gameplay impact description


@dataclass
class SaveReport:
    save_path:         str = ""
    save_size_mb:      float = 0.0
    total_resources:   int = 0
    known_resources:   int = 0
    orphaned_resources: int = 0
    analyzed_at:       str = ""

    orphans:           List[OrphanedRef] = field(default_factory=list)
    resource_list:     List[SaveResource] = field(default_factory=list)

    by_type:           dict = field(default_factory=dict)   # type_label -> count
    orphan_by_type:    dict = field(default_factory=dict)   # type_label -> count

    clean_save_path:   str = ""
    resources_removed: int = 0
    backup_path:       str = ""

    @property
    def critical_orphans(self) -> int:
        return sum(1 for o in self.orphans if o.severity == "CRITICAL")

    @property
    def warning_orphans(self) -> int:
        return sum(1 for o in self.orphans if o.severity == "WARNING")

    @property
    def is_clean(self) -> bool:
        return self.orphaned_resources == 0


# ── DBPF full parser (save-specific) ─────────────────────────────────────────

def _parse_save_dbpf(raw: bytes) -> Tuple[List[SaveResource], dict]:
    """
    Parse a Sims 4 save DBPF and return:
      - List of SaveResource (all resources in the index)
      - header dict (for DBPF reconstruction)
    """
    resources: List[SaveResource] = []
    header = {}

    if len(raw) < 96 or raw[:4] != b"DBPF":
        return resources, header

    major = struct.unpack_from("<I", raw, 4)[0]
    minor = struct.unpack_from("<I", raw, 8)[0]
    if major not in (1, 2):
        return resources, header

    index_count      = struct.unpack_from("<I", raw, 36)[0]
    index_block_size = struct.unpack_from("<I", raw, 44)[0]

    header = {
        "major": major,
        "minor": minor,
        "index_count": index_count,
        "index_block_size": index_block_size,
        "raw_header": raw[:96],
    }

    if index_count == 0 or index_count > 5_000_000:
        return resources, header
    if index_block_size > len(raw):
        return resources, header

    block_start = len(raw) - index_block_size
    if block_start < 96:
        return resources, header

    flags        = struct.unpack_from("<I", raw, block_start)[0]
    TYPE_CONST   = bool(flags & 0x01)
    GROUP_CONST  = bool(flags & 0x02)
    INSHI_CONST  = bool(flags & 0x04)

    header["index_flags"] = flags
    header["block_start"] = block_start

    pos = block_start + 4
    const_type_id  = None
    const_group_id = None
    const_inst_hi  = None

    if TYPE_CONST:
        const_type_id = struct.unpack_from("<I", raw, pos)[0]; pos += 4
    if GROUP_CONST:
        const_group_id = struct.unpack_from("<I", raw, pos)[0]; pos += 4
    if INSHI_CONST:
        const_inst_hi  = struct.unpack_from("<I", raw, pos)[0]; pos += 4

    header["index_start"] = pos

    ENTRY_SIZE = (32
                  - (4 if TYPE_CONST  else 0)
                  - (4 if GROUP_CONST else 0)
                  - (4 if INSHI_CONST else 0))
    if ENTRY_SIZE < 8:
        ENTRY_SIZE = 32

    for i in range(min(index_count, 2_000_000)):
        base = pos + i * ENTRY_SIZE
        if base + ENTRY_SIZE > len(raw):
            break
        try:
            off = base

            if TYPE_CONST:
                type_id = const_type_id
            else:
                type_id = struct.unpack_from("<I", raw, off)[0]; off += 4

            if GROUP_CONST:
                group_id = const_group_id
            else:
                group_id = struct.unpack_from("<I", raw, off)[0]; off += 4

            if INSHI_CONST:
                inst_hi = const_inst_hi
            else:
                inst_hi = struct.unpack_from("<I", raw, off)[0]; off += 4

            inst_lo      = struct.unpack_from("<I", raw, off)[0]; off += 4
            instance_id  = (inst_hi << 32) | inst_lo

            data_offset  = struct.unpack_from("<I", raw, off)[0]; off += 4
            entry_flags  = struct.unpack_from("<I", raw, off)[0]; off += 4
            data_size    = struct.unpack_from("<I", raw, off)[0]  # compressed size

            resources.append(SaveResource(
                type_id=type_id,
                group_id=group_id,
                instance_id=instance_id,
                data_offset=data_offset,
                data_size=data_size,
                flags=entry_flags,
            ))
        except struct.error:
            break

    return resources, header


# ── Save Analyzer ─────────────────────────────────────────────────────────────

class SaveAnalyzer:
    """
    Analyzes a Sims 4 save file for broken mod references and optionally
    repairs it by rewriting the DBPF without orphaned resource entries.
    """

    def __init__(self,
                 s4_folder:  Path,
                 game_root:  Path = DEFAULT_GAME_ROOT,
                 game_index: Optional[GameIndex] = None):
        self.s4_folder   = s4_folder
        self.saves_folder = s4_folder / "saves"
        self.mods_folder  = s4_folder / "Mods"
        self.game_root    = game_root
        self.game_index   = game_index or GameIndex(game_root)
        self._mod_index: Optional[dict] = None

    def _get_mod_index(self, progress_cb=None) -> dict:
        """Build or return cached mod package resource index."""
        if self._mod_index is None:
            if progress_cb:
                progress_cb("Building mod resource index ...")
            self._mod_index = index_mod_packages(self.mods_folder, progress_cb)
        return self._mod_index

    def list_saves(self) -> List[Path]:
        """Return all .save files in the saves folder, sorted newest first."""
        if not self.saves_folder.exists():
            return []
        saves = sorted(
            [f for f in self.saves_folder.glob("*.save") if f.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return saves

    def analyze(self,
                save_path: Path,
                progress_cb: Optional[Callable[[str], None]] = None) -> SaveReport:
        """
        Analyze a save file and return a SaveReport.
        progress_cb(message) is called during analysis.
        """
        def _log(m: str):
            if progress_cb:
                progress_cb(m)

        report = SaveReport(
            save_path=str(save_path),
            analyzed_at=datetime.now().isoformat(),
        )

        if not save_path.exists():
            _log(f"ERROR: Save file not found: {save_path}")
            return report

        report.save_size_mb = save_path.stat().st_size / (1024 * 1024)
        _log(f"Reading save file ({report.save_size_mb:.1f} MB) ...")

        try:
            raw = save_path.read_bytes()
        except Exception as e:
            _log(f"ERROR: Cannot read save file: {e}")
            return report

        _log("Parsing DBPF index ...")
        resources, header = _parse_save_dbpf(raw)
        if not resources:
            _log("ERROR: Could not parse DBPF index — file may be corrupt.")
            return report

        report.total_resources = len(resources)
        report.resource_list   = resources
        _log(f"Found {len(resources):,} resources in save DBPF")

        # Count by type
        by_type: dict = {}
        for res in resources:
            label = res.type_label
            by_type[label] = by_type.get(label, 0) + 1
        report.by_type = by_type

        # Load game index + mod index
        _log("Loading game index ...")
        try:
            self.game_index.ensure_loaded(progress_cb=_log)
        except Exception as e:
            _log(f"WARNING: Game index unavailable ({e}) — orphan detection will be limited")

        _log("Building mod resource index ...")
        mod_index = self._get_mod_index(progress_cb=_log)

        # Build fast lookup sets
        base_game_keys: Set[tuple] = set(self.game_index.resources.keys())
        mod_keys: Set[tuple] = set(mod_index.keys())
        all_known_keys = base_game_keys | mod_keys

        _log(f"Known resources: {len(base_game_keys):,} base game + {len(mod_keys):,} mods")
        _log("Cross-referencing save resources ...")

        orphans: List[OrphanedRef] = []
        known_count = 0
        orphan_by_type: dict = {}

        for idx, res in enumerate(resources):
            if idx % 10000 == 0:
                _log(f"  Cross-referencing [{idx:,}/{len(resources):,}] ...")

            # Skip internal save types (they're generated by the game itself)
            if res.type_id in SAVE_INTERNAL_TYPES:
                known_count += 1
                continue

            key = res.key
            if key in all_known_keys:
                known_count += 1
                continue

            # This resource is in the save but not in base game or any installed mod
            if res.type_id in ORPHAN_CRITICAL_TYPES:
                severity = "CRITICAL"
                impact   = _impact_for_type(res.type_id)
            elif res.type_id in ORPHAN_WARNING_TYPES:
                severity = "WARNING"
                impact   = _impact_for_type(res.type_id)
            else:
                severity = "INFO"
                impact   = "Unknown impact — resource type not recognized."

            reason = (
                f"Resource {res.type_label} (0x{res.type_id:08X}) "
                f"instance 0x{res.instance_id:016X} "
                f"is referenced in the save but not found in any installed "
                f"mod package or base game file."
            )
            orphans.append(OrphanedRef(
                resource=res,
                severity=severity,
                reason=reason,
                impact=impact,
            ))
            label = res.type_label
            orphan_by_type[label] = orphan_by_type.get(label, 0) + 1

        report.known_resources    = known_count
        report.orphaned_resources = len(orphans)
        report.orphans            = orphans
        report.orphan_by_type     = orphan_by_type

        _log(f"Analysis complete: {len(orphans)} orphaned references "
             f"({report.critical_orphans} critical, {report.warning_orphans} warnings)")
        return report

    def generate_clean_save(self,
                             report: SaveReport,
                             output_path: Optional[Path] = None,
                             progress_cb: Optional[Callable[[str], None]] = None
                             ) -> Path:
        """
        Write a cleaned save file that omits orphaned resource entries.
        Backs up the original to .save.bak first.

        Returns the path of the cleaned save.
        """
        def _log(m: str):
            if progress_cb:
                progress_cb(m)

        save_path = Path(report.save_path)
        if not save_path.exists():
            raise FileNotFoundError(f"Original save not found: {save_path}")

        # Default output path
        if output_path is None:
            output_path = save_path.parent / (save_path.stem + "_clean.save")

        # Backup
        backup_path = save_path.parent / (save_path.name + ".bak")
        _log(f"Backing up original save to {backup_path.name} ...")
        shutil.copy2(save_path, backup_path)
        report.backup_path = str(backup_path)

        _log("Reading original save ...")
        raw = save_path.read_bytes()
        resources, header = _parse_save_dbpf(raw)

        if not resources:
            raise ValueError("Cannot parse original save DBPF — aborting clean.")

        # Build set of instance IDs to remove
        orphan_keys: Set[tuple] = {o.resource.key for o in report.orphans}
        _log(f"Removing {len(orphan_keys)} orphaned resource entries ...")

        # Collect resources to keep
        keep = [r for r in resources if r.key not in orphan_keys]
        removed_count = len(resources) - len(keep)
        report.resources_removed = removed_count

        _log(f"Keeping {len(keep):,} of {len(resources):,} resources ...")
        _log("Reconstructing DBPF ...")

        try:
            new_raw = _rebuild_dbpf(raw, keep, header)
            _log(f"Writing clean save to {output_path.name} ...")
            output_path.write_bytes(new_raw)
            report.clean_save_path = str(output_path)
            _log(f"Done — clean save written ({len(new_raw) / 1024 / 1024:.1f} MB), "
                 f"{removed_count} entries removed.")
            return output_path
        except Exception as e:
            raise RuntimeError(f"Failed to rebuild DBPF: {e}") from e


def _impact_for_type(type_id: int) -> str:
    impacts = {
        0x814AF95D: "Affected Sims will lose this custom trait on next load.",
        0x16CCF748: "Affected Sims may lose career progress from this mod.",
        0x0C772E27: "Affected Sims will lose this aspiration.",
        0x6017E896: "Active buffs from this mod will be removed.",
        0x51C21B1B: "Reward points spent on this reward will be lost.",
        0xAA1E1E3E: "Interactions added by this mod will no longer appear.",
        0x03B33DDF: "Tuning override from this mod will no longer apply.",
        0x62ECC59A: "Object behavior changes from this mod will revert.",
        0x034AEECB: "CAS item from this mod will appear as gray/missing on Sims.",
        0x0166038C: "Build/Buy item from this mod will disappear from lots.",
    }
    return impacts.get(type_id, "Behavior may change when this resource is no longer loaded.")


# ── DBPF reconstruction ───────────────────────────────────────────────────────

def _rebuild_dbpf(original: bytes,
                  keep: List[SaveResource],
                  header: dict) -> bytes:
    """
    Rebuild a DBPF file keeping only the listed resources.
    Strategy:
      1. Copy header bytes (first 96 bytes) from original
      2. Copy resource data blocks for kept entries
      3. Write new index at the end
      4. Update header fields: index_count, index_block_size, file size
    This is a conservative rebuild that copies resource data verbatim.
    """
    out = io.BytesIO()

    # Write placeholder header (we'll patch it at the end)
    out.write(original[:96])

    # Write resource data blocks, tracking new offsets
    new_resources: List[SaveResource] = []
    for res in keep:
        # Copy original data block (compressed or uncompressed)
        orig_offset = res.data_offset
        orig_size   = res.data_size

        # Sanity check
        if orig_offset + orig_size > len(original) or orig_offset < 96:
            continue  # skip corrupt entry

        data = original[orig_offset: orig_offset + orig_size]
        new_offset = out.tell()
        out.write(data)
        new_resources.append(SaveResource(
            type_id=res.type_id,
            group_id=res.group_id,
            instance_id=res.instance_id,
            data_offset=new_offset,
            data_size=len(data),
            flags=res.flags,
        ))

    # Write index block
    index_start = out.tell()

    # Determine constant-field flags from original (preserve them)
    orig_flags   = header.get("index_flags", 0)
    TYPE_CONST   = bool(orig_flags & 0x01)
    GROUP_CONST  = bool(orig_flags & 0x02)
    INSHI_CONST  = bool(orig_flags & 0x04)

    # For simplicity in reconstruction, write a non-constant (full 32-byte) index
    # This is always valid even if original used truncated format
    new_flags = 0  # no constants — full entries
    out.write(struct.pack("<I", new_flags))

    ENTRY_SIZE = 32
    for res in new_resources:
        inst_hi = (res.instance_id >> 32) & 0xFFFFFFFF
        inst_lo =  res.instance_id        & 0xFFFFFFFF
        out.write(struct.pack("<II",   res.type_id, res.group_id))
        out.write(struct.pack("<II",   inst_hi,     inst_lo))
        out.write(struct.pack("<I",    res.data_offset))
        out.write(struct.pack("<I",    res.flags))
        out.write(struct.pack("<I",    res.data_size))
        out.write(struct.pack("<I",    res.data_size))  # uncompressed = same (safe default)

    index_end  = out.tell()
    index_size = index_end - index_start

    # Patch header
    result = bytearray(out.getvalue())
    # index_count at offset 36
    struct.pack_into("<I", result, 36, len(new_resources))
    # index_block_size at offset 44 (for v2.x)
    struct.pack_into("<I", result, 44, index_size)
    # Some tools also write index_offset at 40; keep as 0 (end-relative is standard)
    struct.pack_into("<I", result, 40, 0)

    return bytes(result)
