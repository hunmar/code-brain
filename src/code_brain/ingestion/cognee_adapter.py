import logging

import cognee
from cognee.modules.search.types.SearchType import SearchType

from code_brain.ingestion.ast_index import Symbol, ModuleDep

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

class SemanticError(Exception):
    """Base for all semantic-layer errors."""


class SemanticUnavailableError(SemanticError):
    """Raised when semantic backends (Neo4j, Qdrant) are unreachable."""


class SemanticQueryFailedError(SemanticError):
    """Raised when a semantic query executes but returns an error."""


class SemanticValidationError(SemanticError):
    """Raised when input to a semantic operation fails validation."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEARCH_TYPE_BY_VALUE: dict[str, SearchType] = {
    member.value.upper(): member for member in SearchType
}


def _resolve_search_type(search_type: str | None) -> SearchType:
    """Resolve a string to a ``SearchType`` enum member.

    Supports both enum *names* (``SearchType.__members__``) and enum *values*.
    Falls back to ``GRAPH_COMPLETION`` for unknown inputs.
    """
    if not search_type:
        return SearchType.GRAPH_COMPLETION

    candidate = str(search_type).upper()

    # Try by name first
    if candidate in SearchType.__members__:
        return SearchType[candidate]

    # Try by value
    if candidate in _SEARCH_TYPE_BY_VALUE:
        return _SEARCH_TYPE_BY_VALUE[candidate]

    return SearchType.GRAPH_COMPLETION


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

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
        if not symbols:
            return
        docs = [self._format_symbol_doc(sym) for sym in symbols]
        await cognee.add(docs, dataset_name="code_symbols")

    async def ingest_module_deps(self, deps: list[ModuleDep]) -> None:
        if not deps:
            return
        docs = [self._format_module_doc(d.source, d.target, d.kind) for d in deps]
        await cognee.add(docs, dataset_name="code_relationships")

    async def ingest_docs(self, doc_contents: list[tuple[str, str]]) -> None:
        if not doc_contents:
            return
        docs = [f"Document: {fn}\n\n{content}" for fn, content in doc_contents]
        await cognee.add(docs, dataset_name="documentation")

    async def finalize(self, run_memify: bool = True) -> None:
        """Run cognify (required) and optionally memify after all ingestion."""
        await cognee.cognify()
        if run_memify:
            try:
                await cognee.memify()
            except Exception:
                logger.warning("memify failed (non-fatal)", exc_info=True)

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
