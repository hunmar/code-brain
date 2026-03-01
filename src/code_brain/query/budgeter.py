# code-brain/src/code_brain/query/budgeter.py
from dataclasses import dataclass


@dataclass
class ContextEntry:
    name: str
    kind: str
    file_path: str
    line: int
    signature: str
    summary: str = ""
    body: str = ""
    deps: list[str] | None = None
    git_info: str = ""


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4 + 1


class ContextBudgeter:
    def format(self, entries: list[ContextEntry], token_budget: int) -> str:
        if not entries:
            return ""

        if token_budget >= 20000:
            depth = "full"
        elif token_budget >= 5000:
            depth = "medium"
        else:
            depth = "compact"

        output_parts: list[str] = []
        tokens_used = 0

        for entry in entries:
            formatted = self._format_entry(entry, depth)
            entry_tokens = _estimate_tokens(formatted)
            if tokens_used + entry_tokens > token_budget:
                break
            output_parts.append(formatted)
            tokens_used += entry_tokens

        return "\n".join(output_parts)

    def _format_entry(self, entry: ContextEntry, depth: str) -> str:
        parts = [f"{entry.kind} {entry.name} ({entry.file_path}:{entry.line})"]

        if entry.signature:
            parts.append(f"  {entry.signature}")

        if depth in ("medium", "full") and entry.summary:
            parts.append(f"  Summary: {entry.summary}")

        if depth in ("medium", "full") and entry.deps:
            parts.append(f"  Deps: {', '.join(entry.deps)}")

        if depth == "full" and entry.body:
            parts.append(f"  Body:\n    {entry.body}")

        if depth == "full" and entry.git_info:
            parts.append(f"  Git: {entry.git_info}")

        return "\n".join(parts)
