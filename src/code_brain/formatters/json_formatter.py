"""JSON formatter for code-brain query results."""

from __future__ import annotations

import json
from dataclasses import asdict

from code_brain.models import QueryResult


class JsonFormatter:
    """Formats a QueryResult as a JSON string."""

    def __init__(self, indent: int | None = 2) -> None:
        self.indent = indent

    def format(self, result: QueryResult) -> str:
        return json.dumps(asdict(result), indent=self.indent)
