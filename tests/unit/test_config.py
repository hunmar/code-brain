# code-brain/tests/unit/test_config.py
import os
import tempfile
from pathlib import Path
from code_brain.config import CodeBrainConfig, find_project_root


def test_find_project_root_with_code_brain_dir(tmp_path):
    (tmp_path / ".code-brain").mkdir()
    assert find_project_root(tmp_path) == tmp_path


def test_find_project_root_with_git_dir(tmp_path):
    (tmp_path / ".git").mkdir()
    assert find_project_root(tmp_path) == tmp_path


def test_find_project_root_none(tmp_path):
    subdir = tmp_path / "deep" / "nested"
    subdir.mkdir(parents=True)
    assert find_project_root(subdir) is None


def test_config_defaults(tmp_path):
    config = CodeBrainConfig(project_root=tmp_path)
    assert config.project_root == tmp_path
    assert config.code_brain_dir == tmp_path / ".code-brain"
    assert config.graph_path == tmp_path / ".code-brain" / "graph.pkl"
    assert config.neo4j_uri == "bolt://localhost:7687"
    assert config.neo4j_user == "neo4j"
    assert config.neo4j_password == "codebrain"
    assert config.qdrant_url == "http://localhost:6333"


def test_config_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CODE_BRAIN_NEO4J_URI", "bolt://custom:7687")
    monkeypatch.setenv("CODE_BRAIN_NEO4J_PASSWORD", "secret")
    config = CodeBrainConfig(project_root=tmp_path)
    assert config.neo4j_uri == "bolt://custom:7687"
    assert config.neo4j_password == "secret"


def test_config_init_creates_dir(tmp_path):
    config = CodeBrainConfig(project_root=tmp_path)
    config.ensure_dirs()
    assert config.code_brain_dir.is_dir()
