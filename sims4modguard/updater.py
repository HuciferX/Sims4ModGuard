"""
updater.py
Auto-updater for Sims4ModGuard.
Checks GitHub releases API on boot and prompts to update if a newer version exists.
"""

import sys
import os
import json
import threading
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Callable
from urllib.request import urlopen, Request
from urllib.error import URLError

GITHUB_API = "https://api.github.com/repos/HuciferX/Sims4ModGuard/releases/latest"
VERSION_FILE = Path(__file__).parent.parent / "VERSION"
CURRENT_EXE = Path(sys.executable) if getattr(sys, "frozen", False) else None


def get_current_version() -> str:
    """Read version from VERSION file."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return "1.0"


def _semver_tuple(v: str):
    """Convert '1.2.3' to (1, 2, 3) for comparison."""
    try:
        parts = v.lstrip("v").split(".")
        return tuple(int(x) for x in parts[:3])
    except Exception:
        return (0, 0, 0)


def check_for_update() -> Optional[dict]:
    """
    Check GitHub for a newer release.
    Returns release info dict if update available, None otherwise.
    """
    try:
        req = Request(GITHUB_API, headers={"User-Agent": "Sims4ModGuard-Updater/1.0"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "").lstrip("v")
        current = get_current_version().lstrip("v")

        if _semver_tuple(latest_tag) > _semver_tuple(current):
            # Find .exe asset
            exe_asset = None
            for asset in data.get("assets", []):
                if asset["name"].endswith(".exe"):
                    exe_asset = asset
                    break

            return {
                "current_version": current,
                "new_version": latest_tag,
                "release_name": data.get("name", f"v{latest_tag}"),
                "changelog": data.get("body", "")[:500],
                "download_url": exe_asset["browser_download_url"] if exe_asset else None,
                "html_url": data.get("html_url", ""),
            }
    except URLError:
        pass  # Offline or network error — skip silently
    except Exception:
        pass
    return None


def download_update(url: str, progress_callback: Callable[[float], None] = None) -> Optional[Path]:
    """
    Download the new .exe to a temp file.
    Calls progress_callback(0.0-1.0) as download progresses.
    Returns path to downloaded file, or None on failure.
    """
    try:
        req = Request(url, headers={"User-Agent": "Sims4ModGuard-Updater/1.0"})
        with urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 65536  # 64KB

            tmp = tempfile.NamedTemporaryFile(
                suffix=".exe", prefix="Sims4ModGuard_update_", delete=False
            )
            tmp_path = Path(tmp.name)

            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                tmp.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    progress_callback(min(downloaded / total, 1.0))

            tmp.close()

        if progress_callback:
            progress_callback(1.0)
        return tmp_path

    except Exception as e:
        return None


def apply_update(new_exe: Path):
    """
    Replace current exe with new one and relaunch.
    Uses a bat script on Windows so we can replace the running exe.
    """
    if CURRENT_EXE is None:
        # Running from source — just open the download URL
        return

    current = CURRENT_EXE
    bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
move /y "{new_exe}" "{current}"
start "" "{current}"
del "%~f0"
"""
    bat_path = current.parent / "_update_helper.bat"
    bat_path.write_text(bat_content, encoding="utf-8")
    subprocess.Popen(["cmd", "/c", str(bat_path)], creationflags=0x08000000)  # CREATE_NO_WINDOW
    sys.exit(0)


def check_and_prompt(app_window=None):
    """
    Run update check in background thread.
    If update found and app_window provided, shows the UpdateDialog.
    """
    def _check():
        info = check_for_update()
        if info and info.get("download_url") and app_window:
            try:
                from sims4modguard.update_dialog import UpdateDialog
                app_window.after(0, lambda: UpdateDialog(app_window, info))
            except Exception:
                pass

    threading.Thread(target=_check, daemon=True).start()
