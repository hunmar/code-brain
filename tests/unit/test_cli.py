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
