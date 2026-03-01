"""Query router with command classification.

Classifies incoming queries as known commands (map, hotspots, arch,
explain, search) or routes natural-language questions to the semantic
query engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class QueryType(Enum):
    MAP = "map"
    HOTSPOTS = "hotspots"
    ARCH = "arch"
    EXPLAIN = "explain"
    SEARCH = "search"
    SEMANTIC = "semantic"


@dataclass
class RoutedQuery:
    query_type: QueryType
    raw_query: str
    target: str | None = None


# Ordered list of (QueryType, compiled regex) for command matching.
_COMMAND_PATTERNS: list[tuple[QueryType, re.Pattern[str]]] = [
    (QueryType.MAP, re.compile(r"^map\b", re.IGNORECASE)),
    (QueryType.HOTSPOTS, re.compile(r"^hotspots?\b", re.IGNORECASE)),
    (QueryType.ARCH, re.compile(r"^arch(?:itecture)?\b", re.IGNORECASE)),
    (QueryType.EXPLAIN, re.compile(r"^explain\b", re.IGNORECASE)),
    (QueryType.SEARCH, re.compile(r"^search\b", re.IGNORECASE)),
]


def route_query(raw_query: str) -> RoutedQuery:
    """Classify *raw_query* and return a ``RoutedQuery``."""
    query = raw_query.strip()

    for query_type, pattern in _COMMAND_PATTERNS:
        match = pattern.match(query)
        if match:
            target = query[match.end() :].strip() or None
            return RoutedQuery(
                query_type=query_type,
                raw_query=raw_query,
                target=target,
            )

    # Default: treat as natural-language → semantic.
    return RoutedQuery(query_type=QueryType.SEMANTIC, raw_query=raw_query)
