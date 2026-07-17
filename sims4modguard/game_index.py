"""
game_index.py
Indexes real Sims 4 game files to power the boot simulator.

Builds two indexes from the actual game installation:
  1. MODULE REGISTRY  — every Python module the game ships, extracted from
                        simulation.zip, base.zip, core.zip (3,532+ modules).
                        Used to validate whether mod imports will succeed.
  2. RESOURCE TABLE   — every (TypeID, InstanceID) in base-game and DLC
                        DBPF packages.  Used to detect mod resource conflicts.

Caches results to ~/.sims4modguard_cache/game_index.json so rebuilds
only happen when game files change.
"""

import json
import re
import struct
import time
import zipfile
from pathlib import Path
from typing import Generator, Optional

# ── Default game installation path ────────────────────────────────────────────
DEFAULT_GAME_ROOT = Path(r"C:\Games\ea\sims4\Extracted\The Sims 4")

# ── Cache location ─────────────────────────────────────────────────────────────
CACHE_DIR  = Path.home() / ".sims4modguard_cache"
CACHE_FILE = CACHE_DIR / "game_index.json"

# ── Game Python ZIP paths ─────────────────────────────────────────────────────
GAME_PYTHON_ZIPS = [
    "Data/Simulation/Gameplay/simulation.zip",  # 2955 modules
    "Data/Simulation/Gameplay/base.zip",         # 440 stdlib
    "Data/Simulation/Gameplay/core.zip",         # 137 core
    "Game/Bin/Python/generated.zip",             # 59 protobuf
]

# ── DBPF packages to index for base-game resources ────────────────────────────
BASE_PACKAGES = [
    "Data/Simulation/SimulationFullBuild0.package",
    "Data/Simulation/SimulationDeltaBuild0.package",
    "Data/Client/ClientFullBuild0.package",
]

# ── DLC folder patterns for per-DLC resource indexing ─────────────────────────
DLC_PATTERNS = ["EP{:02d}", "GP{:02d}", "SP{:02d}"]

# Resource types to index (tuning + CAS + objects — high-conflict types)
INDEX_TYPE_IDS = {
    0x03B33DDF,  # XML Tuning
    0x62ECC59A,  # Object Tuning
    0x02D5DF13,  # Object Definition
    0x545AC67A,  # SimData
    0xE882D22F,  # SimData Alt
    0x814AF95D,  # Trait Tuning
    0xAA1E1E3E,  # Interaction Tuning
    0x6F9B3B46,  # Social Tuning
    0x0C772E27,  # Aspiration Tuning
    0x16CCF748,  # Career Tuning
    0x6017E896,  # Buff Tuning
    0x51C21B1B,  # Reward Tuning
    0x034AEECB,  # CAS Part
    0x0166038C,  # Build/Buy Catalog Object
    0x9063660B,  # Snippet (XmlInjector)
    0x7DF2169C,  # Snippet
    0x5B16B687,  # Combined Tuning
}


# ── Module name extractor ─────────────────────────────────────────────────────

def _pyc_name_to_module(name: str) -> Optional[str]:
    """
    Convert a .pyc path from a game ZIP to a Python module name.
    e.g. 'sims/sim_info.pyc' -> 'sims.sim_info'
         'lib/abc.pyc'       -> 'abc'   (strip 'lib/' prefix)
    Returns None if not a .pyc.
    """
    if not name.endswith(".pyc"):
        return None
    name = name[:-4]                   # strip .pyc
    name = name.replace("/", ".")      # path sep -> dot
    name = name.replace("\\", ".")
    # Strip 'lib.' prefix from base.zip stdlib modules
    if name.startswith("lib."):
        name = name[4:]
    return name


def build_module_registry(game_root: Path,
                           progress_cb=None) -> set[str]:
    """
    Extract all Python module names from the game's ZIP archives.
    Returns a set of importable module names.
    progress_cb(msg: str) is called if provided.
    """
    modules: set[str] = set()

    for rel_path in GAME_PYTHON_ZIPS:
        zpath = game_root / rel_path
        if not zpath.exists():
            continue
        if progress_cb:
            progress_cb(f"  Indexing {zpath.name} ...")
        try:
            with zipfile.ZipFile(zpath, "r") as z:
                for entry in z.namelist():
                    mod = _pyc_name_to_module(entry)
                    if mod:
                        modules.add(mod)
                        # Also register parent packages
                        parts = mod.split(".")
                        for i in range(1, len(parts)):
                            modules.add(".".join(parts[:i]))
        except Exception as e:
            if progress_cb:
                progress_cb(f"  WARNING: Could not read {zpath.name}: {e}")

    if progress_cb:
        progress_cb(f"  Module registry: {len(modules):,} importable names")
    return modules


# ── DBPF resource index parser ────────────────────────────────────────────────

def _parse_dbpf_index(raw: bytes, source_label: str,
                      type_filter: Optional[set] = None
                      ) -> Generator[tuple, None, None]:
    """
    Parse a DBPF package and yield (TypeID, InstanceID, source_label) tuples
    for every resource in its index.
    Handles both constant-field (truncated) and full 32-byte index entries.
    """
    if len(raw) < 96 or raw[:4] != b"DBPF":
        return

    major = struct.unpack_from("<I", raw, 4)[0]
    if major not in (1, 2):
        return

    index_count      = struct.unpack_from("<I", raw, 36)[0]
    index_block_size = struct.unpack_from("<I", raw, 44)[0]

    if index_count == 0 or index_count > 2_000_000:
        return
    if index_block_size > len(raw):
        return

    block_start = len(raw) - index_block_size
    if block_start < 96:
        return

    flags        = struct.unpack_from("<I", raw, block_start)[0]
    TYPE_CONST   = bool(flags & 0x01)
    GROUP_CONST  = bool(flags & 0x02)
    INSHI_CONST  = bool(flags & 0x04)

    header_pos = block_start + 4
    const_type_id   = None
    const_inst_hi   = None

    if TYPE_CONST:
        const_type_id = struct.unpack_from("<I", raw, header_pos)[0]
        header_pos += 4
    if GROUP_CONST:
        header_pos += 4  # skip group ID
    if INSHI_CONST:
        const_inst_hi = struct.unpack_from("<I", raw, header_pos)[0]
        header_pos += 4

    # Per-entry size: 32 bytes minus 4 for each constant field
    ENTRY_SIZE = (32
                  - (4 if TYPE_CONST  else 0)
                  - (4 if GROUP_CONST else 0)
                  - (4 if INSHI_CONST else 0))
    if ENTRY_SIZE < 8:
        ENTRY_SIZE = 32

    index_start = header_pos
    field_offset = 0  # current position within per-entry fields

    for i in range(min(index_count, 500_000)):
        base = index_start + i * ENTRY_SIZE
        if base + ENTRY_SIZE > len(raw):
            break
        try:
            off = base
            if TYPE_CONST:
                type_id = const_type_id
            else:
                type_id = struct.unpack_from("<I", raw, off)[0]
                off += 4

            if GROUP_CONST:
                pass  # skip group (constant)
            else:
                off += 4  # skip group field

            if INSHI_CONST:
                inst_hi = const_inst_hi
            else:
                inst_hi = struct.unpack_from("<I", raw, off)[0]
                off += 4

            inst_lo = struct.unpack_from("<I", raw, off)[0]
            instance_id = (inst_hi << 32) | inst_lo

            if type_filter is None or type_id in type_filter:
                yield (type_id, instance_id, source_label)

        except struct.error:
            break


def build_resource_table(game_root: Path,
                         progress_cb=None) -> dict[tuple, str]:
    """
    Build a dict mapping (TypeID, InstanceID) -> source_label for all base-game
    and DLC resources.  This is used to detect:
      - Mods that override base-game resources (tuning conflict)
      - Mods that require DLC you don't have installed
    """
    table: dict[tuple, str] = {}

    # Index base-game packages
    for rel in BASE_PACKAGES:
        p = game_root / rel
        if not p.exists():
            continue
        if progress_cb:
            progress_cb(f"  Indexing {p.name} ...")
        try:
            raw = p.read_bytes()
            for type_id, inst_id, _ in _parse_dbpf_index(raw, p.stem, INDEX_TYPE_IDS):
                key = (type_id, inst_id)
                if key not in table:
                    table[key] = p.stem
        except Exception as e:
            if progress_cb:
                progress_cb(f"  WARNING: {p.name}: {e}")

    # Index DLC packs
    for prefix in ["EP", "GP", "SP"]:
        for n in range(1, 25):
            code = f"{prefix}{n:02d}"
            dlc_folder = game_root / code
            if not dlc_folder.exists():
                continue
            if progress_cb:
                progress_cb(f"  Indexing DLC {code} ...")
            for pkg in dlc_folder.rglob("*.package"):
                try:
                    raw = pkg.read_bytes()
                    for type_id, inst_id, _ in _parse_dbpf_index(raw, code, INDEX_TYPE_IDS):
                        key = (type_id, inst_id)
                        if key not in table:
                            table[key] = code
                except Exception:
                    pass

    if progress_cb:
        progress_cb(f"  Resource table: {len(table):,} indexed resources")
    return table


# ── Mod package resource indexer ───────────────────────────────────────────────

def index_mod_packages(mods_folder: Path,
                        progress_cb=None) -> dict[tuple, list[str]]:
    """
    Index all .package files in the Mods folder.
    Returns {(TypeID, InstanceID): [package_paths]} — lists so we catch
    multi-mod conflicts (same key appearing in more than one mod).
    """
    mod_table: dict[tuple, list[str]] = {}
    packages = [p for p in mods_folder.rglob("*.package")
                if "MODS_DISABLED" not in str(p)]
    total = len(packages)

    for i, pkg in enumerate(packages):
        if progress_cb and i % 200 == 0:
            progress_cb(f"  Scanning mod packages [{i}/{total}] ...")
        try:
            raw = pkg.read_bytes()
            for type_id, inst_id, _ in _parse_dbpf_index(raw, pkg.name, INDEX_TYPE_IDS):
                key = (type_id, inst_id)
                if key not in mod_table:
                    mod_table[key] = []
                mod_table[key].append(str(pkg))
        except Exception:
            pass

    if progress_cb:
        progress_cb(f"  Mod resource index: {len(mod_table):,} unique resource IDs")
    return mod_table


# ── Cache management ───────────────────────────────────────────────────────────

class GameIndex:
    """
    Manages building and caching of the game module registry and resource table.
    Cached indexes are stored at ~/.sims4modguard_cache/game_index.json.
    Cache is invalidated if any source file is newer than the cache.
    """

    def __init__(self, game_root: Path = DEFAULT_GAME_ROOT):
        self.game_root      = game_root
        self.modules:  set[str]             = set()
        self.resources: dict[tuple, str]    = {}
        self._loaded   = False

    def _cache_mtime(self) -> float:
        try:
            return CACHE_FILE.stat().st_mtime
        except FileNotFoundError:
            return 0.0

    def _source_mtime(self) -> float:
        """Return the newest mtime among source files used to build the index."""
        mtimes = []
        for rel in GAME_PYTHON_ZIPS:
            p = self.game_root / rel
            if p.exists():
                mtimes.append(p.stat().st_mtime)
        for rel in BASE_PACKAGES:
            p = self.game_root / rel
            if p.exists():
                mtimes.append(p.stat().st_mtime)
        return max(mtimes) if mtimes else 0.0

    def needs_rebuild(self) -> bool:
        return self._cache_mtime() < self._source_mtime()

    def build(self, progress_cb=None) -> None:
        """Build both indexes from scratch and save to cache."""
        if progress_cb:
            progress_cb("Building game module registry from game ZIPs ...")
        self.modules = build_module_registry(self.game_root, progress_cb)

        if progress_cb:
            progress_cb("Building base-game resource table from DBPF packages ...")
        self.resources = build_resource_table(self.game_root, progress_cb)

        self._save_cache()
        self._loaded = True

    def _save_cache(self) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "built_at":  time.time(),
            "game_root": str(self.game_root),
            "modules":   list(self.modules),
            "resources": {f"{t}:{i}": s for (t, i), s in self.resources.items()},
        }
        try:
            CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_cache(self) -> bool:
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            self.modules   = set(data.get("modules", []))
            raw_res        = data.get("resources", {})
            self.resources = {}
            for key_str, src in raw_res.items():
                t, i = key_str.split(":", 1)
                self.resources[(int(t), int(i))] = src
            self._loaded   = True
            return True
        except Exception:
            return False

    def ensure_loaded(self, progress_cb=None, force_rebuild: bool = False) -> None:
        """Load from cache if valid; rebuild if stale or forced."""
        if self._loaded and not force_rebuild:
            return
        if not force_rebuild and not self.needs_rebuild() and self._load_cache():
            if progress_cb:
                progress_cb(f"Loaded game index from cache "
                            f"({len(self.modules):,} modules, "
                            f"{len(self.resources):,} resources)")
            return
        self.build(progress_cb)

    def is_game_module(self, name: str) -> bool:
        """Return True if `name` is a valid game Python module."""
        return name in self.modules or name.split(".")[0] in self.modules

    def is_base_game_resource(self, type_id: int, instance_id: int) -> bool:
        """Return True if this resource is part of the base game or a DLC."""
        return (type_id, instance_id) in self.resources

    def get_resource_source(self, type_id: int, instance_id: int) -> Optional[str]:
        """Return where a resource originates (package name or DLC code)."""
        return self.resources.get((type_id, instance_id))

    @property
    def module_count(self) -> int:
        return len(self.modules)

    @property
    def resource_count(self) -> int:
        return len(self.resources)
