"""
Tests for sims4modguard.cc_cleaner and sims4modguard.quarantine
"""
import sys, tempfile, shutil, struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sims4modguard.cc_cleaner import scan_all_packages
from sims4modguard.quarantine import QuarantineManager


# ── Helpers ───────────────────────────────────────────────────────────────

def make_dbpf_package(path: Path, content_size: int = 256):
    """Create a minimal valid DBPF .package file."""
    # DBPF header: magic + version + padding to 96 bytes
    header = b"DBPF"                   # magic
    header += struct.pack("<I", 2)     # major version = 2
    header += struct.pack("<I", 1)     # minor version = 1
    header += b"\x00" * (96 - len(header))  # rest of header
    path.write_bytes(header + b"\x00" * content_size)


def make_corrupt_package(path: Path):
    """Create a .package file with wrong magic bytes."""
    path.write_bytes(b"NOTDBPF" + b"\x00" * 96)


def make_tiny_package(path: Path):
    """Create a .package file that's too small to be valid."""
    path.write_bytes(b"DBPF" + b"\x00" * 4)  # only 8 bytes


# ── CC Cleaner Tests ──────────────────────────────────────────────────────

class TestCCCleaner:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_valid_package_not_corrupt(self):
        """A valid DBPF package should not be flagged as corrupt."""
        make_dbpf_package(self.tmp / "valid.package")
        data = scan_all_packages(self.tmp)
        assert data["summary"]["corrupt"] == 0

    def test_corrupt_package_detected(self):
        """A package with wrong magic bytes should be flagged as corrupt."""
        make_corrupt_package(self.tmp / "bad.package")
        data = scan_all_packages(self.tmp)
        assert data["summary"]["corrupt"] >= 1

    def test_tiny_package_detected(self):
        """A package too small to have a valid header should be corrupt."""
        make_tiny_package(self.tmp / "tiny.package")
        data = scan_all_packages(self.tmp)
        assert data["summary"]["corrupt"] >= 1

    def test_duplicate_names_detected(self):
        """Two packages with the same name in different subfolders are duplicates."""
        sub1 = self.tmp / "FolderA"
        sub2 = self.tmp / "FolderB"
        sub1.mkdir()
        sub2.mkdir()
        make_dbpf_package(sub1 / "shared_name.package")
        make_dbpf_package(sub2 / "shared_name.package")
        data = scan_all_packages(self.tmp)
        assert data["summary"]["duplicate_names"] >= 1

    def test_unique_names_not_duplicates(self):
        """Packages with different names are not duplicates."""
        make_dbpf_package(self.tmp / "mod_a.package")
        make_dbpf_package(self.tmp / "mod_b.package")
        data = scan_all_packages(self.tmp)
        assert data["summary"]["duplicate_names"] == 0

    def test_empty_folder_returns_zero(self):
        """Scanning an empty folder returns zero for all stats."""
        data = scan_all_packages(self.tmp)
        s = data["summary"]
        assert s["total"] == 0
        assert s["corrupt"] == 0
        assert s["duplicate_names"] == 0

    def test_summary_keys_present(self):
        """scan_all_packages always returns the expected summary structure."""
        data = scan_all_packages(self.tmp)
        required = {"total", "corrupt", "duplicate_names", "duplicate_hashes",
                    "tuning_conflicts", "ww_packages"}
        assert required.issubset(set(data["summary"].keys()))


# ── Quarantine Tests ──────────────────────────────────────────────────────

class TestQuarantineManager:
    def setup_method(self):
        self.base = Path(tempfile.mkdtemp())
        self.mods = self.base / "Mods"
        self.mods.mkdir()
        self.qm = QuarantineManager(self.base)

    def teardown_method(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _make_mod(self, name: str, content: str = "# mod") -> Path:
        p = self.mods / name
        p.write_text(content)
        return p

    def test_quarantine_moves_file(self):
        """Quarantining a file moves it out of Mods."""
        mod = self._make_mod("bad.ts4script", "inject_load_data()")
        dest = self.qm.quarantine(mod, "Old injection pattern", auto=True)
        assert dest is not None
        assert not mod.exists()
        assert dest.exists()

    def test_quarantine_records_manifest(self):
        """Quarantined files are recorded in the manifest."""
        mod = self._make_mod("tracked.ts4script")
        self.qm.quarantine(mod, "Test reason", auto=True)
        entries = self.qm.get_quarantined()
        names = [e["name"] for e in entries]
        assert "tracked.ts4script" in names

    def test_restore_returns_file(self):
        """Restoring a quarantined file puts it back in Mods."""
        mod = self._make_mod("restorable.ts4script")
        dest = self.qm.quarantine(mod, "Test", auto=True)
        ok = self.qm.restore(str(dest))  # restore() needs a string, not Path
        assert ok
        assert mod.exists()

    def test_restore_removes_from_manifest(self):
        """After restore, the file is removed from the quarantine manifest."""
        mod = self._make_mod("manifest_test.ts4script")
        dest = self.qm.quarantine(mod, "Test", auto=True)
        self.qm.restore(str(dest))  # restore() needs a string, not Path
        entries = self.qm.get_quarantined()
        names = [e["name"] for e in entries]
        assert "manifest_test.ts4script" not in names

    def test_quarantine_nonexistent_file(self):
        """Quarantining a file that doesn't exist should not crash."""
        fake = self.mods / "ghost.ts4script"
        result = self.qm.quarantine(fake, "Does not exist", auto=True)
        assert result is None

    def test_empty_quarantine_manifest(self):
        """get_quarantined on a fresh manager returns an empty list."""
        entries = self.qm.get_quarantined()
        assert isinstance(entries, list)
        assert len(entries) == 0
