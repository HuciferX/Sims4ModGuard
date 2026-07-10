"""
cache_manager.py
Clears Sims 4 caches and reads game version from user folder.
"""

import re
from pathlib import Path


def find_s4_folder() -> Path | None:
    """Auto-detect the Sims 4 user data folder."""
    candidates = [
        Path.home() / "Documents" / "Electronic Arts" / "The Sims 4",
        Path("C:/Users") / Path.home().name / "Documents" / "Electronic Arts" / "The Sims 4",
    ]
    for c in candidates:
        if c.exists() and (c / "Mods").exists():
            return c
    return None


def read_game_version(s4_folder: Path) -> str:
    """Read the game version from GameVersion.txt if present."""
    gv = s4_folder / "GameVersion.txt"
    if gv.exists():
        try:
            return gv.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    # Fall back to lastException.txt
    le = s4_folder / "lastException.txt"
    if le.exists():
        try:
            content = le.read_text(encoding="utf-8", errors="replace")[:2000]
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", content)
            if m:
                return m.group(1)
        except Exception:
            pass
    return "Unknown"


def get_cache_state(s4_folder: Path) -> dict:
    """Return info about current cache file sizes."""
    thumb = s4_folder / "localthumbcache.package"
    sim   = s4_folder / "localsimtexturecache.package"
    cstr  = s4_folder / "cachestr"

    def sz(p: Path) -> int:
        try:
            return p.stat().st_size if p.exists() else 0
        except Exception:
            return 0

    cstr_files = list(cstr.glob("*")) if cstr.exists() else []

    return {
        "thumbnail_cache_mb":    sz(thumb) // (1024 * 1024),
        "sim_texture_cache_mb":  sz(sim)   // (1024 * 1024),
        "cachestr_files":        len(cstr_files),
        "thumbnail_path":        thumb,
        "sim_texture_path":      sim,
        "cachestr_path":         cstr,
    }


def clear_caches(s4_folder: Path, verbose: bool = True) -> dict:
    """
    Clear Sims 4 caches. Returns dict with cleared file paths and sizes.
    """
    cleared = {"files": [], "bytes_freed": 0}
    targets = [
        s4_folder / "localthumbcache.package",
        s4_folder / "localsimtexturecache.package",
    ]
    for t in targets:
        if t.exists():
            try:
                size = t.stat().st_size
                t.unlink()
                cleared["files"].append(str(t))
                cleared["bytes_freed"] += size
                if verbose:
                    print(f"  Deleted: {t.name} ({size // 1024} KB)")
            except Exception as e:
                if verbose:
                    print(f"  Could not delete {t.name}: {e}")

    # Clear cachestr folder contents (not the folder itself)
    cstr = s4_folder / "cachestr"
    if cstr.exists():
        for f in cstr.iterdir():
            if f.is_file():
                try:
                    size = f.stat().st_size
                    f.unlink()
                    cleared["files"].append(str(f))
                    cleared["bytes_freed"] += size
                except Exception:
                    pass
        if verbose and cleared["files"]:
            print(f"  Cleared cachestr/")

    if verbose:
        mb = cleared["bytes_freed"] // (1024 * 1024)
        print(f"  Total freed: {mb} MB across {len(cleared['files'])} files")

    return cleared
