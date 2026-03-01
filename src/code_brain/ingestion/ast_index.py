"""AST index SQLite reader – symbol, usage, and dependency queries."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Symbol:
    """A code symbol extracted from the AST index."""

    name: str
    qualified_name: str
    kind: str
    file: str
    line_start: int
    line_end: int


@dataclass(frozen=True)
class Usage:
    """A reference to a symbol found in the codebase."""

    symbol: str
    file: str
    line: int
    kind: str


class AstIndex:
    """Read-only wrapper around an ast-index SQLite database.

    Provides queries for symbols, usages (references), and file-level
    dependency information.
    """

    def __init__(self, db_path: str | Path) -> None:
        db_path = Path(db_path)
        if not db_path.exists():
            raise FileNotFoundError(f"AST index not found: {db_path}")
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row

    # -- context manager -----------------------------------------------------

    def __enter__(self) -> AstIndex:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    # -- symbol queries ------------------------------------------------------

    def symbols(
        self,
        *,
        file: str | None = None,
        kind: str | None = None,
        name: str | None = None,
    ) -> list[Symbol]:
        """Return symbols, optionally filtered by file, kind, or name."""
        clauses: list[str] = []
        params: list[str] = []
        if file is not None:
            clauses.append("file_path = ?")
            params.append(file)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if name is not None:
            clauses.append("name = ?")
            params.append(name)

        sql = "SELECT name, qualified_name, kind, file_path, line_start, line_end FROM symbols"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        rows = self._conn.execute(sql, params).fetchall()
        return [
            Symbol(
                name=r["name"],
                qualified_name=r["qualified_name"],
                kind=r["kind"],
                file=r["file_path"],
                line_start=r["line_start"],
                line_end=r["line_end"],
            )
            for r in rows
        ]

    # -- usage queries -------------------------------------------------------

    def usages(self, symbol_name: str) -> list[Usage]:
        """Return all references to *symbol_name* across the codebase."""
        sql = """
            SELECT s.name, r.file_path, r.line, r.kind
            FROM references_ r
            JOIN symbols s ON s.id = r.symbol_id
            WHERE s.name = ?
        """
        rows = self._conn.execute(sql, (symbol_name,)).fetchall()
        return [
            Usage(
                symbol=r["name"],
                file=r["file_path"],
                line=r["line"],
                kind=r["kind"],
            )
            for r in rows
        ]

    # -- dependency queries --------------------------------------------------

    def dependencies(self, file_path: str) -> list[str]:
        """Return files that *file_path* depends on (imports from)."""
        sql = "SELECT target_file FROM file_dependencies WHERE source_file = ?"
        rows = self._conn.execute(sql, (file_path,)).fetchall()
        return [r["target_file"] for r in rows]

    def dependents(self, file_path: str) -> list[str]:
        """Return files that depend on (import from) *file_path*."""
        sql = "SELECT source_file FROM file_dependencies WHERE target_file = ?"
        rows = self._conn.execute(sql, (file_path,)).fetchall()
        return [r["source_file"] for r in rows]
