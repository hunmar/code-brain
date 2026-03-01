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
