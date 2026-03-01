import sqlite3
import pytest
from pathlib import Path
from code_brain.query.structural import StructuralQueryEngine
from code_brain.ingestion.ast_index import ASTIndexReader


@pytest.fixture
def sample_db(tmp_path):
    db_path = tmp_path / ".ast-index" / "db.sqlite3"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE files (id INTEGER PRIMARY KEY, path TEXT UNIQUE, mtime INTEGER, size INTEGER);
        CREATE TABLE symbols (id INTEGER PRIMARY KEY, file_id INTEGER, name TEXT, kind TEXT,
                              line INTEGER, parent_id INTEGER, signature TEXT);
        CREATE TABLE inheritance (child_id INTEGER, parent_name TEXT, kind TEXT);
        CREATE TABLE modules (id INTEGER PRIMARY KEY, name TEXT UNIQUE, path TEXT, kind TEXT);
        CREATE TABLE module_deps (module_id INTEGER, dep_module_id INTEGER, dep_kind TEXT);
        CREATE TABLE refs (file_id INTEGER, name TEXT, line INTEGER, context TEXT);

        INSERT INTO files VALUES (1, 'src/models/user.py', 1000, 500);
        INSERT INTO files VALUES (2, 'src/services/auth.py', 1000, 300);
        INSERT INTO symbols VALUES (1, 1, 'User', 'class', 1, NULL, 'class User');
        INSERT INTO symbols VALUES (2, 1, 'AdminUser', 'class', 10, NULL, 'class AdminUser(User)');
        INSERT INTO symbols VALUES (3, 2, 'AuthService', 'class', 3, NULL, 'class AuthService');
        INSERT INTO inheritance VALUES (2, 'User', 'extends');
        INSERT INTO modules VALUES (1, 'models', 'src/models', 'package');
        INSERT INTO modules VALUES (2, 'services', 'src/services', 'package');
        INSERT INTO module_deps VALUES (2, 1, 'import');
        INSERT INTO refs VALUES (2, 'User', 3, 'from models import User');
    """)
    conn.close()
    return tmp_path


@pytest.fixture
def engine(sample_db):
    reader = ASTIndexReader(sample_db)
    return StructuralQueryEngine(reader)


def test_find_class(engine):
    result = engine.find("User", kind="class")
    assert len(result) == 1
    assert result[0]["name"] == "User"


def test_find_by_name_only(engine):
    result = engine.find("AuthService")
    assert len(result) == 1


def test_hierarchy(engine):
    result = engine.hierarchy("AdminUser")
    assert "User" in result["parents"]


def test_usages(engine):
    result = engine.usages("User")
    assert len(result) >= 1
    assert result[0]["file_path"] == "src/services/auth.py"


def test_deps(engine):
    result = engine.deps("services")
    assert any(d["target"] == "models" for d in result)


def test_outline(engine):
    result = engine.outline("src/models/user.py")
    assert len(result) == 2
    names = [s["name"] for s in result]
    assert "User" in names
