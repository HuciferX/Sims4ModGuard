"""
boot_engine.py
7-phase Sims 4 boot simulator using real game files.

Replicates what the game does on launch — without actually running it —
to predict what will crash, conflict, or fail to load.

Phases:
  1. ENGINE      — game EXE, DLLs, Python runtime, Resource.cfg
  2. DLC         — installed DLC folder inventory vs dlc.ini catalog
  3. MOD SCAN    — walk Mods folder, depth violations, file stats
  4. RESOURCE    — parse mod DBPF indexes, detect override conflicts
                   using real base-game resource table from game_index
  5. IMPORT PROBE— build stubs from real game module registry; compile()
                   + exec() each mod .py against stubs; catch real errors
  6. TUNING MERGE— detect tuning signature conflicts (posture, reservation)
  7. VERDICT     — crash probability score, ranked issue list

Progress is emitted via a callback: cb(phase_name, pct_float, message, severity)
Results are returned as a BootReport dataclass.
"""

import re
import struct
import sys
import types
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Generator, List, Optional, Tuple

from .known_patterns import (
    REMOVED_APIS, BROKEN_INJECT_PATTERNS, WW_DEPENDENCY_MARKERS,
    KNOWN_DEAD_MODS, KNOWN_SAFE_SCRIPTS, TUNING_CONFLICT_SIGNATURES,
)
from .game_index import GameIndex, DEFAULT_GAME_ROOT, index_mod_packages

# ── Severity levels ───────────────────────────────────────────────────────────
SEV_CRITICAL = "CRITICAL"
SEV_WARNING  = "WARNING"
SEV_INFO     = "INFO"
SEV_OK       = "OK"

# ── Phase names ───────────────────────────────────────────────────────────────
PHASES = [
    "ENGINE",
    "DLC",
    "MOD SCAN",
    "RESOURCE LOAD",
    "IMPORT PROBE",
    "TUNING MERGE",
    "VERDICT",
]

# ── Resource type labels (for conflict reporting) ─────────────────────────────
RESOURCE_TYPE_LABELS = {
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
    0x034AEECB: "CAS Part",
    0x0166038C: "Build/Buy Object",
    0x9063660B: "Snippet (XmlInjector)",
    0x7DF2169C: "Snippet",
    0x5B16B687: "Combined Tuning",
}

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class BootIssue:
    severity:  str          # CRITICAL / WARNING / INFO
    phase:     str          # which phase caught this
    file:      str          # which file triggered it
    message:   str          # short description
    detail:    str = ""     # longer explanation
    fix:       str = ""     # what to do about it


@dataclass
class PhaseResult:
    name:    str
    status:  str = "PENDING"   # PASS / WARN / FAIL / SKIP / PENDING
    issues:  List[BootIssue] = field(default_factory=list)
    stats:   dict            = field(default_factory=dict)


@dataclass
class BootReport:
    game_version:     str = ""
    game_root:        str = ""
    mods_folder:      str = ""
    total_scripts:    int = 0
    total_packages:   int = 0
    total_depth_violations: int = 0
    crash_probability: int = 0      # 0-100
    phases:           List[PhaseResult] = field(default_factory=list)
    all_issues:       List[BootIssue]  = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.all_issues if i.severity == SEV_CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.all_issues if i.severity == SEV_WARNING)

    @property
    def verdict_label(self) -> str:
        p = self.crash_probability
        if p >= 90: return "WILL CRASH"
        if p >= 60: return "LIKELY CRASH"
        if p >= 30: return "UNSTABLE"
        if p >= 10: return "MINOR ISSUES"
        return "CLEAN BOOT"

    @property
    def verdict_color(self) -> str:
        p = self.crash_probability
        if p >= 90: return "#ff003c"
        if p >= 60: return "#ff6600"
        if p >= 30: return "#ffaa00"
        if p >= 10: return "#aaff00"
        return "#00ff9f"


# ── Progress callback type ────────────────────────────────────────────────────
# cb(phase: str, pct: float, message: str, severity: str = "INFO")
ProgressCB = Callable[[str, float, str, str], None]


# ── Boot Engine ───────────────────────────────────────────────────────────────

class BootEngine:
    """
    Runs a 7-phase simulation of the Sims 4 boot sequence using real game files.
    Call run() and receive progress via callback; get the BootReport at the end.
    """

    MAX_MOD_DEPTH = 5   # game hard limit: mods deeper than 5 folders don't load

    def __init__(self,
                 s4_folder:    Path,
                 game_root:    Path = DEFAULT_GAME_ROOT,
                 game_index:   Optional[GameIndex] = None):
        self.s4_folder   = s4_folder
        self.mods_folder = s4_folder / "Mods"
        self.game_root   = game_root
        self.game_index  = game_index or GameIndex(game_root)
        self.report      = BootReport(
            mods_folder=str(self.mods_folder),
            game_root=str(game_root),
        )
        self._cb: Optional[ProgressCB] = None

    def _emit(self, phase: str, pct: float, msg: str, sev: str = SEV_INFO):
        if self._cb:
            self._cb(phase, pct, msg, sev)

    def _issue(self, phase: str, sev: str, file_: str,
               msg: str, detail: str = "", fix: str = "") -> BootIssue:
        issue = BootIssue(severity=sev, phase=phase,
                          file=file_, message=msg, detail=detail, fix=fix)
        self.report.all_issues.append(issue)
        return issue

    # ── Phase 1: ENGINE ───────────────────────────────────────────────────────

    def _phase_engine(self) -> PhaseResult:
        ph = "ENGINE"
        result = PhaseResult(name=ph)
        self._emit(ph, 0.0, "Checking game engine files ...")

        # Check game EXE
        exe_candidates = [
            self.game_root / "Game" / "Bin" / "TS4_x64.exe",
            self.game_root / "Game" / "Bin" / "TS4.exe",
        ]
        exe_found = any(p.exists() for p in exe_candidates)
        if not exe_found:
            i = self._issue(ph, SEV_CRITICAL, "TS4_x64.exe",
                            "Game executable not found",
                            f"Checked {[str(p) for p in exe_candidates]}",
                            "Re-install or re-extract the game.")
            result.issues.append(i)
        self._emit(ph, 0.1, f"Game EXE: {'FOUND' if exe_found else 'MISSING'}",
                   SEV_OK if exe_found else SEV_CRITICAL)

        # Check Python runtime DLL
        py_dll = self.game_root / "Game" / "Bin" / "python37_x64.dll"
        if not py_dll.exists():
            i = self._issue(ph, SEV_CRITICAL, "python37_x64.dll",
                            "Game Python 3.7 runtime DLL missing",
                            "The game will not start without this file.",
                            "Re-install or re-extract the game.")
            result.issues.append(i)
        self._emit(ph, 0.2, f"Python DLL: {'OK' if py_dll.exists() else 'MISSING'}",
                   SEV_OK if py_dll.exists() else SEV_CRITICAL)

        # Check game module ZIPs
        zips_ok = 0
        for zrel in ["Data/Simulation/Gameplay/simulation.zip",
                     "Data/Simulation/Gameplay/base.zip",
                     "Data/Simulation/Gameplay/core.zip"]:
            zpath = self.game_root / zrel
            if zpath.exists():
                zips_ok += 1
        self._emit(ph, 0.3, f"Game Python ZIPs: {zips_ok}/3 present",
                   SEV_OK if zips_ok == 3 else SEV_WARNING)
        if zips_ok < 3:
            i = self._issue(ph, SEV_WARNING, "Simulation/Gameplay/*.zip",
                            f"Only {zips_ok}/3 game Python ZIPs found",
                            "Some game simulation modules may be missing.",
                            "Verify game files or re-extract.")
            result.issues.append(i)

        # Check Resource.cfg in Mods folder
        rescfg = self.mods_folder / "Resource.cfg"
        if not rescfg.exists():
            rescfg2 = self.s4_folder / "Resource.cfg"
            if not rescfg2.exists():
                i = self._issue(ph, SEV_WARNING, "Resource.cfg",
                                "Resource.cfg not found in Mods folder",
                                "The game uses this to discover mods. Without it, mods may not load.",
                                "Ensure Resource.cfg exists in the Mods folder.")
                result.issues.append(i)

        # Check game version
        gv_file = self.s4_folder / "GameVersion.txt"
        if gv_file.exists():
            ver = gv_file.read_text(encoding="utf-8", errors="replace").strip()
        else:
            ver = "Unknown"
        self.report.game_version = ver
        result.stats["game_version"] = ver
        self._emit(ph, 0.5, f"Game version: {ver}", SEV_INFO)

        # Check game index is available
        self._emit(ph, 0.7, "Loading game module registry ...")
        try:
            self.game_index.ensure_loaded(
                progress_cb=lambda m: self._emit(ph, 0.8, m))
            self._emit(ph, 0.9,
                       f"Module registry: {self.game_index.module_count:,} modules | "
                       f"Resource table: {self.game_index.resource_count:,} resources",
                       SEV_OK)
            result.stats["module_count"]   = self.game_index.module_count
            result.stats["resource_count"] = self.game_index.resource_count
        except Exception as e:
            i = self._issue(ph, SEV_WARNING, "game_index",
                            f"Could not build game index: {e}",
                            "Boot simulation will run in pattern-only mode (less accurate).")
            result.issues.append(i)

        result.status = "FAIL" if any(i.severity == SEV_CRITICAL for i in result.issues) \
                        else ("WARN" if result.issues else "PASS")
        return result

    # ── Phase 2: DLC ─────────────────────────────────────────────────────────

    def _phase_dlc(self) -> PhaseResult:
        from .dlc_database import dlc_summary, DLC_CATALOG
        ph = "DLC"
        result = PhaseResult(name=ph)
        self._emit(ph, 0.0, "Inventorying installed DLC packs ...")

        summary = dlc_summary(self.game_root)
        result.stats = {
            "total":     summary["total"],
            "installed": summary["installed"],
            "missing":   summary["missing"],
            "installed_map": summary["installed_map"],
        }
        self._emit(ph, 0.5,
                   f"DLC installed: {summary['installed']}/{summary['total']}",
                   SEV_OK if summary["missing"] == 0 else SEV_INFO)

        for code in summary["missing_codes"]:
            info = DLC_CATALOG.get(code, {})
            name = info.get("name", code)
            self._emit(ph, 0.7, f"  NOT INSTALLED: {code} — {name}", SEV_INFO)

        self._emit(ph, 1.0, f"DLC scan complete — {summary['missing']} missing", SEV_OK)
        result.status = "PASS"
        return result

    # ── Phase 3: MOD SCAN ────────────────────────────────────────────────────

    def _phase_mod_scan(self) -> PhaseResult:
        ph = "MOD SCAN"
        result = PhaseResult(name=ph)
        self._emit(ph, 0.0, f"Walking Mods folder: {self.mods_folder} ...")

        if not self.mods_folder.exists():
            i = self._issue(ph, SEV_CRITICAL, "Mods/",
                            "Mods folder does not exist",
                            "Expected: " + str(self.mods_folder))
            result.issues.append(i)
            result.status = "FAIL"
            return result

        scripts:  list[Path] = []
        packages: list[Path] = []
        depth_violations: list[Path] = []
        mods_base_depth = len(self.mods_folder.parts)

        all_files = list(self.mods_folder.rglob("*"))
        total = len(all_files)
        for idx, f in enumerate(all_files):
            if not f.is_file():
                continue
            if "MODS_DISABLED" in str(f):
                continue
            rel_depth = len(f.parts) - mods_base_depth

            if f.suffix == ".ts4script":
                scripts.append(f)
                if rel_depth > self.MAX_MOD_DEPTH:
                    depth_violations.append(f)
                    i = self._issue(ph, SEV_WARNING, f.name,
                                    f"Script too deep (depth {rel_depth} > {self.MAX_MOD_DEPTH})",
                                    "Sims 4 only loads mods up to 5 subfolders deep. This will NOT load.",
                                    f"Move to: Mods/{f.name}")
                    result.issues.append(i)

            elif f.suffix == ".package":
                packages.append(f)
                if rel_depth > self.MAX_MOD_DEPTH:
                    depth_violations.append(f)
                    i = self._issue(ph, SEV_WARNING, f.name,
                                    f"Package too deep (depth {rel_depth} > {self.MAX_MOD_DEPTH})",
                                    "Sims 4 only loads mods up to 5 subfolders deep. This CC will NOT load.",
                                    f"Move up to within 5 folder levels of Mods/")
                    result.issues.append(i)

            if idx % 1000 == 0:
                self._emit(ph, idx / max(total, 1),
                           f"  Scanning [{idx}/{total}] files ...")

        self.report.total_scripts  = len(scripts)
        self.report.total_packages = len(packages)
        self.report.total_depth_violations = len(depth_violations)
        self._all_scripts  = scripts
        self._all_packages = packages

        result.stats = {
            "scripts":         len(scripts),
            "packages":        len(packages),
            "depth_violations": len(depth_violations),
        }
        self._emit(ph, 1.0,
                   f"Mod scan: {len(scripts)} scripts, {len(packages):,} packages, "
                   f"{len(depth_violations)} depth violations",
                   SEV_WARNING if depth_violations else SEV_OK)
        result.status = "WARN" if depth_violations else "PASS"
        return result

    # ── Phase 4: RESOURCE LOAD ────────────────────────────────────────────────

    def _phase_resource_load(self) -> PhaseResult:
        ph = "RESOURCE LOAD"
        result = PhaseResult(name=ph)
        self._emit(ph, 0.0, "Parsing mod DBPF resource indexes ...")

        mod_index = index_mod_packages(
            self.mods_folder,
            progress_cb=lambda m: self._emit(ph, 0.0, m)
        )
        self._mod_resource_index = mod_index

        # Detect multi-mod conflicts (two+ mods claim same resource)
        multi_conflicts: list[tuple] = []
        base_overrides:  list[tuple] = []

        total_res = len(mod_index)
        for idx, ((tid, iid), paths) in enumerate(mod_index.items()):
            if idx % 5000 == 0:
                self._emit(ph, idx / max(total_res, 1),
                           f"  Checking resource conflicts [{idx:,}/{total_res:,}] ...")

            if len(paths) > 1:
                # Same TypeID+InstanceID in multiple mods → conflict
                multi_conflicts.append((tid, iid, paths))
                type_label = RESOURCE_TYPE_LABELS.get(tid, f"TypeID 0x{tid:08X}")
                names = [Path(p).name for p in paths[:3]]
                i = self._issue(ph, SEV_WARNING,
                                ", ".join(names),
                                f"Resource conflict: {type_label} 0x{iid:016X}",
                                f"{len(paths)} mods claim the same ID. Last loaded wins — behavior undefined.",
                                "Keep only one mod that modifies this resource.")
                result.issues.append(i)

            # Check if mod overrides a base-game resource
            if self.game_index.is_base_game_resource(tid, iid):
                src = self.game_index.get_resource_source(tid, iid)
                base_overrides.append((tid, iid, paths[0], src))
                # Only flag if truly overriding tuning (not CAS which is expected)
                if tid not in {0x034AEECB}:  # skip CAS parts (expected to override)
                    type_label = RESOURCE_TYPE_LABELS.get(tid, f"TypeID 0x{tid:08X}")
                    i = self._issue(ph, SEV_INFO,
                                    Path(paths[0]).name,
                                    f"Overrides base-game {type_label}",
                                    f"Source: {src}. This is intentional for gameplay mods, "
                                    f"but breaks if EA changes this resource in a patch.",
                                    "Check mod is updated for patch 1.121.")
                    result.issues.append(i)

        result.stats = {
            "total_mod_resources": total_res,
            "multi_conflicts":     len(multi_conflicts),
            "base_overrides":      len(base_overrides),
        }
        self._emit(ph, 1.0,
                   f"Resource scan: {total_res:,} resources, "
                   f"{len(multi_conflicts)} conflicts, "
                   f"{len(base_overrides)} base-game overrides",
                   SEV_WARNING if multi_conflicts else SEV_OK)
        result.status = "WARN" if multi_conflicts else "PASS"
        return result

    # ── Phase 5: IMPORT PROBE ─────────────────────────────────────────────────

    # Modules we must NEVER stub — they are stdlib C extensions that zipfile,
    # importlib, and other built-ins depend on at runtime.
    _STUB_BLACKLIST: set = set()

    @classmethod
    def _get_stub_blacklist(cls) -> set:
        if not cls._STUB_BLACKLIST:
            # Python 3.10+ provides a complete stdlib list
            bl = set(getattr(sys, 'stdlib_module_names', set()))
            # Augment with common C extension names that may not be in stdlib_module_names
            bl |= {
                'zlib', 'binascii', '_io', 'io', 'struct', '_struct',
                'os', 'os.path', 'posix', 'nt', 'codecs', '_codecs',
                'string', 'enum', 'abc', 'functools', '_functools',
                'operator', '_operator', 'itertools', 'collections',
                '_collections', 'copy', 'types', 'weakref', 'threading',
                '_thread', 'queue', 'time', 'math', '_math', 'reprlib',
                'socket', 'ssl', 'json', 'json.decoder', 'json.encoder',
                'zipfile', 'tarfile', 'gzip', 'pathlib', 'stat', 'fnmatch',
                'importlib', 'importlib.abc', 'importlib.util',
                'importlib.machinery', 'importlib.metadata',
                'importlib._bootstrap', 'importlib._bootstrap_external',
                '_warnings', 'warnings', 'builtins', '_builtins',
                'gc', '_gc', 'sys', 'traceback', 'linecache', 'tokenize',
                'token', 'keyword', 'dis', 'inspect', 'ast', 'compile',
                'site', 'signal', 'select', 'errno', 'ctypes',
                'ctypes.util', '_ctypes', 'array', '_array',
            }
            cls._STUB_BLACKLIST = bl
        return cls._STUB_BLACKLIST

    def _build_game_stubs(self) -> dict:
        """
        Create stub module objects for every Sims 4 game module.
        NEVER overrides stdlib or C-extension modules — those must remain
        real so zipfile, pathlib, etc. keep working inside _probe_script.
        Returns the original sys.modules snapshot for cleanup.
        """
        class StubAttr:
            """Attribute that returns itself for any access — prevents AttributeError."""
            def __init__(self, name=""):
                self._n = name
            def __getattr__(self, name):
                return StubAttr(f"{self._n}.{name}")
            def __call__(self, *a, **kw):
                return StubAttr(self._n)
            def __iter__(self):
                return iter([])
            def __bool__(self):
                return True
            def __repr__(self):
                return f"<Stub {self._n}>"

        saved = dict(sys.modules)
        if not self.game_index.modules:
            return saved

        blacklist = self._get_stub_blacklist()
        stubbed = 0

        for mod_name in self.game_index.modules:
            # Never shadow already-loaded modules
            if mod_name in sys.modules:
                continue
            # Never shadow stdlib or C extensions
            root = mod_name.split(".")[0]
            if root in blacklist or mod_name in blacklist:
                continue
            stub = types.ModuleType(mod_name)
            stub.__path__ = []
            stub.__spec__ = None
            stub.__getattr__ = lambda name, _m=mod_name: StubAttr(f"{_m}.{name}")
            sys.modules[mod_name] = stub
            stubbed += 1

        self._emit("IMPORT PROBE", 0.0,
                   f"Installed {stubbed:,} game module stubs (preserved {len(blacklist)} stdlib modules)")
        return saved

    def _restore_stubs(self, saved: dict) -> None:
        """Remove stub modules and restore original sys.modules."""
        for k in list(sys.modules.keys()):
            if k not in saved:
                del sys.modules[k]
        sys.modules.update(saved)

    def _probe_script(self, script_path: Path) -> list[BootIssue]:
        """
        Probe a single .ts4script file by:
        1. Pattern-scanning .py source for removed APIs (existing approach)
        2. compile()-ing each .py source to catch SyntaxError
        3. Scanning imports for modules not in the game's module registry
        """
        issues: list[BootIssue] = []
        ph = "IMPORT PROBE"

        # Skip whitelisted scripts
        if script_path.name.lower() in KNOWN_SAFE_SCRIPTS:
            return issues

        # Check known dead mods
        dead_reason = KNOWN_DEAD_MODS.get(script_path.name.lower())
        if dead_reason:
            issues.append(self._issue(ph, SEV_CRITICAL, script_path.name,
                                      "Known broken mod",
                                      dead_reason,
                                      "Remove or update this mod."))
            return issues

        try:
            zf = zipfile.ZipFile(script_path, "r")
        except (zipfile.BadZipFile, Exception) as e:
            issues.append(self._issue(ph, SEV_CRITICAL, script_path.name,
                                      "Corrupt .ts4script archive",
                                      str(e),
                                      "Delete and re-download this mod."))
            return issues

        py_entries = [e for e in zf.namelist() if e.endswith(".py")]
        pyc_entries = [e for e in zf.namelist() if e.endswith(".pyc")]

        if not py_entries and not pyc_entries:
            issues.append(self._issue(ph, SEV_WARNING, script_path.name,
                                      "Empty .ts4script — no Python files",
                                      "Archive contains no .py or .pyc files.",
                                      "The mod may be corrupt or packed incorrectly."))

        # Scan available .py source
        for entry in py_entries:
            try:
                raw = zf.read(entry)
                src = raw.decode("utf-8", errors="replace")
            except Exception:
                continue

            # 1. Pattern check: removed APIs
            for api in REMOVED_APIS:
                if api in src:
                    issues.append(self._issue(ph, SEV_CRITICAL,
                                              f"{script_path.name}::{entry}",
                                              f"Removed API: {api}",
                                              f"EA deleted this API in patch 1.121.",
                                              "This mod needs an update from its author."))

            # 2. Pattern check: broken injection patterns
            for pat in BROKEN_INJECT_PATTERNS:
                if re.search(pat, src):
                    issues.append(self._issue(ph, SEV_CRITICAL,
                                              f"{script_path.name}::{entry}",
                                              f"Broken injection pattern: {pat}",
                                              "This injection style was removed in patch 1.121.",
                                              "Update the mod or quarantine it."))
                    break

            # 3. Syntax check via compile()
            try:
                compile(src, entry, "exec")
            except SyntaxError as e:
                issues.append(self._issue(ph, SEV_CRITICAL,
                                          f"{script_path.name}::{entry}",
                                          f"Python SyntaxError: {e.msg} (line {e.lineno})",
                                          "This file has invalid Python syntax and cannot load.",
                                          "Delete and re-download this mod."))

            # 4. Import registry check — only if game index is loaded
            if self.game_index.modules:
                for line in src.splitlines():
                    line = line.strip()
                    # Match: import X   or   from X import Y
                    m_imp  = re.match(r'^import\s+([\w\.]+)', line)
                    m_from = re.match(r'^from\s+([\w\.]+)\s+import', line)
                    mod_name = None
                    if m_imp:
                        mod_name = m_imp.group(1)
                    elif m_from:
                        mod_name = m_from.group(1)

                    if mod_name:
                        # Skip stdlib and known safe modules
                        root = mod_name.split(".")[0]
                        if root in sys.stdlib_module_names if hasattr(sys, 'stdlib_module_names') \
                                else root in {"os", "sys", "re", "math", "time", "json",
                                              "struct", "zipfile", "io", "pathlib",
                                              "collections", "itertools", "functools",
                                              "traceback", "weakref", "inspect",
                                              "enum", "dataclasses", "typing"}:
                            continue
                        if not self.game_index.is_game_module(mod_name):
                            # Unknown import — mod depends on something not in game
                            issues.append(self._issue(ph, SEV_CRITICAL,
                                                       f"{script_path.name}::{entry}",
                                                       f"Missing game module: {mod_name}",
                                                       f"'{mod_name}' is not in the game's Python registry. "
                                                       f"Import will fail at runtime.",
                                                       "This mod depends on a removed or missing game module."))

        # Scan .pyc for removed APIs (byte-level)
        for entry in pyc_entries:
            try:
                raw = zf.read(entry)
                content = raw.decode("latin-1", errors="replace")
                for api in REMOVED_APIS:
                    if api in content:
                        issues.append(self._issue(ph, SEV_CRITICAL,
                                                   f"{script_path.name}::{entry}",
                                                   f"Removed API in compiled code: {api}",
                                                   "Found in .pyc (compiled). Cannot auto-fix.",
                                                   "Remove this mod and find an updated version."))
                        break
            except Exception:
                pass

        zf.close()
        return issues

    def _phase_import_probe(self) -> PhaseResult:
        ph = "IMPORT PROBE"
        result = PhaseResult(name=ph)
        self._emit(ph, 0.0, "Installing game module stubs ...")

        saved_modules = self._build_game_stubs()
        total = len(self._all_scripts)
        critical_count = 0

        try:
            for idx, script in enumerate(self._all_scripts):
                pct = (idx + 1) / max(total, 1)
                if idx % 20 == 0:
                    self._emit(ph, pct,
                               f"  Probing [{idx+1}/{total}]: {script.name[:60]} ...",
                               SEV_INFO)
                issues = self._probe_script(script)
                result.issues.extend(issues)
                for i in issues:
                    if i.severity == SEV_CRITICAL:
                        critical_count += 1
                        self._emit(ph, pct, f"  [!!] {script.name}: {i.message}", SEV_CRITICAL)
        finally:
            self._restore_stubs(saved_modules)

        result.stats = {
            "scripts_probed": total,
            "issues_found":   len(result.issues),
            "critical":       critical_count,
        }
        self._emit(ph, 1.0,
                   f"Import probe: {total} scripts checked, "
                   f"{critical_count} critical failures",
                   SEV_CRITICAL if critical_count > 0 else SEV_OK)
        result.status = "FAIL" if critical_count > 0 else \
                        ("WARN" if result.issues else "PASS")
        return result

    # ── Phase 6: TUNING MERGE ─────────────────────────────────────────────────

    def _phase_tuning_merge(self) -> PhaseResult:
        ph = "TUNING MERGE"
        result = PhaseResult(name=ph)
        self._emit(ph, 0.0, "Scanning for tuning conflict signatures ...")

        conflict_count = 0
        total = len(self._all_packages)

        for idx, pkg in enumerate(self._all_packages):
            if idx % 500 == 0:
                self._emit(ph, idx / max(total, 1),
                           f"  Tuning merge [{idx:,}/{total:,}] ...")
            try:
                raw = pkg.read_bytes()
                if raw[:4] != b"DBPF":
                    continue
                for sig in TUNING_CONFLICT_SIGNATURES:
                    if sig in raw:
                        conflict_count += 1
                        i = self._issue(ph, SEV_WARNING, pkg.name,
                                        f"Tuning conflict signature: {sig.decode('latin-1', errors='replace')}",
                                        "This package overrides posture/reservation tuning that changed in patch 1.121.",
                                        "Check if this mod has been updated for patch 1.121.")
                        result.issues.append(i)
                        break
            except Exception:
                pass

        result.stats = {"packages_scanned": total, "tuning_conflicts": conflict_count}
        self._emit(ph, 1.0,
                   f"Tuning merge: {conflict_count} conflict signatures in {total:,} packages",
                   SEV_WARNING if conflict_count > 0 else SEV_OK)
        result.status = "WARN" if conflict_count > 0 else "PASS"
        return result

    # ── Phase 7: VERDICT ─────────────────────────────────────────────────────

    def _phase_verdict(self) -> PhaseResult:
        ph = "VERDICT"
        result = PhaseResult(name=ph)

        crit = self.report.critical_count
        warn = self.report.warning_count

        # Crash probability scoring
        # Each critical issue adds ~15%, warnings ~3%, capped at 99%
        prob = min(99, (crit * 15) + (warn * 3))
        # Add extra weight for depth violations
        if self.report.total_depth_violations > 0:
            prob = min(99, prob + 5)
        self.report.crash_probability = prob

        self._emit(ph, 0.5,
                   f"VERDICT: {self.report.verdict_label} "
                   f"({prob}% crash probability) — "
                   f"{crit} critical, {warn} warnings",
                   SEV_CRITICAL if prob >= 60 else
                   SEV_WARNING  if prob >= 30 else SEV_OK)

        result.stats = {
            "crash_probability": prob,
            "critical_issues":   crit,
            "warning_issues":    warn,
            "verdict":           self.report.verdict_label,
        }
        result.status = "FAIL" if prob >= 60 else ("WARN" if prob >= 10 else "PASS")
        return result

    # ── Main runner ───────────────────────────────────────────────────────────

    def run(self, progress_cb: Optional[ProgressCB] = None) -> BootReport:
        """
        Run all 7 phases and return a BootReport.
        progress_cb(phase, pct, message, severity) is called throughout.
        """
        self._cb = progress_cb
        self._all_scripts:  list[Path] = []
        self._all_packages: list[Path] = []
        self._mod_resource_index: dict = {}

        phase_fns = [
            self._phase_engine,
            self._phase_dlc,
            self._phase_mod_scan,
            self._phase_resource_load,
            self._phase_import_probe,
            self._phase_tuning_merge,
            self._phase_verdict,
        ]

        for fn in phase_fns:
            try:
                ph_result = fn()
            except Exception as e:
                ph_result = PhaseResult(
                    name=fn.__name__.replace("_phase_", "").upper(),
                    status="FAIL",
                    issues=[BootIssue(severity=SEV_CRITICAL,
                                      phase="INTERNAL",
                                      file="boot_engine.py",
                                      message=f"Phase crashed: {e}",
                                      detail=str(e))],
                )
            self.report.phases.append(ph_result)

        return self.report
