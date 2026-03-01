import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path


@dataclass(frozen=True)
class HotSpot:
    file_path: str
    change_count: int


@dataclass(frozen=True)
class CoChange:
    file_a: str
    file_b: str
    count: int


class GitAnalyzer:
    def __init__(self, project_root: Path):
        self._root = project_root

    def _run_git(self, *args: str) -> str:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self._root,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def hot_spots(self, since: str = "6 months ago",
                  limit: int = 20) -> list[HotSpot]:
        log = self._run_git(
            "log", f"--since={since}", "--pretty=format:", "--name-only"
        )
        counts = Counter(
            line for line in log.strip().split("\n") if line.strip()
        )
        return [
            HotSpot(file_path=f, change_count=c)
            for f, c in counts.most_common(limit)
        ]

    def co_changes(self, since: str = "6 months ago",
                   min_count: int = 2) -> list[CoChange]:
        log = self._run_git(
            "log", f"--since={since}", "--pretty=format:---", "--name-only"
        )
        pair_counts: Counter = Counter()
        for commit_block in log.split("---"):
            files = [
                line.strip()
                for line in commit_block.strip().split("\n")
                if line.strip()
            ]
            for a, b in combinations(sorted(set(files)), 2):
                pair_counts[(a, b)] += 1

        return [
            CoChange(file_a=a, file_b=b, count=c)
            for (a, b), c in pair_counts.most_common()
            if c >= min_count
        ]
