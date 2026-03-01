import pickle
from pathlib import Path

import networkx as nx

from code_brain.ingestion.ast_index import Symbol, ModuleDep, Usage
from code_brain.ingestion.git_analyzer import HotSpot, CoChange


class GraphBuilder:
    def build(
        self,
        symbols: list[Symbol],
        inheritance: dict[str, list[str]],
        module_deps: list[ModuleDep],
        usages: dict[str, list[Usage]],
        hot_spots: list[HotSpot] | None = None,
        co_changes: list[CoChange] | None = None,
    ) -> nx.DiGraph:
        g = nx.DiGraph()

        name_to_id: dict[str, int] = {}
        file_to_symbols: dict[str, list[int]] = {}

        for sym in symbols:
            g.add_node(
                sym.id,
                type="symbol",
                kind=sym.kind,
                name=sym.name,
                file_path=sym.file_path,
                line=sym.line,
                signature=sym.signature,
                parent_id=sym.parent_id,
                change_frequency=0,
            )
            name_to_id[sym.name] = sym.id
            file_to_symbols.setdefault(sym.file_path, []).append(sym.id)

        for child_name, parent_names in inheritance.items():
            child_id = name_to_id.get(child_name)
            if child_id is None:
                continue
            for parent_name in parent_names:
                parent_id = name_to_id.get(parent_name)
                if parent_id is not None:
                    g.add_edge(child_id, parent_id, type="inherits")

        for dep in module_deps:
            g.add_edge(
                f"mod:{dep.source}", f"mod:{dep.target}",
                type="module_dep", kind=dep.kind,
            )

        for symbol_name, usage_list in usages.items():
            target_id = name_to_id.get(symbol_name)
            if target_id is None:
                continue
            for usage in usage_list:
                source_ids = file_to_symbols.get(usage.file_path, [])
                for source_id in source_ids:
                    if source_id != target_id:
                        g.add_edge(source_id, target_id, type="uses",
                                   line=usage.line, context=usage.context)
                        break

        if hot_spots:
            for spot in hot_spots:
                for sym_id in file_to_symbols.get(spot.file_path, []):
                    if sym_id in g:
                        g.nodes[sym_id]["change_frequency"] = spot.change_count

        if co_changes:
            for cc in co_changes:
                ids_a = file_to_symbols.get(cc.file_a, [])
                ids_b = file_to_symbols.get(cc.file_b, [])
                if ids_a and ids_b:
                    g.add_edge(
                        ids_a[0], ids_b[0],
                        type="co_changed", weight=cc.count,
                    )

        return g

    def save(self, graph: nx.DiGraph, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(graph, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, path: Path) -> nx.DiGraph:
        with open(path, "rb") as f:
            return pickle.load(f)
