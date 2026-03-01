from unittest.mock import AsyncMock, MagicMock

import pytest

from code_brain.mcp_server import TOOL_NAMES, _dispatch, _safe_semantic_call


def test_server_has_expected_tools():
    assert "code_find_symbol" in TOOL_NAMES
    assert "code_map" in TOOL_NAMES
    assert "code_impact" in TOOL_NAMES
    assert "code_search" in TOOL_NAMES
    assert "code_reason" in TOOL_NAMES
    assert len(TOOL_NAMES) == 14


# ---------------------------------------------------------------------------
# _safe_semantic_call — degraded responses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_safe_semantic_call_passes_through_on_success():
    async def ok():
        return {"answer": "hello", "evidence": [], "confidence": "low", "degraded": False, "warnings": []}

    result = await _safe_semantic_call(ok())
    assert result["answer"] == "hello"
    assert result["degraded"] is False


@pytest.mark.asyncio
async def test_safe_semantic_call_degrades_on_backend_error():
    async def failing_call():
        raise Exception("sqlite3.OperationalError: unable to open database file")

    result = await _safe_semantic_call(failing_call())
    assert result["degraded"] is True
    assert result["confidence"] == "low"
    assert result["evidence"] == []
    assert any("code-brain up" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_safe_semantic_call_degrades_on_generic_error():
    async def failing_call():
        raise ValueError("something unexpected")

    result = await _safe_semantic_call(failing_call())
    assert result["degraded"] is True
    assert any("something unexpected" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# _dispatch — code_search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_code_search_calls_semantic_search_fast():
    structural = MagicMock()
    semantic = MagicMock()
    hybrid = MagicMock()
    graph = MagicMock()
    semantic.search_fast = AsyncMock(return_value={
        "answer": "auth logic", "evidence": [], "confidence": "low",
        "degraded": False, "warnings": [],
    })

    result = await _dispatch(
        "code_search",
        {"query": "auth logic"},
        structural,
        semantic,
        hybrid,
        graph,
    )

    semantic.search_fast.assert_awaited_once_with("auth logic", top_k=10)
    assert result["answer"] == "auth logic"


# ---------------------------------------------------------------------------
# _dispatch — code_reason
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_code_reason_calls_semantic_reason():
    structural = MagicMock()
    semantic = MagicMock()
    hybrid = MagicMock()
    graph = MagicMock()
    semantic.reason = AsyncMock(return_value={
        "answer": "Because of shared auth boundary.",
        "evidence": [], "confidence": "low",
        "degraded": False, "warnings": [],
    })

    result = await _dispatch(
        "code_reason",
        {"question": "Why does payments depend on auth?"},
        structural,
        semantic,
        hybrid,
        graph,
    )

    semantic.reason.assert_awaited_once_with("Why does payments depend on auth?")
    assert isinstance(result, dict)
    assert "answer" in result


# ---------------------------------------------------------------------------
# _dispatch — missing arguments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_returns_missing_argument_error():
    structural = MagicMock()
    semantic = MagicMock()
    hybrid = MagicMock()
    graph = MagicMock()

    result = await _dispatch(
        "code_search",
        {},
        structural,
        semantic,
        hybrid,
        graph,
    )

    assert "error" in result
    assert "missing required argument" in result["error"].lower()


# ---------------------------------------------------------------------------
# _dispatch — unknown tool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_unknown_tool():
    structural = MagicMock()
    semantic = MagicMock()
    hybrid = MagicMock()
    graph = MagicMock()

    result = await _dispatch(
        "nonexistent_tool",
        {},
        structural,
        semantic,
        hybrid,
        graph,
    )

    assert "error" in result
    assert "Unknown tool" in result["error"]


# ---------------------------------------------------------------------------
# _dispatch — code_ask
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_code_ask():
    structural = MagicMock()
    semantic = MagicMock()
    hybrid = MagicMock()
    graph = MagicMock()
    semantic.ask = AsyncMock(return_value={
        "answer": "Auth manages sessions",
        "evidence": [], "confidence": "low",
        "degraded": False, "warnings": [],
    })

    result = await _dispatch(
        "code_ask",
        {"question": "What is auth?"},
        structural,
        semantic,
        hybrid,
        graph,
    )

    assert result["answer"] == "Auth manages sessions"
    assert result["degraded"] is False
