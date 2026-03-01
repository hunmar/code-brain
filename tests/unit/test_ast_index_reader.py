# code-brain/tests/unit/test_ast_index_reader.py
import sqlite3
import pytest
from pathlib import Path
from code_brain.ingestion.ast_index import ASTIndexReader, Symbol, ModuleDep


@pytest.fixture
def sample_db(tmp_path):
    """Create a minimal ast-index SQLite DB for testing."""
    db_path = tmp_path / ".ast-index" / "db.sqlite3"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE files (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            mtime INTEGER,
            size INTEGER
        );
        CREATE TABLE symbols (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            name TEXT,
            kind TEXT,
            line INTEGER,
            parent_id INTEGER,
            signature TEXT
        );
        CREATE TABLE inheritance (
            child_id INTEGER,
            parent_name TEXT,
            kind TEXT
        );
        CREATE TABLE modules (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            path TEXT,
            kind TEXT
        );
        CREATE TABLE module_deps (
            module_id INTEGER,
            dep_module_id INTEGER,
            dep_kind TEXT
        );
        CREATE TABLE refs (
            file_id INTEGER,
            name TEXT,
            line INTEGER,
            context TEXT
        );

        INSERT INTO files VALUES (1, 'src/models/user.py', 1000, 500);
        INSERT INTO files VALUES (2, 'src/services/auth.py', 1000, 300);

        INSERT INTO symbols VALUES (1, 1, 'User', 'class', 1, NULL, 'class User');
        INSERT INTO symbols VALUES (2, 1, 'AdminUser', 'class', 10, NULL, 'class AdminUser(User)');
        INSERT INTO symbols VALUES (3, 1, 'display_name', 'function', 5, 1, 'def display_name(self) -> str');
        INSERT INTO symbols VALUES (4, 2, 'AuthService', 'class', 3, NULL, 'class AuthService');
        INSERT INTO symbols VALUES (5, 2, 'authenticate', 'function', 7, 4, 'def authenticate(self, email, password)');

        INSERT INTO inheritance VALUES (2, 'User', 'extends');

        INSERT INTO modules VALUES (1, 'models', 'src/models', 'package');
        INSERT INTO modules VALUES (2, 'services', 'src/services', 'package');

        INSERT INTO module_deps VALUES (2, 1, 'import');

        INSERT INTO refs VALUES (2, 'User', 3, 'from src.models.user import User');
        INSERT INTO refs VALUES (2, 'User', 10, 'user: User = ...');
    """)
    conn.close()
    return tmp_path


def test_reader_opens_db(sample_db):
    reader = ASTIndexReader(sample_db)
    assert reader.is_available()


def test_reader_not_available(tmp_path):
    reader = ASTIndexReader(tmp_path)
    assert not reader.is_available()


def test_get_all_symbols(sample_db):
    reader = ASTIndexReader(sample_db)
    symbols = reader.get_symbols()
    assert len(symbols) == 5
    assert all(isinstance(s, Symbol) for s in symbols)


def test_find_symbol_by_name(sample_db):
    reader = ASTIndexReader(sample_db)
    results = reader.find_symbols("User")
    assert len(results) == 1
    assert results[0].name == "User"
    assert results[0].kind == "class"


def test_find_symbol_by_kind(sample_db):
    reader = ASTIndexReader(sample_db)
    results = reader.find_symbols(kind="function")
    assert len(results) == 2


def test_get_hierarchy(sample_db):
    reader = ASTIndexReader(sample_db)
    parents = reader.get_parents("AdminUser")
    assert "User" in parents


def test_get_usages(sample_db):
    reader = ASTIndexReader(sample_db)
    usages = reader.get_usages("User")
    assert len(usages) == 2
    assert all(u.file_path == "src/services/auth.py" for u in usages)


def test_get_module_deps(sample_db):
    reader = ASTIndexReader(sample_db)
    deps = reader.get_module_deps("services")
    assert len(deps) == 1
    assert deps[0].target == "models"


def test_get_file_outline(sample_db):
    reader = ASTIndexReader(sample_db)
    symbols = reader.get_file_outline("src/models/user.py")
    assert len(symbols) == 3
    names = [s.name for s in symbols]
    assert "User" in names
    assert "AdminUser" in names
