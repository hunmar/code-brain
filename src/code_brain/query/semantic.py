from code_brain.ingestion.cognee_adapter import CogneeAdapter


class SemanticQueryEngine:
    def __init__(self, adapter: CogneeAdapter):
        self._adapter = adapter

    async def ask(self, question: str) -> list[dict]:
        return await self._adapter.search(
            question,
            search_type="GRAPH_COMPLETION",
        )

    async def explain(self, symbol_name: str,
                      structural_info: dict | None = None) -> str:
        semantic = await self._adapter.search(
            f"Explain the purpose and context of {symbol_name}",
            search_type="GRAPH_SUMMARY_COMPLETION",
        )

        parts = [f"# {symbol_name}"]
        if structural_info:
            parts.append(
                f"\nLocation: {structural_info.get('file_path', '?')}"
                f":{structural_info.get('line', '?')}"
            )
            parts.append(f"Kind: {structural_info.get('kind', '?')}")

        if semantic:
            parts.append("\n## Semantic Context")
            for item in semantic:
                parts.append(f"- {item.get('text', str(item))}")

        return "\n".join(parts)

    async def search_fast(self, query: str, top_k: int = 10) -> list[dict]:
        return await self._adapter.search(
            query,
            search_type="CHUNKS",
            top_k=top_k,
        )

    async def reason(self, question: str) -> list[dict]:
        return await self._adapter.search(
            question,
            search_type="GRAPH_COMPLETION_COT",
        )

    async def review_diff(self, diff: str) -> list[dict]:
        return await self._adapter.search(
            f"Review this code change for potential issues:\n\n{diff}",
            search_type="CODING_RULES",
        )
