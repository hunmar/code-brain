"""Tests for code_brain.config module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from code_brain.config import ProjectConfig


class TestProjectConfigDefaults:
    """Test that ProjectConfig provides sensible defaults."""

    def test_repo_root_is_required(self):
        cfg = ProjectConfig(repo_root=Path("/tmp/myrepo"))
        assert cfg.repo_root == Path("/tmp/myrepo")

    def test_ast_db_path_defaults_to_repo_root(self):
        cfg = ProjectConfig(repo_root=Path("/tmp/myrepo"))
        assert cfg.ast_db_path == Path("/tmp/myrepo/.code_brain/ast.db")

    def test_neo4j_uri_default(self):
        cfg = ProjectConfig(repo_root=Path("/tmp/myrepo"))
        assert cfg.neo4j_uri == "bolt://localhost:7687"

    def test_neo4j_user_default(self):
        cfg = ProjectConfig(repo_root=Path("/tmp/myrepo"))
        assert cfg.neo4j_user == "neo4j"

    def test_neo4j_password_default(self):
        cfg = ProjectConfig(repo_root=Path("/tmp/myrepo"))
        assert cfg.neo4j_password == "codebrain"

    def test_qdrant_url_default(self):
        cfg = ProjectConfig(repo_root=Path("/tmp/myrepo"))
        assert cfg.qdrant_url == "http://localhost:6333"

    def test_token_budget_default(self):
        cfg = ProjectConfig(repo_root=Path("/tmp/myrepo"))
        assert cfg.token_budget == 10_000


class TestProjectConfigCustomValues:
    """Test that ProjectConfig accepts custom values."""

    def test_custom_ast_db_path(self):
        cfg = ProjectConfig(
            repo_root=Path("/tmp/myrepo"),
            ast_db_path=Path("/custom/ast.db"),
        )
        assert cfg.ast_db_path == Path("/custom/ast.db")

    def test_custom_neo4j_uri(self):
        cfg = ProjectConfig(
            repo_root=Path("/tmp/myrepo"),
            neo4j_uri="bolt://neo4j-host:7687",
        )
        assert cfg.neo4j_uri == "bolt://neo4j-host:7687"

    def test_custom_token_budget(self):
        cfg = ProjectConfig(
            repo_root=Path("/tmp/myrepo"),
            token_budget=50_000,
        )
        assert cfg.token_budget == 50_000


class TestProjectConfigEnvOverrides:
    """Test that environment variables override defaults."""

    @patch.dict(os.environ, {"CODE_BRAIN_NEO4J_URI": "bolt://prod:7687"})
    def test_neo4j_uri_env_override(self):
        cfg = ProjectConfig.from_repo(Path("/tmp/myrepo"))
        assert cfg.neo4j_uri == "bolt://prod:7687"

    @patch.dict(os.environ, {"CODE_BRAIN_NEO4J_USER": "admin"})
    def test_neo4j_user_env_override(self):
        cfg = ProjectConfig.from_repo(Path("/tmp/myrepo"))
        assert cfg.neo4j_user == "admin"

    @patch.dict(os.environ, {"CODE_BRAIN_NEO4J_PASSWORD": "s3cret"})
    def test_neo4j_password_env_override(self):
        cfg = ProjectConfig.from_repo(Path("/tmp/myrepo"))
        assert cfg.neo4j_password == "s3cret"

    @patch.dict(os.environ, {"CODE_BRAIN_QDRANT_URL": "http://qdrant:6333"})
    def test_qdrant_url_env_override(self):
        cfg = ProjectConfig.from_repo(Path("/tmp/myrepo"))
        assert cfg.qdrant_url == "http://qdrant:6333"

    @patch.dict(os.environ, {"CODE_BRAIN_TOKEN_BUDGET": "25000"})
    def test_token_budget_env_override(self):
        cfg = ProjectConfig.from_repo(Path("/tmp/myrepo"))
        assert cfg.token_budget == 25_000

    def test_from_repo_uses_defaults_without_env(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove any CODE_BRAIN_ vars that might exist
            env = {k: v for k, v in os.environ.items() if not k.startswith("CODE_BRAIN_")}
            with patch.dict(os.environ, env, clear=True):
                cfg = ProjectConfig.from_repo(Path("/tmp/myrepo"))
                assert cfg.neo4j_uri == "bolt://localhost:7687"
                assert cfg.neo4j_user == "neo4j"
                assert cfg.neo4j_password == "codebrain"
                assert cfg.qdrant_url == "http://localhost:6333"
                assert cfg.token_budget == 10_000


class TestProjectConfigDataDir:
    """Test the data_dir property and path derivations."""

    def test_data_dir(self):
        cfg = ProjectConfig(repo_root=Path("/tmp/myrepo"))
        assert cfg.data_dir == Path("/tmp/myrepo/.code_brain")

    def test_ast_db_path_inside_data_dir(self):
        cfg = ProjectConfig(repo_root=Path("/tmp/myrepo"))
        assert cfg.ast_db_path.parent == cfg.data_dir
