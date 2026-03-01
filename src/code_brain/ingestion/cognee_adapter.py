import cognee
from cognee.modules.search.types.SearchType import SearchType

from code_brain.ingestion.ast_index import Symbol, ModuleDep


def _resolve_search_type(search_type: str | None) -> SearchType:
    if not search_type:
        return SearchType.GRAPH_COMPLETION

    candidate = str(search_type).upper()
    if candidate in SearchType.__members__:
        return SearchType[candidate]

    return SearchType.GRAPH_COMPLETION


class CogneeAdapter:
    def _format_symbol_doc(self, symbol: Symbol) -> str:
        return (
            f"Code symbol: {symbol.name}\n"
            f"Kind: {symbol.kind}\n"
            f"File: {symbol.file_path}:{symbol.line}\n"
            f"Signature: {symbol.signature}\n"
        )

    def _format_module_doc(self, source: str, target: str, kind: str) -> str:
        return f"Module {source} depends on {target} (relationship: {kind})"

    async def ingest_symbols(self, symbols: list[Symbol]) -> None:
        for sym in symbols:
            doc = self._format_symbol_doc(sym)
            await cognee.add(doc, dataset_name="code_structure")
        await cognee.cognify()

    async def ingest_module_deps(self, deps: list[ModuleDep]) -> None:
        for dep in deps:
            doc = self._format_module_doc(dep.source, dep.target, dep.kind)
            await cognee.add(doc, dataset_name="module_deps")
        await cognee.cognify()

    async def ingest_docs(self, doc_contents: list[tuple[str, str]]) -> None:
        for filename, content in doc_contents:
            await cognee.add(
                f"Document: {filename}\n\n{content}",
                dataset_name="documentation",
            )
        await cognee.cognify()

    async def search(
        self,
        query: str,
        search_type: str = "GRAPH_COMPLETION",
        top_k: int = 10,
    ) -> list[dict]:
        query_type = _resolve_search_type(search_type)
        results = await cognee.search(
            query_text=query,
            query_type=query_type,
            top_k=top_k,
        )
        return [{"text": str(r)} for r in results]
