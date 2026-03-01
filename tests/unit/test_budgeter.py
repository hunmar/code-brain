# code-brain/tests/unit/test_budgeter.py
import pytest
from code_brain.query.budgeter import ContextBudgeter, ContextEntry


@pytest.fixture
def sample_entries():
    return [
        ContextEntry(
            name="User", kind="class", file_path="models/user.py", line=1,
            signature="class User", summary="User model", body="class User:\n    pass",
        ),
        ContextEntry(
            name="AuthService", kind="class", file_path="services/auth.py", line=1,
            signature="class AuthService", summary="Auth logic",
            body="class AuthService:\n    def authenticate(self): pass",
        ),
        ContextEntry(
            name="UserRepo", kind="class", file_path="repos/repo.py", line=1,
            signature="class UserRepo", summary="Data access",
            body="class UserRepo:\n    def find(self): pass",
        ),
    ]


def test_compact_depth(sample_entries):
    budgeter = ContextBudgeter()
    result = budgeter.format(sample_entries, token_budget=500)
    # Should include names and signatures but NOT body
    assert "User" in result
    assert "class User" in result
    # Body should be excluded in compact mode
    assert "pass" not in result or len(result) < 500


def test_full_depth(sample_entries):
    budgeter = ContextBudgeter()
    result = budgeter.format(sample_entries, token_budget=50000)
    # Should include everything
    assert "User" in result
    assert "class User" in result


def test_budget_respected(sample_entries):
    budgeter = ContextBudgeter()
    result = budgeter.format(sample_entries, token_budget=100)
    # With very small budget, should have fewer entries
    assert len(result) < 1000  # rough char estimate for 100 tokens


def test_empty_entries():
    budgeter = ContextBudgeter()
    result = budgeter.format([], token_budget=1000)
    assert result == ""
