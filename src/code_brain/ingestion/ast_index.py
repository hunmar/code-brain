# code-brain/src/code_brain/ingestion/ast_index.py
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Symbol:
    id: int
    name: str
    kind: str
    file_path: str
    line: int
    signature: str
    parent_id: int | None = None


@dataclass(frozen=True)
class Usage:
    file_path: str
    line: int
    context: str


@dataclass(frozen=True)
class ModuleDep:
    source: str
    target: str
    kind: str


def _find_ast_index_bin() -> str:
    """Find the ast-index binary, checking common install locations."""
    import shutil
    found = shutil.which("ast-index")
    if found:
        return found
    # Check common cargo install location
    cargo_bin = Path.home() / ".cargo" / "bin" / "ast-index"
    if cargo_bin.is_file():
        return str(cargo_bin)
    return "ast-index"


def _discover_db_path(project_root: Path) -> Path:
    """Find the ast-index database, trying `ast-index db-path` first, then local fallback."""
    ast_bin = _find_ast_index_bin()
    try:
        result = subprocess.run(
            [ast_bin, "db-path"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            db = Path(result.stdout.strip())
            if db.is_file():
                return db
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Fallback: check local .ast-index directory
    return project_root / ".ast-index" / "db.sqlite3"


class ASTIndexReader:
    def __init__(self, project_root: Path):
        self._project_root = project_root
        self._db_path = _discover_db_path(project_root)
        self._conn: sqlite3.Connection | None = None

    def is_available(self) -> bool:
        return self._db_path.is_file()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                f"file:{self._db_path}?mode=ro", uri=True
            )
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def get_symbols(self) -> list[Symbol]:
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT s.id, s.name, s.kind, f.path, s.line, s.signature, s.parent_id
            FROM symbols s
            JOIN files f ON s.file_id = f.id
        """).fetchall()
        return [Symbol(
            id=r["id"], name=r["name"], kind=r["kind"],
            file_path=r["path"], line=r["line"],
            signature=r["signature"] or "", parent_id=r["parent_id"]
        ) for r in rows]

    def find_symbols(self, name: str | None = None, kind: str | None = None,
                     limit: int = 100) -> list[Symbol]:
        conn = self._get_conn()
        conditions = []
        params = []
        if name:
            conditions.append("s.name = ?")
            params.append(name)
        if kind:
            conditions.append("s.kind = ?")
            params.append(kind)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = conn.execute(f"""
            SELECT s.id, s.name, s.kind, f.path, s.line, s.signature, s.parent_id
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            {where}
            LIMIT ?
        """, params + [limit]).fetchall()
        return [Symbol(
            id=r["id"], name=r["name"], kind=r["kind"],
            file_path=r["path"], line=r["line"],
            signature=r["signature"] or "", parent_id=r["parent_id"]
        ) for r in rows]

    def get_parents(self, class_name: str) -> list[str]:
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT i.parent_name
            FROM inheritance i
            JOIN symbols s ON i.child_id = s.id
            WHERE s.name = ?
        """, (class_name,)).fetchall()
        return [r["parent_name"] for r in rows]

    def get_usages(self, symbol_name: str, limit: int = 100) -> list[Usage]:
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT f.path, r.line, r.context
            FROM refs r
            JOIN files f ON r.file_id = f.id
            WHERE r.name = ?
            LIMIT ?
        """, (symbol_name, limit)).fetchall()
        return [Usage(
            file_path=r["path"], line=r["line"], context=r["context"] or ""
        ) for r in rows]

    def get_module_deps(self, module_name: str) -> list[ModuleDep]:
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT m1.name as src, m2.name as dst, md.dep_kind
            FROM module_deps md
            JOIN modules m1 ON md.module_id = m1.id
            JOIN modules m2 ON md.dep_module_id = m2.id
            WHERE m1.name = ?
        """, (module_name,)).fetchall()
        return [ModuleDep(
            source=r["src"], target=r["dst"], kind=r["dep_kind"]
        ) for r in rows]

    def get_file_outline(self, file_path: str) -> list[Symbol]:
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT s.id, s.name, s.kind, f.path, s.line, s.signature, s.parent_id
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE f.path = ?
            ORDER BY s.line
        """, (file_path,)).fetchall()
        return [Symbol(
            id=r["id"], name=r["name"], kind=r["kind"],
            file_path=r["path"], line=r["line"],
            signature=r["signature"] or "", parent_id=r["parent_id"]
        ) for r in rows]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
