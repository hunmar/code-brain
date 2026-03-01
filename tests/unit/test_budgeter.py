"""Tests for the context token budgeter."""

import pytest
from code_brain.query.budgeter import ContextBudgeter, Depth


class TestDepthEnum:
    """Test the Depth enum values."""

    def test_depth_values(self):
        assert Depth.COMPACT == "compact"
        assert Depth.MEDIUM == "medium"
        assert Depth.FULL == "full"

    def test_depth_from_string(self):
        assert Depth("compact") is Depth.COMPACT
        assert Depth("medium") is Depth.MEDIUM
        assert Depth("full") is Depth.FULL


class TestContextBudgeterInit:
    """Test ContextBudgeter initialization."""

    def test_default_budget(self):
        b = ContextBudgeter()
        assert b.max_tokens == 4096
        assert b.depth == Depth.MEDIUM

    def test_custom_budget(self):
        b = ContextBudgeter(max_tokens=8000, depth=Depth.FULL)
        assert b.max_tokens == 8000
        assert b.depth == Depth.FULL

    def test_zero_budget(self):
        b = ContextBudgeter(max_tokens=0)
        assert b.total_remaining() == 0


class TestTokenCounting:
    """Test token counting with tiktoken."""

    def test_count_tokens_empty(self):
        b = ContextBudgeter()
        assert b.count_tokens("") == 0

    def test_count_tokens_simple(self):
        b = ContextBudgeter()
        count = b.count_tokens("hello world")
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_code(self):
        b = ContextBudgeter()
        code = "def foo(x: int) -> int:\n    return x + 1"
        count = b.count_tokens(code)
        assert count > 0


class TestBudgetAllocation:
    """Test budget allocation across sections for each depth."""

    def test_compact_has_no_source_budget(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.COMPACT)
        assert b.get_allocation("source") == 0

    def test_compact_has_signatures_budget(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.COMPACT)
        assert b.get_allocation("signatures") > 0

    def test_medium_has_all_sections(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.MEDIUM)
        assert b.get_allocation("signatures") > 0
        assert b.get_allocation("docstrings") > 0
        assert b.get_allocation("source") > 0
        assert b.get_allocation("context") > 0

    def test_full_has_most_source(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.FULL)
        assert b.get_allocation("source") > b.get_allocation("signatures")

    def test_allocations_sum_to_max(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.MEDIUM)
        total = sum(
            b.get_allocation(s) for s in ["signatures", "docstrings", "source", "context"]
        )
        # Allow off-by-one from int rounding
        assert abs(total - 1000) <= 4


class TestFitsAndConsume:
    """Test fits() and consume() methods."""

    def test_fits_within_budget(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.FULL)
        assert b.fits("x", "source") is True

    def test_fits_unknown_section(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.FULL)
        assert b.fits("x", "nonexistent") is False

    def test_consume_reduces_remaining(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.FULL)
        before = b.remaining("source")
        text = "def foo(): pass"
        result = b.consume(text, "source")
        assert result is True
        assert b.remaining("source") < before

    def test_consume_returns_false_when_exceeds(self):
        b = ContextBudgeter(max_tokens=10, depth=Depth.FULL)
        long_text = "x " * 500  # way more than 10 tokens
        result = b.consume(long_text, "source")
        assert result is False

    def test_consume_unknown_section(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.FULL)
        assert b.consume("hello", "nonexistent") is False

    def test_multiple_consumes_accumulate(self):
        b = ContextBudgeter(max_tokens=2000, depth=Depth.FULL)
        b.consume("def foo(): pass", "source")
        first_remaining = b.remaining("source")
        b.consume("def bar(): pass", "source")
        assert b.remaining("source") < first_remaining


class TestTotalBudget:
    """Test total_remaining and total_used."""

    def test_initial_total_remaining(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.MEDIUM)
        # Should be close to max_tokens (may differ by rounding)
        assert abs(b.total_remaining() - 1000) <= 4

    def test_total_used_starts_zero(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.MEDIUM)
        assert b.total_used() == 0

    def test_total_used_after_consume(self):
        b = ContextBudgeter(max_tokens=2000, depth=Depth.FULL)
        text = "def hello(): pass"
        b.consume(text, "source")
        assert b.total_used() > 0
        assert b.total_used() == b.count_tokens(text)


class TestTruncateToFit:
    """Test truncate_to_fit helper."""

    def test_short_text_unchanged(self):
        b = ContextBudgeter(max_tokens=2000, depth=Depth.FULL)
        text = "hello"
        result = b.truncate_to_fit(text, "source")
        assert result == text

    def test_long_text_truncated(self):
        b = ContextBudgeter(max_tokens=50, depth=Depth.FULL)
        text = "word " * 200
        result = b.truncate_to_fit(text, "source")
        assert len(result) < len(text)
        # Truncated result should fit in the allocation
        assert b.count_tokens(result) <= b.get_allocation("source")

    def test_truncate_unknown_section_returns_empty(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.FULL)
        result = b.truncate_to_fit("hello", "nonexistent")
        assert result == ""


class TestDepthProfiles:
    """Test that depth profiles have correct relative proportions."""

    def test_compact_mostly_signatures(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.COMPACT)
        sig = b.get_allocation("signatures")
        ctx = b.get_allocation("context")
        assert sig >= ctx  # signatures should dominate in compact

    def test_full_mostly_source(self):
        b = ContextBudgeter(max_tokens=1000, depth=Depth.FULL)
        src = b.get_allocation("source")
        sig = b.get_allocation("signatures")
        assert src > sig  # source should dominate in full
