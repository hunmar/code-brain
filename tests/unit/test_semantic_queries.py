from unittest.mock import AsyncMock, MagicMock
import pytest

from code_brain.query.semantic import SemanticQueryEngine


@pytest.mark.asyncio
async def test_ask_uses_graph_completion():
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value=[{"text": "Result about auth"}])
    engine = SemanticQueryEngine(adapter)

    result = await engine.ask("What does AuthService do?")

    adapter.search.assert_awaited_once_with(
        "What does AuthService do?",
        search_type="GRAPH_COMPLETION",
    )
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_explain_uses_summary_completion_and_includes_symbol():
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value=[{"text": "Handles user auth"}])
    engine = SemanticQueryEngine(adapter)
    structural_info = {
        "name": "AuthService",
        "kind": "class",
        "file_path": "services/auth.py",
        "line": 3,
    }

    result = await engine.explain("AuthService", structural_info)

    adapter.search.assert_awaited_once_with(
        "Explain the purpose and context of AuthService",
        search_type="GRAPH_SUMMARY_COMPLETION",
    )
    assert "AuthService" in result


@pytest.mark.asyncio
async def test_search_fast_uses_chunks():
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value=[{"text": "chunk"}])
    engine = SemanticQueryEngine(adapter)

    await engine.search_fast("auth", top_k=5)

    adapter.search.assert_awaited_once_with(
        "auth",
        search_type="CHUNKS",
        top_k=5,
    )


@pytest.mark.asyncio
async def test_reason_uses_graph_completion_cot():
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value=[{"text": "reason"}])
    engine = SemanticQueryEngine(adapter)

    await engine.reason("Why does module A depend on B?")

    adapter.search.assert_awaited_once_with(
        "Why does module A depend on B?",
        search_type="GRAPH_COMPLETION_COT",
    )


@pytest.mark.asyncio
async def test_review_diff_uses_coding_rules():
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value=[{"text": "Looks good."}])
    engine = SemanticQueryEngine(adapter)

    await engine.review_diff("+ def foo():\n+    return 1")

    adapter.search.assert_awaited_once()
    args = adapter.search.await_args
    assert args.kwargs.get("search_type") == "CODING_RULES"
