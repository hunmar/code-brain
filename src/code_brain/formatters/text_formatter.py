"""Plain-text formatter for code-brain query results."""

from __future__ import annotations

from code_brain.models import QueryResult


class TextFormatter:
    """Formats a QueryResult as human-readable plain text."""

    def __init__(
        self,
        max_snippet_lines: int = 10,
        show_scores: bool = True,
    ) -> None:
        self.max_snippet_lines = max_snippet_lines
        self.show_scores = show_scores

    def format(self, result: QueryResult) -> str:
        lines: list[str] = []
        lines.append(f"Query: {result.query}")
        lines.append(f"Found {result.total_count} result(s)")

        if result.elapsed_ms is not None:
            lines.append(f"Time: {result.elapsed_ms:.1f}ms")

        lines.append("")

        for i, item in enumerate(result.items, 1):
            header = f"{i}. [{item.kind}] {item.symbol}"
            if self.show_scores:
                header += f" (score: {item.score:.2f})"
            lines.append(header)

            location = f"   {item.file_path}"
            if item.line_number is not None:
                location += f":{item.line_number}"
            lines.append(location)

            if item.snippet:
                snippet_lines = item.snippet.splitlines()
                if len(snippet_lines) > self.max_snippet_lines:
                    snippet_lines = snippet_lines[: self.max_snippet_lines]
                    snippet_lines.append("...")
                for sl in snippet_lines:
                    lines.append(f"   {sl}")

            lines.append("")

        return "\n".join(lines)
