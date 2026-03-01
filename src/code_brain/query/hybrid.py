import networkx as nx

from code_brain.query.structural import StructuralQueryEngine
from code_brain.query.semantic import SemanticQueryEngine


class HybridQueryEngine:
    def __init__(
        self,
        structural: StructuralQueryEngine,
        semantic: SemanticQueryEngine,
        graph: nx.DiGraph,
    ):
        self._structural = structural
        self._semantic = semantic
        self._graph = graph

    async def impact(self, symbol_name: str, token_budget: int = 8000) -> dict:
        found = self._structural.find(symbol_name)
        if not found:
            return {"symbol": symbol_name, "error": "Symbol not found"}

        symbol_info = found[0]
        node_id = symbol_info["id"]

        dependents = []
        if node_id in self._graph:
            dependents = [
                self._graph.nodes[pred]
                for pred in self._graph.predecessors(node_id)
                if self._graph.nodes.get(pred, {}).get("type") == "symbol"
            ]

        semantic = await self._semantic.ask(
            f"What is the business impact of {symbol_name}?"
        )

        change_freq = self._graph.nodes.get(node_id, {}).get("change_frequency", 0)
        dep_count = len(dependents)
        risk = "high" if dep_count > 5 or change_freq > 3 else (
            "medium" if dep_count > 2 or change_freq > 1 else "low"
        )

        return {
            "symbol": symbol_name,
            "location": f"{symbol_info['file_path']}:{symbol_info['line']}",
            "dependents": [
                {"name": d.get("name", "?"), "file_path": d.get("file_path", "?")}
                for d in dependents
            ],
            "dependent_count": dep_count,
            "change_frequency": change_freq,
            "risk_level": risk,
            "semantic_context": semantic,
        }

    async def dead_code(self) -> list[dict]:
        dead = []
        for node_id, data in self._graph.nodes(data=True):
            if data.get("type") != "symbol":
                continue
            name = data.get("name", "")
            usages = self._structural.usages(name, limit=1)
            if not usages:
                dead.append({
                    "name": name,
                    "kind": data.get("kind", ""),
                    "file_path": data.get("file_path", ""),
                    "line": data.get("line", 0),
                })
        return dead
