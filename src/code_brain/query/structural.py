from pathlib import Path

from code_brain.ingestion.ast_index import ASTIndexReader


class StructuralQueryEngine:
    def __init__(self, reader: ASTIndexReader, project_root: Path | None = None):
        self._reader = reader
        self._project_root = project_root

    def find(self, name: str | None = None, kind: str | None = None,
             limit: int = 100) -> list[dict]:
        symbols = self._reader.find_symbols(name=name, kind=kind, limit=limit)
        return [
            {
                "id": s.id,
                "name": s.name,
                "kind": s.kind,
                "file_path": s.file_path,
                "line": s.line,
                "signature": s.signature,
            }
            for s in symbols
        ]

    def hierarchy(self, class_name: str) -> dict:
        parents = self._reader.get_parents(class_name)
        return {"class": class_name, "parents": parents}

    def usages(self, symbol: str, limit: int = 100) -> list[dict]:
        usages = self._reader.get_usages(symbol, limit=limit)
        return [
            {"file_path": u.file_path, "line": u.line, "context": u.context}
            for u in usages
        ]

    def deps(self, module: str) -> list[dict]:
        deps = self._reader.get_module_deps(module)
        return [
            {"source": d.source, "target": d.target, "kind": d.kind}
            for d in deps
        ]

    def outline(self, file_path: str, project_root: Path | None = None) -> list[dict]:
        root = project_root or self._project_root
        normalized = file_path

        # Strip leading ./
        if normalized.startswith("./"):
            normalized = normalized[2:]

        # Strip project root prefix if absolute path
        if root and normalized.startswith(str(root)):
            normalized = normalized[len(str(root)):].lstrip("/")

        # Try exact match first
        symbols = self._reader.get_file_outline(normalized)

        # Fallback: suffix match (user gave "user.py", DB has "src/models/user.py")
        if not symbols and "/" not in normalized:
            symbols = self._reader.get_file_outline_by_suffix(normalized)

        return [
            {
                "name": s.name,
                "kind": s.kind,
                "line": s.line,
                "signature": s.signature,
            }
            for s in symbols
        ]
