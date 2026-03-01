"""Semantic query engine with evidence-backed responses."""

from __future__ import annotations

import re

from code_brain.ingestion.cognee_adapter import CogneeAdapter

# Pattern to extract file_path:line references from text
_FILE_LINE_RE = re.compile(r"(?:^|[\s(])([a-zA-Z0-9_./-]+\.\w+):(\d+)")
# Pattern to extract symbol names following common code patterns
_SYMBOL_RE = re.compile(r"\b(?:class|def|function|symbol)\s+(\w+)", re.IGNORECASE)


def _extract_evidence(results: list[dict]) -> list[dict]:
    """Parse structural anchors (symbol, file_path, line) from result text."""
    evidence: list[dict] = []
    seen: set[tuple] = set()
    for item in results:
        text = item.get("text", "")
        for match in _FILE_LINE_RE.finditer(text):
            fp, line = match.group(1), int(match.group(2))
            key = (fp, line)
            if key not in seen:
                seen.add(key)
                # Try to find a symbol name nearby in the same text
                sym_match = _SYMBOL_RE.search(text)
                entry: dict = {"file_path": fp, "line": line}
                if sym_match:
                    entry["symbol"] = sym_match.group(1)
                evidence.append(entry)
    return evidence


def _score_confidence(evidence: list[dict]) -> str:
    """Score confidence based on structural anchor count."""
    if len(evidence) >= 2:
        return "high"
    if len(evidence) == 1:
        return "medium"
    return "low"


def _build_response(
    answer: str,
    results: list[dict],
    *,
    degraded: bool = False,
    warnings: list[str] | None = None,
) -> dict:
    """Build a semantic response conforming to the evidence contract."""
    evidence = _extract_evidence(results)
    return {
        "answer": answer,
        "evidence": evidence,
        "confidence": _score_confidence(evidence),
        "degraded": degraded,
        "warnings": warnings or [],
    }


class SemanticQueryEngine:
    def __init__(self, adapter: CogneeAdapter):
        self._adapter = adapter

    async def ask(self, question: str) -> dict:
        results = await self._adapter.search(
            question,
            search_type="GRAPH_COMPLETION",
        )
        answer = "\n".join(item.get("text", str(item)) for item in results)
        return _build_response(answer, results)

    async def explain(
        self,
        symbol_name: str,
        structural_info: dict | None = None,
    ) -> dict:
        semantic = await self._adapter.search(
            f"Explain the purpose and context of {symbol_name}",
            search_type="GRAPH_SUMMARY_COMPLETION",
        )

        parts = [f"# {symbol_name}"]
        evidence: list[dict] = []

        if structural_info:
            fp = structural_info.get("file_path", "?")
            line = structural_info.get("line", "?")
            parts.append(f"\nLocation: {fp}:{line}")
            parts.append(f"Kind: {structural_info.get('kind', '?')}")
            if fp != "?" and line != "?":
                entry: dict = {"file_path": fp, "line": line}
                sym_name = structural_info.get("name")
                if sym_name:
                    entry["symbol"] = sym_name
                evidence.append(entry)

        if semantic:
            parts.append("\n## Semantic Context")
            for item in semantic:
                parts.append(f"- {item.get('text', str(item))}")
            evidence.extend(_extract_evidence(semantic))

        answer = "\n".join(parts)
        return {
            "answer": answer,
            "evidence": evidence,
            "confidence": _score_confidence(evidence),
            "degraded": False,
            "warnings": [],
        }

    async def search_fast(self, query: str, top_k: int = 10) -> dict:
        results = await self._adapter.search(
            query,
            search_type="CHUNKS",
            top_k=top_k,
        )
        answer = "\n".join(item.get("text", str(item)) for item in results)
        return _build_response(answer, results)

    async def reason(self, question: str) -> dict:
        results = await self._adapter.search(
            question,
            search_type="GRAPH_COMPLETION_COT",
        )
        answer = "\n".join(item.get("text", str(item)) for item in results)
        return _build_response(answer, results)

    async def review_diff(self, diff: str) -> dict:
        results = await self._adapter.search(
            f"Review this code change for potential issues:\n\n{diff}",
            search_type="CODING_RULES",
        )
        answer = "\n".join(item.get("text", str(item)) for item in results)
        return _build_response(answer, results)
