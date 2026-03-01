import subprocess
import pytest
from pathlib import Path
from code_brain.ingestion.git_analyzer import (
    GitAnalyzer, HotSpot, CoChange,
)


@pytest.fixture
def git_repo(tmp_path):
    """Create a small git repo with some history."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, capture_output=True
    )
    # First commit: create files
    (tmp_path / "a.py").write_text("class A: pass")
    (tmp_path / "b.py").write_text("class B: pass")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path, capture_output=True
    )
    # Second commit: modify a.py and b.py together
    (tmp_path / "a.py").write_text("class A:\n    x = 1")
    (tmp_path / "b.py").write_text("class B:\n    y = 1")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "update both"],
        cwd=tmp_path, capture_output=True
    )
    # Third commit: modify only a.py
    (tmp_path / "a.py").write_text("class A:\n    x = 2")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "update a only"],
        cwd=tmp_path, capture_output=True
    )
    return tmp_path


def test_hot_spots(git_repo):
    analyzer = GitAnalyzer(git_repo)
    spots = analyzer.hot_spots(limit=10)
    assert len(spots) >= 1
    assert isinstance(spots[0], HotSpot)
    # a.py changed more than b.py
    names = [s.file_path for s in spots]
    assert "a.py" in names


def test_co_changes(git_repo):
    analyzer = GitAnalyzer(git_repo)
    pairs = analyzer.co_changes(min_count=1)
    assert len(pairs) >= 1
    assert isinstance(pairs[0], CoChange)
    files_in_pair = {pairs[0].file_a, pairs[0].file_b}
    assert "a.py" in files_in_pair
    assert "b.py" in files_in_pair
