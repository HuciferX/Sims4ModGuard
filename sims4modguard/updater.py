"""
Auto-updater for Sims4ModGuard.
Checks GitHub releases API on boot and updates the app if a newer version exists.

Flow:
  1. Read current version from VERSION file (next to the running exe / script).
  2. Hit the GitHub releases API.
  3. Compare semver strings — if remote tag_name > local, open UpdateDialog.
  4. UpdateDialog handles download, replacement, and relaunch.
"""

from __future__ import annotations

import re
import sys
import threading
import urllib.request
import json
from pathlib import Path
from typing import Callable, Optional

# ── Constants ──────────────────────────────────────────────────────────────────

GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/HuciferX/Sims4ModGuard/releases/latest"
)
EXE_ASSET_NAME = "Sims4ModGuard.exe"
REQUEST_TIMEOUT = 8  # seconds


# ── Version helpers ────────────────────────────────────────────────────────────

def _parse_version(ver: str) -> tuple[int, ...]:
    """Parse a semver-like string into a tuple of ints for comparison.

    Strips leading 'v' or 'V', then splits on '.'.
    Non-numeric parts are treated as 0 so that e.g. '1.2.0-beta' still works.
    """
    ver = ver.strip().lstrip("vV")
    parts = re.split(r"[.\-]", ver)
    result: list[int] = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            break  # stop at first non-numeric segment
    return tuple(result) if result else (0,)


def _version_newer(remote: str, local: str) -> bool:
    """Return True if *remote* is strictly newer than *local*."""
    return _parse_version(remote) > _parse_version(local)


# ── VERSION file discovery ─────────────────────────────────────────────────────

def _find_version_file() -> Optional[Path]:
    """Locate the VERSION file relative to the running exe or script."""
    # When packaged with PyInstaller, sys.executable is the .exe
    candidates = [
        Path(sys.executable).parent / "VERSION",
        Path(__file__).parent.parent / "VERSION",  # repo root when running from source
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def read_current_version() -> str:
    """Return the local version string, or '0.0' if the file cannot be found."""
    vf = _find_version_file()
    if vf:
        try:
            return vf.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return "0.0"


# ── GitHub API ─────────────────────────────────────────────────────────────────

def fetch_latest_release() -> Optional[dict]:
    """Return the parsed JSON from the GitHub releases API, or None on failure."""
    try:
        req = urllib.request.Request(
            GITHUB_RELEASES_URL,
            headers={"User-Agent": "Sims4ModGuard-Updater"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except Exception:
        return None


# ── Download ───────────────────────────────────────────────────────────────────

def download_asset(
    url: str,
    dest: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """Stream-download *url* to *dest*, calling progress_callback(bytes_done, total).

    Writes to a .tmp sibling first, then renames atomically to avoid corrupting
    the current exe on partial download.

    Returns True on success, False on any error.
    """
    tmp = dest.with_suffix(".tmp")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Sims4ModGuard-Updater"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024  # 64 KB chunks
            with tmp.open("wb") as fh:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total:
                        progress_callback(downloaded, total)

        # Atomic rename
        if dest.exists():
            dest.replace(dest.with_suffix(".bak"))
        tmp.rename(dest)
        return True
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


# ── Relaunch ───────────────────────────────────────────────────────────────────

def relaunch_exe(exe_path: Path) -> None:
    """Start *exe_path* as a detached process and exit the current process."""
    import subprocess
    import os

    if sys.platform == "win32":
        # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP so the new exe owns its console
        DETACHED = 0x00000008
        subprocess.Popen(
            [str(exe_path)],
            creationflags=DETACHED,
            close_fds=True,
        )
    else:
        # Fallback for non-Windows (dev/testing)
        subprocess.Popen([str(exe_path)], start_new_session=True)

    # Give the OS a moment, then exit
    import time
    time.sleep(0.4)
    os._exit(0)


# ── Public entry point ─────────────────────────────────────────────────────────

def check_and_prompt(parent_window) -> None:
    """Check for updates in a background thread; open UpdateDialog if one exists.

    This is the only function that *gui_app.py* needs to call.
    *parent_window* is the main CTk window (used to schedule the dialog on the
    main thread via ``parent_window.after``).
    """

    def _worker():
        current_ver = read_current_version()
        release = fetch_latest_release()
        if release is None:
            return  # network unavailable — skip silently

        remote_tag = release.get("tag_name", "")
        if not remote_tag:
            return

        if not _version_newer(remote_tag, current_ver):
            return  # already up to date

        # Find the exe asset URL
        exe_url: Optional[str] = None
        for asset in release.get("assets", []):
            if asset.get("name", "").lower() == EXE_ASSET_NAME.lower():
                exe_url = asset.get("browser_download_url")
                break

        if exe_url is None:
            return  # no matching asset — skip silently

        changelog = release.get("body", "")  # release notes markdown

        # Schedule the dialog on the Tk main thread
        def _open_dialog():
            from sims4modguard.update_dialog import UpdateDialog
            dlg = UpdateDialog(
                parent=parent_window,
                current_version=current_ver,
                new_version=remote_tag,
                changelog=changelog,
                exe_url=exe_url,
            )
            dlg.grab_set()

        parent_window.after(0, _open_dialog)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
