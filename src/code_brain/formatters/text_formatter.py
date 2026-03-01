class TextFormatter:
    def format_symbols(self, symbols: list[dict]) -> str:
        lines = []
        for s in symbols:
            loc = f"{s['file_path']}:{s['line']}"
            sig = s.get("signature", "")
            lines.append(f"  {s['kind']} {s['name']}  ({loc})")
            if sig:
                lines.append(f"    {sig}")
        return "\n".join(lines) if lines else "No results found."

    def format_hierarchy(self, hierarchy: dict) -> str:
        cls = hierarchy["class"]
        parents = hierarchy.get("parents", [])
        if not parents:
            return f"{cls} (no parents)"
        tree = " <- ".join([cls] + parents)
        return tree

    def format_usages(self, usages: list[dict]) -> str:
        lines = []
        for u in usages:
            lines.append(f"  {u['file_path']}:{u['line']}  {u.get('context', '')}")
        return "\n".join(lines) if lines else "No usages found."

    def format_deps(self, deps: list[dict]) -> str:
        lines = []
        for d in deps:
            lines.append(f"  {d['source']} -> {d['target']} ({d['kind']})")
        return "\n".join(lines) if lines else "No dependencies found."
