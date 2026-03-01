# code-brain/src/code_brain/config.py
import os
from dataclasses import dataclass, field
from pathlib import Path


def find_project_root(start: Path) -> Path | None:
    current = start.resolve()
    while current != current.parent:
        if (current / ".code-brain").is_dir():
            return current
        if (current / ".git").is_dir():
            return current
        current = current.parent
    return None


@dataclass
class CodeBrainConfig:
    project_root: Path

    neo4j_uri: str = field(default_factory=lambda: os.environ.get(
        "CODE_BRAIN_NEO4J_URI", "bolt://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.environ.get(
        "CODE_BRAIN_NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.environ.get(
        "CODE_BRAIN_NEO4J_PASSWORD", "codebrain"))
    qdrant_url: str = field(default_factory=lambda: os.environ.get(
        "CODE_BRAIN_QDRANT_URL", "http://localhost:6333"))

    @property
    def code_brain_dir(self) -> Path:
        return self.project_root / ".code-brain"

    @property
    def graph_path(self) -> Path:
        return self.code_brain_dir / "graph.pkl"

    @property
    def ast_index_db_path(self) -> Path:
        return self.project_root / ".ast-index" / "db.sqlite3"

    def ensure_dirs(self) -> None:
        self.code_brain_dir.mkdir(parents=True, exist_ok=True)
