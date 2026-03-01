"""Tests for JSON and text formatters."""

from __future__ import annotations

import json

import pytest

from code_brain.formatters.json_formatter import JsonFormatter
from code_brain.formatters.text_formatter import TextFormatter
from code_brain.models import QueryResult, ResultItem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_result() -> QueryResult:
    return QueryResult(query="find_by_email", items=[], total_count=0)


@pytest.fixture
def single_result() -> QueryResult:
    return QueryResult(
        query="find_by_email",
        items=[
            ResultItem(
                file_path="src/repos/user_repo.py",
                symbol="UserRepository.find_by_email",
                kind="function",
                snippet="def find_by_email(self, email: str) -> User | None:",
                score=0.95,
                line_number=8,
            ),
        ],
        total_count=1,
        elapsed_ms=12.5,
    )


@pytest.fixture
def multi_result() -> QueryResult:
    return QueryResult(
        query="User",
        items=[
            ResultItem(
                file_path="src/models/user.py",
                symbol="User",
                kind="class",
                snippet="class User:\n    def __init__(self, name: str, email: str):",
                score=1.0,
                line_number=1,
            ),
            ResultItem(
                file_path="src/models/user.py",
                symbol="AdminUser",
                kind="class",
                snippet="class AdminUser(User):",
                score=0.85,
                line_number=10,
            ),
            ResultItem(
                file_path="src/repos/user_repo.py",
                symbol="UserRepository",
                kind="class",
                snippet="class UserRepository:",
                score=0.70,
                line_number=4,
            ),
        ],
        total_count=3,
        elapsed_ms=8.3,
    )


@pytest.fixture
def result_with_metadata() -> QueryResult:
    return QueryResult(
        query="authenticate",
        items=[
            ResultItem(
                file_path="src/services/auth.py",
                symbol="AuthService.authenticate",
                kind="function",
                snippet="def authenticate(self, email: str, password: str) -> User | None:",
                score=0.92,
                line_number=8,
                metadata={"callers": 3, "complexity": "low"},
            ),
        ],
        total_count=1,
    )


# ---------------------------------------------------------------------------
# JsonFormatter tests
# ---------------------------------------------------------------------------

class TestJsonFormatter:
    def test_format_empty_results(self, empty_result: QueryResult):
        fmt = JsonFormatter()
        output = fmt.format(empty_result)
        data = json.loads(output)
        assert data["query"] == "find_by_email"
        assert data["items"] == []
        assert data["total_count"] == 0

    def test_format_single_result(self, single_result: QueryResult):
        fmt = JsonFormatter()
        output = fmt.format(single_result)
        data = json.loads(output)
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["file_path"] == "src/repos/user_repo.py"
        assert item["symbol"] == "UserRepository.find_by_email"
        assert item["kind"] == "function"
        assert item["score"] == 0.95
        assert item["line_number"] == 8

    def test_format_multiple_results(self, multi_result: QueryResult):
        fmt = JsonFormatter()
        output = fmt.format(multi_result)
        data = json.loads(output)
        assert len(data["items"]) == 3
        assert data["total_count"] == 3
        symbols = [item["symbol"] for item in data["items"]]
        assert symbols == ["User", "AdminUser", "UserRepository"]

    def test_format_is_valid_json(self, multi_result: QueryResult):
        fmt = JsonFormatter()
        output = fmt.format(multi_result)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)
        assert "query" in parsed
        assert "items" in parsed

    def test_format_preserves_metadata(self, result_with_metadata: QueryResult):
        fmt = JsonFormatter()
        output = fmt.format(result_with_metadata)
        data = json.loads(output)
        meta = data["items"][0]["metadata"]
        assert meta["callers"] == 3
        assert meta["complexity"] == "low"

    def test_format_compact(self, single_result: QueryResult):
        fmt = JsonFormatter(indent=None)
        output = fmt.format(single_result)
        assert "\n" not in output
        json.loads(output)  # still valid JSON

    def test_format_custom_indent(self, single_result: QueryResult):
        fmt = JsonFormatter(indent=4)
        output = fmt.format(single_result)
        assert "    " in output  # 4-space indent present
        json.loads(output)

    def test_format_null_optional_fields(self):
        result = QueryResult(
            query="test",
            items=[
                ResultItem(
                    file_path="a.py",
                    symbol="foo",
                    kind="function",
                    snippet="def foo():",
                    score=0.5,
                )
            ],
            total_count=1,
        )
        fmt = JsonFormatter()
        output = fmt.format(result)
        data = json.loads(output)
        assert data["items"][0]["line_number"] is None
        assert data["items"][0]["metadata"] is None
        assert data["elapsed_ms"] is None


# ---------------------------------------------------------------------------
# TextFormatter tests
# ---------------------------------------------------------------------------

class TestTextFormatter:
    def test_format_empty_results(self, empty_result: QueryResult):
        fmt = TextFormatter()
        output = fmt.format(empty_result)
        assert "find_by_email" in output
        assert "0 result" in output

    def test_format_single_result(self, single_result: QueryResult):
        fmt = TextFormatter()
        output = fmt.format(single_result)
        assert "UserRepository.find_by_email" in output
        assert "src/repos/user_repo.py" in output
        assert "function" in output

    def test_format_multiple_results(self, multi_result: QueryResult):
        fmt = TextFormatter()
        output = fmt.format(multi_result)
        assert "User" in output
        assert "AdminUser" in output
        assert "UserRepository" in output
        assert "3 result" in output

    def test_format_shows_scores_by_default(self, single_result: QueryResult):
        fmt = TextFormatter()
        output = fmt.format(single_result)
        assert "0.95" in output

    def test_format_hides_scores(self, single_result: QueryResult):
        fmt = TextFormatter(show_scores=False)
        output = fmt.format(single_result)
        assert "0.95" not in output

    def test_format_shows_line_numbers(self, single_result: QueryResult):
        fmt = TextFormatter()
        output = fmt.format(single_result)
        assert "user_repo.py:8" in output

    def test_format_omits_line_number_when_none(self):
        result = QueryResult(
            query="test",
            items=[
                ResultItem(
                    file_path="a.py",
                    symbol="foo",
                    kind="function",
                    snippet="def foo():",
                    score=0.5,
                )
            ],
            total_count=1,
        )
        fmt = TextFormatter()
        output = fmt.format(result)
        assert "a.py:" not in output  # no trailing colon without line number
        assert "a.py" in output

    def test_format_shows_elapsed_time(self, single_result: QueryResult):
        fmt = TextFormatter()
        output = fmt.format(single_result)
        assert "12.5" in output

    def test_format_omits_elapsed_when_none(self, empty_result: QueryResult):
        fmt = TextFormatter()
        output = fmt.format(empty_result)
        assert "ms" not in output

    def test_format_truncates_long_snippets(self):
        long_snippet = "\n".join(f"line {i}" for i in range(20))
        result = QueryResult(
            query="test",
            items=[
                ResultItem(
                    file_path="a.py",
                    symbol="foo",
                    kind="function",
                    snippet=long_snippet,
                    score=0.5,
                )
            ],
            total_count=1,
        )
        fmt = TextFormatter(max_snippet_lines=5)
        output = fmt.format(result)
        assert "line 0" in output
        assert "line 4" in output
        assert "line 5" not in output
        assert "..." in output

    def test_format_preserves_snippet_within_limit(self, single_result: QueryResult):
        fmt = TextFormatter(max_snippet_lines=10)
        output = fmt.format(single_result)
        assert "def find_by_email" in output
        assert "..." not in output
