from typer.testing import CliRunner
from code_brain.cli import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_cli_status_no_project(tmp_path):
    result = runner.invoke(app, ["status"], env={"CODE_BRAIN_PROJECT": str(tmp_path)})
    assert result.exit_code == 0 or "not initialized" in result.stdout.lower()


def test_find_positional_name():
    """code-brain find UserService should work as a positional arg."""
    from unittest.mock import patch, MagicMock

    mock_engine = MagicMock()
    mock_engine.find.return_value = [
        {"id": 1, "name": "UserService", "kind": "class",
         "file_path": "src/svc.py", "line": 5, "signature": "class UserService"}
    ]

    with patch("code_brain.cli._get_structural_engine", return_value=mock_engine):
        result = runner.invoke(app, ["find", "UserService"])
    assert result.exit_code == 0
    assert "UserService" in result.stdout
    mock_engine.find.assert_called_once_with(name="UserService", kind=None, limit=100)


def test_find_no_args_lists_all():
    """code-brain find (no args) should list all symbols."""
    from unittest.mock import patch, MagicMock

    mock_engine = MagicMock()
    mock_engine.find.return_value = []

    with patch("code_brain.cli._get_structural_engine", return_value=mock_engine):
        result = runner.invoke(app, ["find"])
    assert result.exit_code == 0
    mock_engine.find.assert_called_once_with(name=None, kind=None, limit=100)


def test_serve_import_works():
    """Verify the serve command can import run_server without error."""
    from code_brain.mcp_server import run_server
    assert callable(run_server)


def test_serve_command_exists():
    """Verify serve command is registered and help works."""
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "MCP" in result.stdout or "server" in result.stdout.lower()


def test_search_command_exists():
    """Verify search command is registered and help works."""
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0
    assert "semantic" in result.stdout.lower() or "search" in result.stdout.lower()


def test_reason_command_exists():
    """Verify reason command is registered and help works."""
    result = runner.invoke(app, ["reason", "--help"])
    assert result.exit_code == 0
    assert "reason" in result.stdout.lower()


def test_search_calls_semantic_engine():
    """search should call semantic engine search_fast with top_k."""
    from unittest.mock import patch, MagicMock, AsyncMock

    mock_engine = MagicMock()
    mock_engine.search_fast = AsyncMock(return_value=[{"text": "auth result"}])

    with patch("code_brain.cli._get_semantic_engine", return_value=mock_engine):
        result = runner.invoke(app, ["search", "authentication", "--top-k", "3"])

    assert result.exit_code == 0
    mock_engine.search_fast.assert_called_once_with("authentication", top_k=3)


def test_reason_calls_semantic_engine():
    """reason should call semantic engine reason method."""
    from unittest.mock import patch, MagicMock, AsyncMock

    mock_engine = MagicMock()
    mock_engine.reason = AsyncMock(return_value=[{"text": "Because boundaries are shared"}])

    with patch("code_brain.cli._get_semantic_engine", return_value=mock_engine):
        result = runner.invoke(app, ["reason", "Why does auth depend on users?"])

    assert result.exit_code == 0
    mock_engine.reason.assert_called_once_with("Why does auth depend on users?")


def test_ingest_runs_ast_index_when_no_db(tmp_path, monkeypatch):
    """ingest should try ast-index rebuild when no DB exists."""
    from unittest.mock import patch, MagicMock

    (tmp_path / ".code-brain").mkdir()
    monkeypatch.setenv("CODE_BRAIN_PROJECT", str(tmp_path))

    mock_run = MagicMock()
    mock_run.return_value.returncode = 1  # ast-index rebuild "fails"

    with patch("subprocess.run", mock_run):
        result = runner.invoke(app, ["ingest"])

    # Should have attempted ast-index rebuild
    calls = [str(c) for c in mock_run.call_args_list]
    assert any("ast-index" in c and "rebuild" in c for c in calls), \
        f"Expected ast-index rebuild call, got: {calls}"


def test_ingest_ast_index_not_found_shows_install_help(tmp_path, monkeypatch):
    """When ast-index binary not found, show install instructions."""
    from unittest.mock import patch

    (tmp_path / ".code-brain").mkdir()
    monkeypatch.setenv("CODE_BRAIN_PROJECT", str(tmp_path))

    with patch("subprocess.run", side_effect=FileNotFoundError("not found")):
        result = runner.invoke(app, ["ingest"])

    assert "ast-index not installed" in result.stdout
    assert "cargo install" in result.stdout


def test_doctor_command_runs(tmp_path, monkeypatch):
    """doctor should report status without crashing."""
    monkeypatch.setenv("CODE_BRAIN_PROJECT", str(tmp_path))
    (tmp_path / ".code-brain").mkdir()

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Code Brain Doctor" in result.stdout


def test_doctor_shows_all_checks(tmp_path, monkeypatch):
    """doctor should check ast-index, graph, docker."""
    monkeypatch.setenv("CODE_BRAIN_PROJECT", str(tmp_path))
    (tmp_path / ".code-brain").mkdir()

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    output = result.stdout.lower()
    assert "ast-index" in output
    assert "graph" in output
    assert "docker" in output


def test_error_message_mentions_ingest(tmp_path, monkeypatch):
    """When AST index missing, error should mention 'ingest'."""
    monkeypatch.setenv("CODE_BRAIN_PROJECT", str(tmp_path))
    (tmp_path / ".code-brain").mkdir()

    result = runner.invoke(app, ["find", "Foo"])
    assert "ingest" in result.stdout.lower()
