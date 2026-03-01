# code-brain/src/code_brain/graph/queries.py
from __future__ import annotations

import networkx as nx

from code_brain.graph.pagerank import PageRankScorer
from code_brain.query.budgeter import ContextBudgeter, ContextEntry


class GraphQueryEngine:
    def __init__(self, graph: nx.DiGraph):
        self._graph = graph
        self._scorer = PageRankScorer(graph)
        self._budgeter = ContextBudgeter()

    def repo_map(
        self,
        focus_files: list[str] | None = None,
        token_budget: int = 4000,
    ) -> str:
        focus_nodes = None
        if focus_files:
            focus_nodes = [
                n for n, d in self._graph.nodes(data=True)
                if d.get("file_path") in focus_files
            ]

        ranked = self._scorer.rank(focus_nodes=focus_nodes)

        entries = []
        for rn in ranked:
            if not rn.name:
                continue
            data = self._graph.nodes.get(rn.node_id, {})
            entries.append(ContextEntry(
                name=rn.name,
                kind=rn.kind,
                file_path=rn.file_path,
                line=rn.line,
                signature=data.get("signature", ""),
            ))

        return self._budgeter.format(entries, token_budget)

    def hotspots(self, limit: int = 10) -> list[dict]:
        symbol_nodes = [
            (n, d) for n, d in self._graph.nodes(data=True)
            if d.get("type") == "symbol" and d.get("change_frequency", 0) > 0
        ]
        symbol_nodes.sort(key=lambda x: x[1].get("change_frequency", 0), reverse=True)
        symbol_nodes = symbol_nodes[:limit]

        return [
            {
                "name": d.get("name", ""),
                "kind": d.get("kind", ""),
                "file_path": d.get("file_path", ""),
                "change_frequency": d.get("change_frequency", 0),
            }
            for _, d in symbol_nodes
        ]

    def architecture(self, fmt: str = "mermaid") -> str:
        module_nodes = [
            (n, d) for n, d in self._graph.nodes(data=True)
            if d.get("type") == "module"
        ]
        module_edges = [
            (u, v) for u, v, d in self._graph.edges(data=True)
            if d.get("type") == "module_dep"
        ]

        if fmt == "mermaid":
            return self._mermaid_diagram(module_nodes, module_edges)
        return self._text_diagram(module_nodes, module_edges)

    def _module_label(self, node_id: int | str) -> str:
        s = str(node_id)
        if s.startswith("mod:"):
            return s[4:]
        return s

    def _mermaid_diagram(
        self,
        nodes: list[tuple],
        edges: list[tuple],
    ) -> str:
        lines = ["graph TD"]
        for node_id, _ in nodes:
            label = self._module_label(node_id)
            safe_id = label.replace("/", "_").replace(".", "_")
            lines.append(f"    {safe_id}[{label}]")
        for u, v in edges:
            src = self._module_label(u).replace("/", "_").replace(".", "_")
            dst = self._module_label(v).replace("/", "_").replace(".", "_")
            lines.append(f"    {src} --> {dst}")
        return "\n".join(lines)

    def _text_diagram(
        self,
        nodes: list[tuple],
        edges: list[tuple],
    ) -> str:
        lines = ["Architecture:"]
        lines.append("Modules:")
        for node_id, _ in nodes:
            lines.append(f"  - {self._module_label(node_id)}")
        if edges:
            lines.append("Dependencies:")
            for u, v in edges:
                lines.append(f"  {self._module_label(u)} -> {self._module_label(v)}")
        return "\n".join(lines)
