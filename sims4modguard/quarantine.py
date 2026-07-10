"""
quarantine.py
Safe file mover for Sims 4 mods.
- Uses shutil.move with Path objects (handles [brackets] in filenames)
- Maintains a JSON manifest of every move with reason and restore info
- Supports restoring individual files or entire sessions
- Never deletes — only moves between Mods/ and MODS_DISABLED/
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class QuarantineManager:
    def __init__(self, s4_folder: Path):
        self.s4_folder   = s4_folder
        self.mods_folder = s4_folder / "Mods"
        self.disabled    = s4_folder / "MODS_DISABLED"
        self.manifest_path = s4_folder / "MODS_DISABLED" / "_quarantine_manifest.json"
        self.manifest: list = []
        self._load_manifest()

    # ── Manifest ──────────────────────────────────────────────────────────────

    def _load_manifest(self):
        self.disabled.mkdir(parents=True, exist_ok=True)
        if self.manifest_path.exists():
            try:
                self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except Exception:
                self.manifest = []

    def _save_manifest(self):
        self.manifest_path.write_text(
            json.dumps(self.manifest, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # ── Core move operations ──────────────────────────────────────────────────

    def quarantine(self, source: Path, reason: str, auto: bool = False) -> Optional[Path]:
        """
        Move source file to MODS_DISABLED/.
        Returns destination path on success, None on failure.
        Handles filenames with brackets safely.
        """
        if not source.exists():
            return None

        dest = self.disabled / source.name

        # If name collision in disabled folder, add timestamp suffix
        if dest.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = self.disabled / f"{source.stem}__{ts}{source.suffix}"

        try:
            shutil.move(str(source), str(dest))
        except Exception as e:
            print(f"  ⚠  Could not quarantine {source.name}: {e}")
            return None

        entry = {
            "action":      "quarantine",
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "source":      str(source),
            "destination": str(dest),
            "name":        source.name,
            "reason":      reason,
            "auto":        auto,
            "restored":    False,
        }
        self.manifest.append(entry)
        self._save_manifest()
        return dest

    def restore(self, dest_path_or_name: str) -> bool:
        """
        Restore a file from MODS_DISABLED back to its original location.
        Accepts either the full destination path or just the filename.
        Returns True on success.
        """
        # Find matching manifest entry
        entry = None
        for e in reversed(self.manifest):
            if e.get("restored"):
                continue
            if (e["destination"] == dest_path_or_name or
                    e["name"] == dest_path_or_name or
                    Path(e["destination"]).name == dest_path_or_name):
                entry = e
                break

        if not entry:
            print(f"  ⚠  No quarantine entry found for: {dest_path_or_name}")
            return False

        src  = Path(entry["destination"])
        dest = Path(entry["source"])

        if not src.exists():
            print(f"  ⚠  Quarantined file not found: {src}")
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dest))
            entry["restored"] = True
            entry["restore_time"] = datetime.now(timezone.utc).isoformat()
            self._save_manifest()
            return True
        except Exception as e:
            print(f"  ⚠  Restore failed: {e}")
            return False

    def restore_session(self, session_timestamp_prefix: str) -> int:
        """Restore all files quarantined in a given session (timestamp prefix). Returns count."""
        count = 0
        for entry in self.manifest:
            if entry.get("restored"):
                continue
            if entry["timestamp"].startswith(session_timestamp_prefix):
                if self.restore(entry["destination"]):
                    count += 1
        return count

    # ── Batch quarantine ──────────────────────────────────────────────────────

    def quarantine_many(self, paths_with_reasons: list, auto: bool = True) -> dict:
        """
        Quarantine multiple files.
        paths_with_reasons: list of (Path, reason_str) tuples.
        Returns dict: {success: [Path], failed: [Path]}
        """
        result = {"success": [], "failed": []}
        for source, reason in paths_with_reasons:
            dest = self.quarantine(source, reason, auto=auto)
            if dest:
                result["success"].append(source)
            else:
                result["failed"].append(source)
        return result

    # ── Reporting ─────────────────────────────────────────────────────────────

    def get_quarantined(self) -> list:
        """Return all currently quarantined (not restored) entries."""
        return [e for e in self.manifest if not e.get("restored")]

    def print_manifest(self):
        active = self.get_quarantined()
        print(f"\nQuarantined files ({len(active)}):")
        for e in active:
            print(f"  {e['name']}")
            print(f"    Reason:  {e['reason']}")
            print(f"    Moved:   {e['timestamp'][:19]}")
            print(f"    Origin:  {e['source']}")
