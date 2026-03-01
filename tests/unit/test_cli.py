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
