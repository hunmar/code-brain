from code_brain.ingestion.ast_index import ASTIndexReader


class StructuralQueryEngine:
    def __init__(self, reader: ASTIndexReader):
        self._reader = reader

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

    def outline(self, file_path: str) -> list[dict]:
        symbols = self._reader.get_file_outline(file_path)
        return [
            {
                "name": s.name,
                "kind": s.kind,
                "line": s.line,
                "signature": s.signature,
            }
            for s in symbols
        ]
