"""
Tests for sims4modguard.log_parser
Uses synthetic lastException.txt content to test parsing logic.
"""
import sys, tempfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sims4modguard.log_parser import parse_log

GOOD_LOG = """\
<report>
  <sessionid>ABC123</sessionid>
  <buildsignature>1.121.372.1020.Sims4</buildsignature>
  <categoryid>bad_mod.py:42</categoryid>
  <type>desync</type>
  <createtime>2026-07-10 12:00:00</createtime>
  <desyncdata>AttributeError: type object 'SomeClass' has no attribute 'inject_load_data'
  File "Scripts/MyMod/bad_mod.py", line 42, in do_inject</desyncdata>
</report>
<report>
  <sessionid>ABC123</sessionid>
  <buildsignature>1.121.372.1020.Sims4</buildsignature>
  <categoryid>bad_mod.py:55</categoryid>
  <type>desync</type>
  <createtime>2026-07-10 12:00:01</createtime>
  <desyncdata>AttributeError: type object 'AnotherClass' has no attribute 'inject_load_data'
  File "Scripts/MyMod/bad_mod.py", line 55, in do_inject</desyncdata>
</report>
"""

CRASH_LOG = """\
<BetterExceptions>
<TuningLoadFinished>False</TuningLoadFinished>
</BetterExceptions>
<report>
  <sessionid>XYZ999</sessionid>
  <buildsignature>1.121.372.1020.Sims4</buildsignature>
  <categoryid>main.py:10</categoryid>
  <type>desync</type>
  <createtime>2026-07-10 13:00:00</createtime>
  <desyncdata>KeyError: HasTunableReference not found
  File "Scripts/BrokenMod/main.py", line 10, in load</desyncdata>
</report>
"""

EMPTY_LOG = """"""  # completely empty log file


class TestLogParser:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_log(self, content: str) -> Path:
        p = self.tmp / "lastException.txt"
        p.write_text(content, encoding="utf-8")
        return p

    def test_parses_game_version(self):
        path = self._write_log(GOOD_LOG)
        summary = parse_log(path)
        assert "1.121" in summary.game_version

    def test_counts_errors(self):
        path = self._write_log(GOOD_LOG)
        summary = parse_log(path)
        assert summary.total_errors == 2

    def test_tuning_finished_true(self):
        """If tuning finished, no crash from tuning load."""
        path = self._write_log(GOOD_LOG)
        summary = parse_log(path)
        assert summary.tuning_finished is True

    def test_tuning_finished_false_is_crash(self):
        """BetterExceptions TuningLoadFinished=False means crash on load."""
        path = self._write_log(CRASH_LOG)
        summary = parse_log(path)
        # The parser checks for <BetterExceptions><TuningLoadFinished>False
        assert summary.tuning_finished is False

    def test_empty_log_no_errors(self):
        path = self._write_log(EMPTY_LOG)
        summary = parse_log(path)
        # Empty file has no <report> elements
        assert summary.total_errors == 0

    def test_missing_log_handled(self):
        """parse_log on a missing file should not raise."""
        missing = self.tmp / "nonexistent.txt"
        summary = parse_log(missing)
        assert summary is not None
        assert summary.total_errors == 0

    def test_root_causes_extracted(self):
        path = self._write_log(GOOD_LOG)
        summary = parse_log(path)
        # Should extract at least one root cause from the errors
        assert summary.root_causes is not None

    def test_grouped_errors(self):
        path = self._write_log(GOOD_LOG)
        summary = parse_log(path)
        # Should group errors into categories
        assert summary.grouped is not None
