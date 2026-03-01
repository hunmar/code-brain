"""Tests for the git history analyzer (hot spots + co-changes)."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from code_brain.ingestion.git_analyzer import (
    GitAnalyzer,
    FileHotSpot,
    CoChangePair,
)


# ── fixtures ──────────────────────────────────────────────────────────────

SAMPLE_LOG_NUMSTAT = """\
abc1234
3\t1\tsrc/models/user.py
10\t2\tsrc/services/auth.py

bcd2345
5\t0\tsrc/models/user.py
1\t1\tsrc/repos/user_repo.py

cde3456
20\t5\tsrc/services/auth.py
2\t0\tsrc/repos/user_repo.py
1\t0\tsrc/models/user.py
"""

SAMPLE_LOG_NAME_ONLY = """\
abc1234
src/models/user.py
src/services/auth.py

bcd2345
src/models/user.py
src/repos/user_repo.py

cde3456
src/services/auth.py
src/repos/user_repo.py
src/models/user.py
"""


@pytest.fixture
def analyzer(tmp_path: Path) -> GitAnalyzer:
    """Create a GitAnalyzer pointed at a temporary directory."""
    return GitAnalyzer(tmp_path)


# ── FileHotSpot dataclass ────────────────────────────────────────────────

class TestFileHotSpot:
    def test_fields(self):
        hs = FileHotSpot(
            path="src/foo.py", commits=5, lines_added=20, lines_removed=3
        )
        assert hs.path == "src/foo.py"
        assert hs.commits == 5
        assert hs.lines_added == 20
        assert hs.lines_removed == 3

    def test_churn(self):
        hs = FileHotSpot(path="a.py", commits=1, lines_added=10, lines_removed=4)
        assert hs.churn == 14


# ── CoChangePair dataclass ───────────────────────────────────────────────

class TestCoChangePair:
    def test_fields(self):
        cc = CoChangePair(file_a="a.py", file_b="b.py", count=3)
        assert cc.file_a == "a.py"
        assert cc.file_b == "b.py"
        assert cc.count == 3


# ── hot_spots ─────────────────────────────────────────────────────────────

class TestHotSpots:
    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_returns_sorted_by_commits_desc(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(
            stdout=SAMPLE_LOG_NUMSTAT, returncode=0
        )
        spots = analyzer.hot_spots()
        assert len(spots) == 3
        # user.py has 3 commits, auth.py has 2, user_repo.py has 2
        assert spots[0].path == "src/models/user.py"
        assert spots[0].commits == 3

    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_limits_results(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(
            stdout=SAMPLE_LOG_NUMSTAT, returncode=0
        )
        spots = analyzer.hot_spots(n=2)
        assert len(spots) == 2

    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_accumulates_line_counts(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(
            stdout=SAMPLE_LOG_NUMSTAT, returncode=0
        )
        spots = analyzer.hot_spots()
        user = next(s for s in spots if s.path == "src/models/user.py")
        # 3+5+1 = 9 added, 1+0+0 = 1 removed
        assert user.lines_added == 9
        assert user.lines_removed == 1
        assert user.churn == 10

    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_empty_log(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        spots = analyzer.hot_spots()
        assert spots == []

    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_passes_correct_git_command(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        analyzer.hot_spots()
        args = mock_run.call_args
        cmd = args[0][0]
        assert "git" in cmd
        assert "log" in cmd
        assert "--numstat" in cmd


# ── co_changes ────────────────────────────────────────────────────────────

class TestCoChanges:
    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_returns_pairs_sorted_by_count_desc(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(
            stdout=SAMPLE_LOG_NAME_ONLY, returncode=0
        )
        pairs = analyzer.co_changes(min_count=1)
        assert len(pairs) > 0
        # All three pairs appear: (user, auth)=2, (user, repo)=2, (auth, repo)=1
        # But with min_count=1, all three appear
        counts = [p.count for p in pairs]
        assert counts == sorted(counts, reverse=True)

    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_filters_by_min_count(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(
            stdout=SAMPLE_LOG_NAME_ONLY, returncode=0
        )
        pairs = analyzer.co_changes(min_count=2)
        for p in pairs:
            assert p.count >= 2

    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_pair_ordering_is_canonical(self, mock_run, analyzer):
        """file_a < file_b alphabetically, so pairs are unique."""
        mock_run.return_value = MagicMock(
            stdout=SAMPLE_LOG_NAME_ONLY, returncode=0
        )
        pairs = analyzer.co_changes(min_count=1)
        for p in pairs:
            assert p.file_a < p.file_b

    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_empty_log(self, mock_run, analyzer):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        pairs = analyzer.co_changes()
        assert pairs == []

    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_single_file_commits_produce_no_pairs(self, mock_run, analyzer):
        log = "abc1234\nsrc/only.py\n\n"
        mock_run.return_value = MagicMock(stdout=log, returncode=0)
        pairs = analyzer.co_changes(min_count=1)
        assert pairs == []


# ── error handling ────────────────────────────────────────────────────────

class TestErrorHandling:
    @patch("code_brain.ingestion.git_analyzer.subprocess.run")
    def test_non_git_repo_raises(self, mock_run, analyzer):
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        with pytest.raises(subprocess.CalledProcessError):
            analyzer.hot_spots()
