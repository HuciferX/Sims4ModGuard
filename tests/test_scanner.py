"""
Tests for sims4modguard.scanner
Creates synthetic .ts4script ZIP files in memory to test detection logic.
"""
import sys, os, zipfile, io, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sims4modguard.scanner import scan_all_scripts, SEVERITY_CRITICAL, SEVERITY_WARNING
from sims4modguard.known_patterns import KNOWN_SAFE_SCRIPTS


def make_ts4script(name: str, py_source: str, tmp_dir: Path) -> Path:
    """Create a synthetic .ts4script (ZIP containing a .py file)."""
    path = tmp_dir / name
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name.replace(".ts4script", ".py"), py_source)
    path.write_bytes(buf.getvalue())
    return path


class TestScanner:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── Detection tests ───────────────────────────────────────────────────

    def test_detects_inject_load_data(self):
        """inject_load_data_into_class_instances is a critical broken pattern."""
        make_ts4script(
            "broken_inject.ts4script",
            "inject_load_data_into_class_instances(some_class, 'attr', value)",
            self.tmp,
        )
        results = scan_all_scripts(self.tmp)
        critical = [r for r in results if r.severity == SEVERITY_CRITICAL]
        assert len(critical) == 1
        assert critical[0].name == "broken_inject.ts4script"

    def test_detects_has_tunable_reference(self):
        """HasTunableReference is a known broken API."""
        make_ts4script(
            "broken_tunable.ts4script",
            "class MyMod(HasTunableReference):\n    pass",
            self.tmp,
        )
        results = scan_all_scripts(self.tmp)
        critical = [r for r in results if r.severity == SEVERITY_CRITICAL]
        assert any(r.name == "broken_tunable.ts4script" for r in critical)

    def test_detects_lmsinjector(self):
        """Scumbumbo's lmsinjector pattern is broken post-1.105."""
        make_ts4script(
            "broken_lms.ts4script",
            "import lmsinjector\nlmsinjector.inject(SomeClass, 'method', my_func)",
            self.tmp,
        )
        results = scan_all_scripts(self.tmp)
        critical = [r for r in results if r.severity == SEVERITY_CRITICAL]
        assert any(r.name == "broken_lms.ts4script" for r in critical)

    def test_detects_wicked_whims_dependency(self):
        """add_wicked_attributes signals a WickedWhims dependency."""
        make_ts4script(
            "ww_dep.ts4script",
            "add_wicked_attributes(sim, 'ww_arousal', 0)",
            self.tmp,
        )
        results = scan_all_scripts(self.tmp)
        # Should be flagged as critical or warning (WW dep)
        flagged = [r for r in results if r.issues]
        assert any(r.name == "ww_dep.ts4script" for r in flagged)

    # ── Clean / whitelist tests ───────────────────────────────────────────

    def test_clean_script_passes(self):
        """A normal modern script with no broken patterns should be clean."""
        make_ts4script(
            "modern_mod.ts4script",
            "# Modern Sims 4 mod\ndef register_instance_manager():\n    pass",
            self.tmp,
        )
        results = scan_all_scripts(self.tmp)
        assert len(results) == 1
        assert results[0].is_clean
        assert not results[0].issues

    def test_multiple_scripts_scanned(self):
        """Scanner processes all .ts4script files in a folder."""
        for i in range(5):
            make_ts4script(f"mod_{i}.ts4script", f"# mod {i}\ndef run(): pass", self.tmp)
        results = scan_all_scripts(self.tmp)
        assert len(results) == 5

    def test_whitelisted_scripts_not_flagged(self):
        """Whitelisted mod names should never be flagged even if they look broken."""
        # mc_cmd_center is whitelisted — inject pattern should be ignored
        if "mc_cmd_center.ts4script" in KNOWN_SAFE_SCRIPTS:
            make_ts4script(
                "mc_cmd_center.ts4script",
                "inject_load_data_into_class_instances(cls, 'x', v)",
                self.tmp,
            )
            results = scan_all_scripts(self.tmp)
            critical = [r for r in results if r.severity == SEVERITY_CRITICAL]
            assert not any(r.name == "mc_cmd_center.ts4script" for r in critical)

    def test_corrupt_zip_handled(self):
        """A corrupt (non-ZIP) .ts4script should not crash the scanner."""
        bad = self.tmp / "corrupt.ts4script"
        bad.write_bytes(b"this is not a zip file at all")
        results = scan_all_scripts(self.tmp)
        # Should complete without exception; corrupt file gets its own result
        names = [r.name for r in results]
        assert "corrupt.ts4script" in names

    def test_empty_zip_handled(self):
        """An empty ZIP .ts4script should not crash the scanner."""
        empty = self.tmp / "empty.ts4script"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w"):
            pass
        empty.write_bytes(buf.getvalue())
        results = scan_all_scripts(self.tmp)
        assert "empty.ts4script" in [r.name for r in results]

    def test_results_sorted_critical_first(self):
        """Critical results should come before clean results when sorted."""
        make_ts4script("aaa_clean.ts4script", "def run(): pass", self.tmp)
        make_ts4script(
            "zzz_broken.ts4script",
            "inject_load_data_into_class_instances(cls, 'x', v)",
            self.tmp,
        )
        results = scan_all_scripts(self.tmp)
        sorted_results = sorted(
            results, key=lambda x: (0 if x.severity == SEVERITY_CRITICAL else 1, x.name)
        )
        assert sorted_results[0].name == "zzz_broken.ts4script"
        assert sorted_results[1].name == "aaa_clean.ts4script"
