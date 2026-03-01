from code_brain.ingestion.cognee_adapter import CogneeAdapter


class SemanticQueryEngine:
    def __init__(self, adapter: CogneeAdapter):
        self._adapter = adapter

    async def ask(self, question: str) -> list[dict]:
        return await self._adapter.search(question)

    async def explain(self, symbol_name: str,
                      structural_info: dict | None = None) -> str:
        semantic = await self._adapter.search(
            f"Explain the purpose and context of {symbol_name}"
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
