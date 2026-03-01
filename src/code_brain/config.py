"""Project configuration with environment variable overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_NEO4J_URI = "bolt://localhost:7687"
_DEFAULT_NEO4J_USER = "neo4j"
_DEFAULT_NEO4J_PASSWORD = "codebrain"
_DEFAULT_QDRANT_URL = "http://localhost:6333"
_DEFAULT_TOKEN_BUDGET = 10_000


def _default_ast_db(repo_root: Path) -> Path:
    return repo_root / ".code_brain" / "ast.db"


@dataclass(frozen=True)
class ProjectConfig:
    """Immutable project configuration.

    Construct directly for full control, or use ``from_repo()``
    to pick up ``CODE_BRAIN_*`` environment-variable overrides.
    """

    repo_root: Path
    ast_db_path: Path | None = None
    neo4j_uri: str = _DEFAULT_NEO4J_URI
    neo4j_user: str = _DEFAULT_NEO4J_USER
    neo4j_password: str = _DEFAULT_NEO4J_PASSWORD
    qdrant_url: str = _DEFAULT_QDRANT_URL
    token_budget: int = _DEFAULT_TOKEN_BUDGET

    def __post_init__(self) -> None:
        if self.ast_db_path is None:
            object.__setattr__(self, "ast_db_path", _default_ast_db(self.repo_root))

    @property
    def data_dir(self) -> Path:
        return self.repo_root / ".code_brain"

    @classmethod
    def from_repo(cls, repo_root: Path) -> ProjectConfig:
        """Create config from a repo path, reading CODE_BRAIN_* env vars."""
        neo4j_uri = os.environ.get("CODE_BRAIN_NEO4J_URI", _DEFAULT_NEO4J_URI)
        neo4j_user = os.environ.get("CODE_BRAIN_NEO4J_USER", _DEFAULT_NEO4J_USER)
        neo4j_password = os.environ.get("CODE_BRAIN_NEO4J_PASSWORD", _DEFAULT_NEO4J_PASSWORD)
        qdrant_url = os.environ.get("CODE_BRAIN_QDRANT_URL", _DEFAULT_QDRANT_URL)
        token_budget_str = os.environ.get("CODE_BRAIN_TOKEN_BUDGET")
        token_budget = int(token_budget_str) if token_budget_str else _DEFAULT_TOKEN_BUDGET

        return cls(
            repo_root=repo_root,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            qdrant_url=qdrant_url,
            token_budget=token_budget,
        )
