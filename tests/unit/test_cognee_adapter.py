from unittest.mock import AsyncMock, patch
import pytest
from code_brain.ingestion.cognee_adapter import (
    CogneeAdapter,
    SemanticError,
    SemanticQueryFailedError,
    SemanticUnavailableError,
    SemanticValidationError,
    _resolve_search_type,
)
from code_brain.ingestion.ast_index import Symbol, ModuleDep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_symbols():
    return [
        Symbol(1, "User", "class", "models/user.py", 1, "class User"),
        Symbol(2, "AuthService", "class", "services/auth.py", 3, "class AuthService"),
    ]


@pytest.fixture
def sample_deps():
    return [
        ModuleDep("services", "models", "import"),
        ModuleDep("api", "services", "import"),
    ]


@pytest.fixture
def adapter():
    return CogneeAdapter()


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

def test_error_hierarchy():
    assert issubclass(SemanticUnavailableError, SemanticError)
    assert issubclass(SemanticQueryFailedError, SemanticError)
    assert issubclass(SemanticValidationError, SemanticError)


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def test_format_symbol_document(adapter, sample_symbols):
    doc = adapter._format_symbol_doc(sample_symbols[0])
    assert "User" in doc
    assert "class" in doc
    assert "models/user.py" in doc


def test_format_module_doc(adapter):
    doc = adapter._format_module_doc("services", "models", "import")
    assert "services" in doc
    assert "models" in doc


# ---------------------------------------------------------------------------
# Search type resolution
# ---------------------------------------------------------------------------

def test_resolve_search_type_by_name():
    from cognee.modules.search.types.SearchType import SearchType
    result = _resolve_search_type("GRAPH_COMPLETION")
    assert result == SearchType.GRAPH_COMPLETION


def test_resolve_search_type_by_value():
    from cognee.modules.search.types.SearchType import SearchType
    result = _resolve_search_type("CHUNKS")
    assert result == SearchType.CHUNKS


def test_resolve_search_type_case_insensitive():
    from cognee.modules.search.types.SearchType import SearchType
    result = _resolve_search_type("graph_completion")
    assert result == SearchType.GRAPH_COMPLETION


def test_resolve_search_type_none_defaults():
    from cognee.modules.search.types.SearchType import SearchType
    result = _resolve_search_type(None)
    assert result == SearchType.GRAPH_COMPLETION


def test_resolve_search_type_invalid_falls_back():
    from cognee.modules.search.types.SearchType import SearchType
    result = _resolve_search_type("NOT_A_TYPE")
    assert result == SearchType.GRAPH_COMPLETION


# ---------------------------------------------------------------------------
# Contract: batched ingest_symbols — single add call, no cognify
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_symbols_batches_add(adapter, sample_symbols):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        mock_cognee.cognify = AsyncMock()
        await adapter.ingest_symbols(sample_symbols)
        mock_cognee.add.assert_called_once()
        docs = mock_cognee.add.call_args.args[0]
        assert isinstance(docs, list)
        assert len(docs) == len(sample_symbols)
        mock_cognee.cognify.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_symbols_uses_code_symbols_dataset(adapter, sample_symbols):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        await adapter.ingest_symbols(sample_symbols)
        kwargs = mock_cognee.add.call_args.kwargs
        assert kwargs["dataset_name"] == "code_symbols"


@pytest.mark.asyncio
async def test_ingest_symbols_empty_is_noop(adapter):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        await adapter.ingest_symbols([])
        mock_cognee.add.assert_not_called()


# ---------------------------------------------------------------------------
# Contract: batched ingest_module_deps — single add call, no cognify
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_module_deps_batches_add(adapter, sample_deps):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        mock_cognee.cognify = AsyncMock()
        await adapter.ingest_module_deps(sample_deps)
        mock_cognee.add.assert_called_once()
        docs = mock_cognee.add.call_args.args[0]
        assert isinstance(docs, list)
        assert len(docs) == len(sample_deps)
        mock_cognee.cognify.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_module_deps_uses_code_relationships_dataset(adapter, sample_deps):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        await adapter.ingest_module_deps(sample_deps)
        kwargs = mock_cognee.add.call_args.kwargs
        assert kwargs["dataset_name"] == "code_relationships"


# ---------------------------------------------------------------------------
# Contract: batched ingest_docs — single add call, no cognify
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_docs_batches_add(adapter):
    docs = [("README.md", "Hello"), ("DESIGN.md", "Architecture")]
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        mock_cognee.cognify = AsyncMock()
        await adapter.ingest_docs(docs)
        mock_cognee.add.assert_called_once()
        payload = mock_cognee.add.call_args.args[0]
        assert isinstance(payload, list)
        assert len(payload) == 2
        mock_cognee.cognify.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_docs_empty_is_noop(adapter):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        await adapter.ingest_docs([])
        mock_cognee.add.assert_not_called()


# ---------------------------------------------------------------------------
# Contract: finalize calls cognify exactly once
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finalize_calls_cognify_once(adapter):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.cognify = AsyncMock()
        mock_cognee.memify = AsyncMock()
        await adapter.finalize()
        mock_cognee.cognify.assert_called_once()


@pytest.mark.asyncio
async def test_finalize_calls_memify_by_default(adapter):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.cognify = AsyncMock()
        mock_cognee.memify = AsyncMock()
        await adapter.finalize()
        mock_cognee.memify.assert_called_once()


@pytest.mark.asyncio
async def test_finalize_skips_memify_when_disabled(adapter):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.cognify = AsyncMock()
        mock_cognee.memify = AsyncMock()
        await adapter.finalize(run_memify=False)
        mock_cognee.memify.assert_not_called()


@pytest.mark.asyncio
async def test_finalize_memify_failure_is_non_fatal(adapter):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.cognify = AsyncMock()
        mock_cognee.memify = AsyncMock(side_effect=RuntimeError("memify boom"))
        # Should not raise
        await adapter.finalize()
        mock_cognee.cognify.assert_called_once()


# ---------------------------------------------------------------------------
# Contract: search passes query_type and top_k
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_passes_query_type_and_top_k(adapter):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=["result"])
        results = await adapter.search("auth flow", search_type="CHUNKS", top_k=3)

    kwargs = mock_cognee.search.await_args.kwargs
    assert kwargs["query_text"] == "auth flow"
    assert kwargs["top_k"] == 3
    assert getattr(kwargs["query_type"], "value", "") == "CHUNKS"
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_invalid_type_falls_back_to_graph_completion(adapter):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=["result"])
        await adapter.search("auth flow", search_type="NOT_A_TYPE")

    kwargs = mock_cognee.search.await_args.kwargs
    assert getattr(kwargs["query_type"], "value", "") == "GRAPH_COMPLETION"


@pytest.mark.asyncio
async def test_search_results_wrapped_as_dicts(adapter):
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=["one", "two"])
        results = await adapter.search("query")
    assert results == [{"text": "one"}, {"text": "two"}]
