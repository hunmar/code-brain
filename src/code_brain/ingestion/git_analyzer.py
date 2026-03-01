"""Git history analyzer – extracts hot spots and co-change pairs."""

from __future__ import annotations

import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileHotSpot:
    """A file ranked by change frequency and churn."""

    path: str
    commits: int
    lines_added: int
    lines_removed: int

    @property
    def churn(self) -> int:
        """Total lines touched (added + removed)."""
        return self.lines_added + self.lines_removed


@dataclass(frozen=True, slots=True)
class CoChangePair:
    """Two files that are frequently changed in the same commit."""

    file_a: str
    file_b: str
    count: int


class GitAnalyzer:
    """Analyses git history of a repository for hot spots and co-changes."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    # ── public API ────────────────────────────────────────────────────

    def hot_spots(self, n: int = 10) -> list[FileHotSpot]:
        """Return the *n* most frequently changed files, sorted by commit count descending."""
        raw = self._git(
            "log", "--pretty=format:%h", "--numstat",
        )
        if not raw.strip():
            return []

        commit_counts: Counter[str] = Counter()
        added: defaultdict[str, int] = defaultdict(int)
        removed: defaultdict[str, int] = defaultdict(int)

        current_hash: str | None = None
        seen_in_commit: set[str] = set()

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                current_hash = None
                seen_in_commit = set()
                continue

            parts = line.split("\t")
            if len(parts) == 1:
                # commit hash line
                current_hash = parts[0]
                seen_in_commit = set()
                continue

            if len(parts) == 3:
                add_str, rm_str, path = parts
                # binary files show '-' for stats – skip them
                if add_str == "-" or rm_str == "-":
                    continue
                added[path] += int(add_str)
                removed[path] += int(rm_str)
                if path not in seen_in_commit:
                    commit_counts[path] += 1
                    seen_in_commit.add(path)

        spots = [
            FileHotSpot(
                path=path,
                commits=commit_counts[path],
                lines_added=added[path],
                lines_removed=removed[path],
            )
            for path in commit_counts
        ]
        spots.sort(key=lambda s: s.commits, reverse=True)
        return spots[:n]

    def co_changes(self, min_count: int = 2) -> list[CoChangePair]:
        """Return pairs of files that change together, filtered by *min_count*."""
        raw = self._git(
            "log", "--pretty=format:%h", "--name-only",
        )
        if not raw.strip():
            return []

        pair_counts: Counter[tuple[str, str]] = Counter()

        files_in_commit: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                # end of commit block – generate pairs
                for a, b in combinations(sorted(set(files_in_commit)), 2):
                    pair_counts[(a, b)] += 1
                files_in_commit = []
                continue

            parts = line.split("\t")
            if len(parts) == 1 and " " not in line and "/" in line:
                # file path
                files_in_commit.append(line)
            elif len(parts) == 1:
                # commit hash – flush previous commit if needed
                if files_in_commit:
                    for a, b in combinations(sorted(set(files_in_commit)), 2):
                        pair_counts[(a, b)] += 1
                files_in_commit = []

        # flush trailing commit
        if files_in_commit:
            for a, b in combinations(sorted(set(files_in_commit)), 2):
                pair_counts[(a, b)] += 1

        pairs = [
            CoChangePair(file_a=a, file_b=b, count=cnt)
            for (a, b), cnt in pair_counts.items()
            if cnt >= min_count
        ]
        pairs.sort(key=lambda p: p.count, reverse=True)
        return pairs

    # ── helpers ───────────────────────────────────────────────────────

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
