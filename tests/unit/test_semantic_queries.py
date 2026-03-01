from unittest.mock import AsyncMock, MagicMock
import pytest

from code_brain.query.semantic import (
    SemanticQueryEngine,
    _extract_evidence,
    _score_confidence,
    _build_response,
)


# ---------------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------------

def test_extract_evidence_from_file_line():
    results = [{"text": "Code symbol: AuthService\nFile: services/auth.py:3"}]
    evidence = _extract_evidence(results)
    assert len(evidence) == 1
    assert evidence[0]["file_path"] == "services/auth.py"
    assert evidence[0]["line"] == 3


def test_extract_evidence_finds_symbol_name():
    results = [{"text": "class AuthService in services/auth.py:3"}]
    evidence = _extract_evidence(results)
    assert len(evidence) == 1
    assert evidence[0].get("symbol") == "AuthService"


def test_extract_evidence_deduplicates():
    results = [
        {"text": "File: auth.py:10"},
        {"text": "Also at auth.py:10"},
    ]
    evidence = _extract_evidence(results)
    assert len(evidence) == 1


def test_extract_evidence_no_matches():
    results = [{"text": "Just a plain answer with no file refs"}]
    evidence = _extract_evidence(results)
    assert evidence == []


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def test_confidence_high():
    assert _score_confidence([{"file_path": "a.py"}, {"file_path": "b.py"}]) == "high"


def test_confidence_medium():
    assert _score_confidence([{"file_path": "a.py"}]) == "medium"


def test_confidence_low():
    assert _score_confidence([]) == "low"


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def test_build_response_shape():
    resp = _build_response("answer text", [])
    assert resp["answer"] == "answer text"
    assert resp["evidence"] == []
    assert resp["confidence"] == "low"
    assert resp["degraded"] is False
    assert resp["warnings"] == []


def test_build_response_with_evidence():
    results = [{"text": "class Foo at src/foo.py:42"}]
    resp = _build_response("answer", results)
    assert resp["confidence"] == "medium"
    assert len(resp["evidence"]) == 1


def test_build_response_degraded():
    resp = _build_response("partial", [], degraded=True, warnings=["backend down"])
    assert resp["degraded"] is True
    assert resp["warnings"] == ["backend down"]


# ---------------------------------------------------------------------------
# SemanticQueryEngine.ask
# ---------------------------------------------------------------------------

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
    assert "answer" in result
    assert "evidence" in result
    assert "confidence" in result
    assert result["degraded"] is False


@pytest.mark.asyncio
async def test_ask_answer_contains_result_text():
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value=[{"text": "Auth handles login"}])
    engine = SemanticQueryEngine(adapter)
    result = await engine.ask("question")
    assert "Auth handles login" in result["answer"]


# ---------------------------------------------------------------------------
# SemanticQueryEngine.explain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_uses_summary_completion():
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
    assert "AuthService" in result["answer"]
    assert result["confidence"] in ("medium", "high")
    assert any(
        e.get("file_path") == "services/auth.py" for e in result["evidence"]
    )


@pytest.mark.asyncio
async def test_explain_without_structural_info():
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value=[{"text": "A helper util"}])
    engine = SemanticQueryEngine(adapter)

    result = await engine.explain("some_func")
    assert "some_func" in result["answer"]
    assert result["confidence"] == "low"


# ---------------------------------------------------------------------------
# SemanticQueryEngine.search_fast
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_fast_uses_chunks():
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value=[{"text": "chunk"}])
    engine = SemanticQueryEngine(adapter)

    result = await engine.search_fast("auth", top_k=5)

    adapter.search.assert_awaited_once_with(
        "auth",
        search_type="CHUNKS",
        top_k=5,
    )
    assert "answer" in result
    assert result["degraded"] is False


# ---------------------------------------------------------------------------
# SemanticQueryEngine.reason
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reason_uses_graph_completion_cot():
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value=[{"text": "reason"}])
    engine = SemanticQueryEngine(adapter)

    result = await engine.reason("Why does module A depend on B?")

    adapter.search.assert_awaited_once_with(
        "Why does module A depend on B?",
        search_type="GRAPH_COMPLETION_COT",
    )
    assert "answer" in result


# ---------------------------------------------------------------------------
# SemanticQueryEngine.review_diff
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_diff_uses_coding_rules():
    adapter = MagicMock()
    adapter.search = AsyncMock(return_value=[{"text": "Looks good."}])
    engine = SemanticQueryEngine(adapter)

    result = await engine.review_diff("+ def foo():\n+    return 1")

    adapter.search.assert_awaited_once()
    args = adapter.search.await_args
    assert args.kwargs.get("search_type") == "CODING_RULES"
    assert "answer" in result
