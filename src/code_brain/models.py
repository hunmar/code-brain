"""Shared data models for code-brain."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResultItem:
    """A single code-intelligence query result."""

    file_path: str
    symbol: str
    kind: str  # "function", "class", "module", etc.
    snippet: str
    score: float
    line_number: int | None = None
    metadata: dict | None = None


@dataclass
class QueryResult:
    """Container for a set of query results."""

    query: str
    items: list[ResultItem] = field(default_factory=list)
    total_count: int = 0
    elapsed_ms: float | None = None
