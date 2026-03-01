"""Tests for AST index SQLite reader."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from code_brain.ingestion.ast_index import AstIndex, Symbol, Usage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create a test SQLite database with sample AST data."""
    db = tmp_path / "ast_index.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE symbols (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            qualified_name TEXT NOT NULL,
            kind TEXT NOT NULL,
            file_path TEXT NOT NULL,
            line_start INTEGER NOT NULL,
            line_end INTEGER NOT NULL,
            parent_id INTEGER REFERENCES symbols(id)
        );
        CREATE TABLE references_ (
            id INTEGER PRIMARY KEY,
            symbol_id INTEGER NOT NULL REFERENCES symbols(id),
            file_path TEXT NOT NULL,
            line INTEGER NOT NULL,
            kind TEXT NOT NULL
        );
        CREATE TABLE file_dependencies (
            source_file TEXT NOT NULL,
            target_file TEXT NOT NULL,
            PRIMARY KEY (source_file, target_file)
        );

        -- Sample symbols
        INSERT INTO symbols VALUES
            (1, 'User', 'src.models.user.User', 'class',
             'src/models/user.py', 1, 7, NULL);
        INSERT INTO symbols VALUES
            (2, '__init__', 'src.models.user.User.__init__', 'method',
             'src/models/user.py', 2, 4, 1);
        INSERT INTO symbols VALUES
            (3, 'display_name', 'src.models.user.User.display_name', 'method',
             'src/models/user.py', 6, 7, 1);
        INSERT INTO symbols VALUES
            (4, 'AdminUser', 'src.models.user.AdminUser', 'class',
             'src/models/user.py', 10, 13, NULL);
        INSERT INTO symbols VALUES
            (5, 'AuthService', 'src.services.auth.AuthService', 'class',
             'src/services/auth.py', 4, 15, NULL);
        INSERT INTO symbols VALUES
            (6, 'authenticate', 'src.services.auth.AuthService.authenticate',
             'method', 'src/services/auth.py', 8, 12, 5);
        INSERT INTO symbols VALUES
            (7, 'UserRepository', 'src.repos.user_repo.UserRepository', 'class',
             'src/repos/user_repo.py', 4, 15, NULL);
        INSERT INTO symbols VALUES
            (8, 'find_by_email',
             'src.repos.user_repo.UserRepository.find_by_email', 'method',
             'src/repos/user_repo.py', 8, 12, 7);
        INSERT INTO symbols VALUES
            (9, 'save', 'src.repos.user_repo.UserRepository.save', 'method',
             'src/repos/user_repo.py', 14, 15, 7);

        -- Sample references (usages)
        INSERT INTO references_ VALUES
            (1, 1, 'src/services/auth.py', 1, 'import');
        INSERT INTO references_ VALUES
            (2, 4, 'src/services/auth.py', 1, 'import');
        INSERT INTO references_ VALUES
            (3, 1, 'src/repos/user_repo.py', 1, 'import');
        INSERT INTO references_ VALUES
            (4, 8, 'src/services/auth.py', 9, 'call');
        INSERT INTO references_ VALUES
            (5, 1, 'src/services/auth.py', 8, 'type_annotation');

        -- Sample file dependencies
        INSERT INTO file_dependencies VALUES
            ('src/services/auth.py', 'src/models/user.py');
        INSERT INTO file_dependencies VALUES
            ('src/repos/user_repo.py', 'src/models/user.py');
    """)
    conn.close()
    return db


# ---------------------------------------------------------------------------
# Open / close / context-manager
# ---------------------------------------------------------------------------

class TestAstIndexOpen:
    def test_open_valid_db(self, db_path: Path):
        idx = AstIndex(db_path)
        assert idx is not None
        idx.close()

    def test_open_nonexistent_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            AstIndex(tmp_path / "nonexistent.db")

    def test_context_manager(self, db_path: Path):
        with AstIndex(db_path) as idx:
            syms = idx.symbols()
            assert len(syms) > 0


# ---------------------------------------------------------------------------
# Symbol queries
# ---------------------------------------------------------------------------

class TestSymbols:
    def test_all_symbols(self, db_path: Path):
        with AstIndex(db_path) as idx:
            syms = idx.symbols()
            assert len(syms) == 9

    def test_filter_by_file(self, db_path: Path):
        with AstIndex(db_path) as idx:
            syms = idx.symbols(file="src/models/user.py")
            names = [s.name for s in syms]
            assert "User" in names
            assert "AdminUser" in names
            assert "AuthService" not in names

    def test_filter_by_kind(self, db_path: Path):
        with AstIndex(db_path) as idx:
            syms = idx.symbols(kind="class")
            assert all(s.kind == "class" for s in syms)
            names = [s.name for s in syms]
            assert "User" in names
            assert "__init__" not in names

    def test_filter_by_name(self, db_path: Path):
        with AstIndex(db_path) as idx:
            syms = idx.symbols(name="User")
            assert len(syms) == 1
            assert syms[0].name == "User"
            assert syms[0].qualified_name == "src.models.user.User"

    def test_filter_combined(self, db_path: Path):
        with AstIndex(db_path) as idx:
            syms = idx.symbols(file="src/models/user.py", kind="class")
            names = [s.name for s in syms]
            assert set(names) == {"User", "AdminUser"}

    def test_symbol_fields(self, db_path: Path):
        with AstIndex(db_path) as idx:
            syms = idx.symbols(name="User")
            s = syms[0]
            assert s.name == "User"
            assert s.qualified_name == "src.models.user.User"
            assert s.kind == "class"
            assert s.file == "src/models/user.py"
            assert s.line_start == 1
            assert s.line_end == 7

    def test_no_match_returns_empty(self, db_path: Path):
        with AstIndex(db_path) as idx:
            syms = idx.symbols(name="NonExistent")
            assert syms == []


# ---------------------------------------------------------------------------
# Usage queries
# ---------------------------------------------------------------------------

class TestUsages:
    def test_usages_of_symbol(self, db_path: Path):
        with AstIndex(db_path) as idx:
            usages = idx.usages("User")
            assert len(usages) >= 2
            files = [u.file for u in usages]
            assert "src/services/auth.py" in files
            assert "src/repos/user_repo.py" in files

    def test_usage_fields(self, db_path: Path):
        with AstIndex(db_path) as idx:
            usages = idx.usages("find_by_email")
            assert len(usages) == 1
            u = usages[0]
            assert u.symbol == "find_by_email"
            assert u.file == "src/services/auth.py"
            assert u.line == 9
            assert u.kind == "call"

    def test_no_usages(self, db_path: Path):
        with AstIndex(db_path) as idx:
            usages = idx.usages("save")
            assert usages == []


# ---------------------------------------------------------------------------
# Dependency queries
# ---------------------------------------------------------------------------

class TestDependencies:
    def test_dependencies(self, db_path: Path):
        with AstIndex(db_path) as idx:
            deps = idx.dependencies("src/services/auth.py")
            assert "src/models/user.py" in deps

    def test_dependents(self, db_path: Path):
        with AstIndex(db_path) as idx:
            deps = idx.dependents("src/models/user.py")
            assert "src/services/auth.py" in deps
            assert "src/repos/user_repo.py" in deps

    def test_no_dependencies(self, db_path: Path):
        with AstIndex(db_path) as idx:
            deps = idx.dependencies("src/models/user.py")
            assert deps == []

    def test_no_dependents(self, db_path: Path):
        with AstIndex(db_path) as idx:
            deps = idx.dependents("src/services/auth.py")
            assert deps == []
