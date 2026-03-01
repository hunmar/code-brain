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


@pytest.mark.asyncio
async def test_safe_semantic_call_degrades_on_backend_error():
    async def failing_call():
        raise Exception("sqlite3.OperationalError: unable to open database file")

    result = await _safe_semantic_call(failing_call())
    assert "error" in result
    assert "unavailable" in result["error"].lower()


@pytest.mark.asyncio
async def test_dispatch_code_search_calls_semantic_search_fast():
    structural = MagicMock()
    semantic = MagicMock()
    hybrid = MagicMock()
    graph = MagicMock()
    semantic.search_fast = AsyncMock(return_value=[{"text": "auth logic"}])

    result = await _dispatch(
        "code_search",
        {"query": "auth logic"},
        structural,
        semantic,
        hybrid,
        graph,
    )

    semantic.search_fast.assert_awaited_once_with("auth logic", top_k=10)
    assert result == [{"text": "auth logic"}]


@pytest.mark.asyncio
async def test_dispatch_code_reason_calls_semantic_reason():
    structural = MagicMock()
    semantic = MagicMock()
    hybrid = MagicMock()
    graph = MagicMock()
    semantic.reason = AsyncMock(return_value=[{"text": "Because of shared auth boundary."}])

    result = await _dispatch(
        "code_reason",
        {"question": "Why does payments depend on auth?"},
        structural,
        semantic,
        hybrid,
        graph,
    )

    semantic.reason.assert_awaited_once_with("Why does payments depend on auth?")
    assert isinstance(result, list)


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
