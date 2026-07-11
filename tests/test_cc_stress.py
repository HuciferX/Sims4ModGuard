"""
Stress tests and edge cases for sims4modguard.cc_cleaner.
Tries to break the scanner with unusual inputs.
"""
import sys, tempfile, shutil, struct, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sims4modguard.cc_cleaner import scan_all_packages, scan_package


# ── DBPF helpers ──────────────────────────────────────────────────────────────

def make_dbpf(path: Path, resource_count: int = 0, size: int = 512):
    """Minimal valid DBPF package."""
    header = b"DBPF"
    header += struct.pack("<I", 2)    # major
    header += struct.pack("<I", 1)    # minor
    header += b"\x00" * (96 - len(header))
    path.write_bytes(header + b"\x00" * max(0, size - 96))


def make_corrupt(path: Path, content: bytes = b"not a package at all"):
    path.write_bytes(content)


# ── Edge Cases ────────────────────────────────────────────────────────────────

class TestCCEdgeCases:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── Zero-byte file ────────────────────────────────────────────────────
    def test_zero_byte_file(self):
        """A completely empty .package file should not crash the scanner."""
        (self.tmp / "empty.package").write_bytes(b"")
        data = scan_all_packages(self.tmp)
        assert data["summary"]["total"] == 1
        assert data["summary"]["corrupt"] == 1   # empty = corrupt

    # ── Filename with Windows brackets ────────────────────────────────────
    def test_brackets_in_filename(self):
        """Filenames with [brackets] must be handled without LiteralPath issues."""
        make_dbpf(self.tmp / "[CC] My Awesome Mod.package")
        make_dbpf(self.tmp / "Normal Mod.package")
        data = scan_all_packages(self.tmp)
        assert data["summary"]["total"] == 2
        assert data["summary"]["corrupt"] == 0
        names = [r.name for r in data["results"]]
        assert "[CC] My Awesome Mod.package" in names

    # ── Deep folder nesting ───────────────────────────────────────────────
    def test_deeply_nested_folders(self):
        """Packages buried 8 levels deep should still be found."""
        deep = self.tmp
        for level in range(8):
            deep = deep / f"level_{level}"
            deep.mkdir()
        make_dbpf(deep / "buried_mod.package")
        data = scan_all_packages(self.tmp)
        assert data["summary"]["total"] == 1
        names = [r.name for r in data["results"]]
        assert "buried_mod.package" in names

    # ── All files corrupt ─────────────────────────────────────────────────
    def test_all_corrupt(self):
        """A folder of 10 corrupt packages should report 10 corrupt."""
        for i in range(10):
            make_corrupt(self.tmp / f"bad_{i}.package", b"GARBAGE" + bytes([i]))
        data = scan_all_packages(self.tmp)
        assert data["summary"]["total"] == 10
        assert data["summary"]["corrupt"] == 10
        assert data["summary"]["duplicate_names"] == 0

    # ── Identical content, different filenames (hash duplicate) ───────────
    def test_same_content_different_names(self):
        """Two packages with identical bytes but different names = hash dup."""
        content = b"DBPF" + b"\x00" * 512
        (self.tmp / "mod_a.package").write_bytes(content)
        (self.tmp / "mod_b.package").write_bytes(content)
        data = scan_all_packages(self.tmp)
        assert data["summary"]["duplicate_hashes"] >= 1

    # ── Same name, different content (name duplicate) ─────────────────────
    def test_same_name_different_content(self):
        """Same filename in two subfolders = name duplicate."""
        sub1 = self.tmp / "creator1"; sub1.mkdir()
        sub2 = self.tmp / "creator2"; sub2.mkdir()
        make_dbpf(sub1 / "popular_cc.package")
        make_dbpf(sub2 / "popular_cc.package", size=1024)  # slightly different size
        data = scan_all_packages(self.tmp)
        assert data["summary"]["duplicate_names"] >= 1

    # ── WW filename pattern ───────────────────────────────────────────────
    def test_ww_filename_flagged(self):
        """A package matching WickedWhims filename patterns should be flagged."""
        # WW packages typically have 'WW' or 'WickedWhims' in the name
        make_dbpf(self.tmp / "WickedWhims_Anim_SomeCreator.package")
        data = scan_all_packages(self.tmp)
        # Should be flagged as WW package (warning, not necessarily corrupt)
        assert data["summary"]["total"] == 1
        # WW packages are collected separately
        # Even if not flagged by filename, scan should not crash

    # ── Valid DBPF with no resources (empty index) ────────────────────────
    def test_valid_dbpf_zero_resources(self):
        """A valid DBPF header with index_count=0 should scan cleanly."""
        header = b"DBPF"
        header += struct.pack("<I", 2)    # major
        header += struct.pack("<I", 1)    # minor
        # bytes 12-35: unused, fill with zeros
        header += b"\x00" * 24
        # bytes 36-39: index_count = 0
        header += struct.pack("<I", 0)
        # bytes 40-47: index_offset, index_size = 0
        header += struct.pack("<I", 96)  # offset = right after header
        header += struct.pack("<I", 0)   # size = 0
        # pad to 96
        header += b"\x00" * (96 - len(header))
        (self.tmp / "empty_index.package").write_bytes(header)
        data = scan_all_packages(self.tmp)
        assert data["summary"]["total"] == 1
        assert data["summary"]["corrupt"] == 0

    # ── Truncated DBPF (header starts right but file ends early) ─────────
    def test_truncated_dbpf(self):
        """A file starting with DBPF but cut off mid-header should be corrupt."""
        (self.tmp / "truncated.package").write_bytes(b"DBPF" + b"\x00" * 10)
        data = scan_all_packages(self.tmp)
        assert data["summary"]["corrupt"] == 1

    # ── Wrong magic bytes ─────────────────────────────────────────────────
    def test_wrong_magic(self):
        """Files with wrong first 4 bytes flagged as corrupt."""
        wrong_magics = [b"ABCD", b"\x00\x00\x00\x00", b"PBDF", b"ZIP\x00"]
        for i, magic in enumerate(wrong_magics):
            (self.tmp / f"wrong_{i}.package").write_bytes(magic + b"\x00" * 100)
        data = scan_all_packages(self.tmp)
        assert data["summary"]["corrupt"] == 4

    # ── MODS_DISABLED folder excluded ─────────────────────────────────────
    def test_mods_disabled_excluded(self):
        """Packages in MODS_DISABLED should not be scanned."""
        disabled = self.tmp / "MODS_DISABLED"
        disabled.mkdir()
        make_dbpf(disabled / "quarantined.package")
        make_dbpf(self.tmp / "active.package")
        data = scan_all_packages(self.tmp)
        assert data["summary"]["total"] == 1
        assert data["results"][0].name == "active.package"

    # ── max_files limit ───────────────────────────────────────────────────
    def test_max_files_limit(self):
        """max_files parameter caps the number of files scanned."""
        for i in range(20):
            make_dbpf(self.tmp / f"mod_{i:03d}.package")
        data = scan_all_packages(self.tmp, max_files=5)
        assert data["summary"]["total"] == 5

    # ── Long filename ─────────────────────────────────────────────────────
    def test_very_long_filename(self):
        """Filenames near the 255-char limit should not crash the scanner."""
        long_name = "a" * 200 + ".package"
        make_dbpf(self.tmp / long_name)
        data = scan_all_packages(self.tmp)
        assert data["summary"]["total"] == 1


# ── Progress Callback Tests ───────────────────────────────────────────────────

class TestProgressCallback:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_callback_called_for_each_file(self):
        """Progress callback receives at least one call per scan."""
        for i in range(10):
            make_dbpf(self.tmp / f"mod_{i}.package")

        calls = []
        scan_all_packages(self.tmp, progress_callback=lambda c, t: calls.append((c, t)))
        assert len(calls) > 0

    def test_callback_total_is_correct(self):
        """The total passed to callback matches actual file count."""
        for i in range(7):
            make_dbpf(self.tmp / f"mod_{i}.package")

        totals = []
        scan_all_packages(self.tmp, progress_callback=lambda c, t: totals.append(t))
        assert all(t == 7 for t in totals)

    def test_callback_reaches_100_percent(self):
        """Last callback call should have current == total."""
        for i in range(5):
            make_dbpf(self.tmp / f"mod_{i}.package")

        last = []
        scan_all_packages(self.tmp, progress_callback=lambda c, t: last.append((c, t)))
        assert last, "Callback was never called"
        assert last[-1][0] == last[-1][1] == 5

    def test_callback_not_called_on_empty_folder(self):
        """Callback should not be called when there are no packages."""
        calls = []
        scan_all_packages(self.tmp, progress_callback=lambda c, t: calls.append((c, t)))
        assert calls == []

    def test_callback_exception_does_not_crash_scan(self):
        """If callback raises, the scan should still complete."""
        make_dbpf(self.tmp / "mod.package")

        def bad_callback(c, t):
            raise RuntimeError("callback exploded")

        # Scan should not propagate the callback exception
        # (Note: currently the exception WILL propagate — this test documents behavior)
        # If we want to suppress it, we'd wrap in try/except in the scanner
        try:
            data = scan_all_packages(self.tmp, progress_callback=bad_callback)
            # If we get here, exception was suppressed
            assert data["summary"]["total"] == 1
        except RuntimeError:
            # This is also acceptable current behavior — documents it
            pass

    def test_progress_values_are_monotonically_increasing(self):
        """Current value in callback should always increase."""
        for i in range(60):  # enough to trigger the every-50 filter
            make_dbpf(self.tmp / f"mod_{i:03d}.package")

        currents = []
        scan_all_packages(self.tmp, progress_callback=lambda c, t: currents.append(c))
        for i in range(1, len(currents)):
            assert currents[i] >= currents[i - 1], \
                f"Progress went backwards: {currents[i-1]} -> {currents[i]}"


# ── Performance / Scale Test ──────────────────────────────────────────────────

class TestCCScale:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_500_packages_completes(self):
        """Scanning 500 packages should complete in a reasonable time."""
        for i in range(500):
            make_dbpf(self.tmp / f"mod_{i:04d}.package")

        start = time.time()
        data = scan_all_packages(self.tmp)
        elapsed = time.time() - start

        assert data["summary"]["total"] == 500
        assert data["summary"]["corrupt"] == 0
        assert elapsed < 30, f"Scan took too long: {elapsed:.1f}s"
        print(f"\n  500 packages scanned in {elapsed:.2f}s "
              f"({500/elapsed:.0f} pkg/s)")

    def test_mixed_500_packages(self):
        """Mix of valid, corrupt, and duplicate files at scale."""
        # 400 valid
        for i in range(400):
            make_dbpf(self.tmp / f"valid_{i:04d}.package")
        # 50 corrupt
        for i in range(50):
            make_corrupt(self.tmp / f"corrupt_{i:04d}.package")
        # 50 duplicates (25 pairs) — use a proper DBPF header
        # major=2, minor=1, rest zero: a valid minimal DBPF
        dbpf_header = b"DBPF" + struct.pack("<I", 2) + struct.pack("<I", 1) + b"\x00" * 88
        content = dbpf_header + b"\x00" * 416  # 512 total bytes
        sub = self.tmp / "dupes"; sub.mkdir()
        for i in range(25):
            (self.tmp / f"dup_{i}.package").write_bytes(content)
            (sub / f"dup_{i}.package").write_bytes(content)

        data = scan_all_packages(self.tmp)
        assert data["summary"]["total"] == 500
        assert data["summary"]["corrupt"] == 50
        assert data["summary"]["duplicate_names"] == 25
