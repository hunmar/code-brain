from unittest.mock import AsyncMock, patch
import pytest
from code_brain.ingestion.cognee_adapter import CogneeAdapter
from code_brain.ingestion.ast_index import Symbol


@pytest.fixture
def sample_symbols():
    return [
        Symbol(1, "User", "class", "models/user.py", 1, "class User"),
        Symbol(2, "AuthService", "class", "services/auth.py", 3, "class AuthService"),
    ]


def test_format_symbol_document(sample_symbols):
    adapter = CogneeAdapter()
    doc = adapter._format_symbol_doc(sample_symbols[0])
    assert "User" in doc
    assert "class" in doc
    assert "models/user.py" in doc


def test_format_module_doc():
    adapter = CogneeAdapter()
    doc = adapter._format_module_doc("services", "models", "import")
    assert "services" in doc
    assert "models" in doc


@pytest.mark.asyncio
async def test_ingest_symbols_calls_cognee(sample_symbols):
    adapter = CogneeAdapter()
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.add = AsyncMock()
        mock_cognee.cognify = AsyncMock()
        await adapter.ingest_symbols(sample_symbols)
        assert mock_cognee.add.call_count == len(sample_symbols)
        mock_cognee.cognify.assert_called_once()


@pytest.mark.asyncio
async def test_search_passes_query_type_and_top_k():
    adapter = CogneeAdapter()
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=["result"])
        results = await adapter.search("auth flow", search_type="CHUNKS", top_k=3)

    kwargs = mock_cognee.search.await_args.kwargs
    assert kwargs["query_text"] == "auth flow"
    assert kwargs["top_k"] == 3
    assert getattr(kwargs["query_type"], "value", "") == "CHUNKS"
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_invalid_type_falls_back_to_graph_completion():
    adapter = CogneeAdapter()
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=["result"])
        await adapter.search("auth flow", search_type="NOT_A_TYPE")

    kwargs = mock_cognee.search.await_args.kwargs
    assert getattr(kwargs["query_type"], "value", "") == "GRAPH_COMPLETION"
