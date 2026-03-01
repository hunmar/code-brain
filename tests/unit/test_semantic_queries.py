from unittest.mock import AsyncMock, patch
import pytest
from code_brain.query.semantic import SemanticQueryEngine


@pytest.mark.asyncio
async def test_ask_returns_results():
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=["Result about auth"])
        from code_brain.ingestion.cognee_adapter import CogneeAdapter
        adapter = CogneeAdapter()
        engine = SemanticQueryEngine(adapter)
        result = await engine.ask("What does AuthService do?")
        assert len(result) >= 1


@pytest.mark.asyncio
async def test_explain_combines_structural_and_semantic():
    with patch("code_brain.ingestion.cognee_adapter.cognee") as mock_cognee:
        mock_cognee.search = AsyncMock(return_value=["Handles user auth"])
        from code_brain.ingestion.cognee_adapter import CogneeAdapter
        adapter = CogneeAdapter()
        engine = SemanticQueryEngine(adapter)
        structural_info = {
            "name": "AuthService", "kind": "class",
            "file_path": "services/auth.py", "line": 3,
        }
        result = await engine.explain("AuthService", structural_info)
        assert "AuthService" in result
