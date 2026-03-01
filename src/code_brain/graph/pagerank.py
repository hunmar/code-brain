# code-brain/src/code_brain/graph/pagerank.py
from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True)
class RankedNode:
    node_id: int | str
    score: float
    name: str
    kind: str
    file_path: str
    line: int


class PageRankScorer:
    def __init__(self, graph: nx.DiGraph):
        self._graph = graph

    def rank(
        self,
        focus_nodes: list[int | str] | None = None,
        alpha: float = 0.85,
        limit: int | None = None,
    ) -> list[RankedNode]:
        personalization = None
        if focus_nodes:
            personalization = {n: 0.0 for n in self._graph.nodes}
            for node in focus_nodes:
                if node in personalization:
                    personalization[node] = 1.0 / len(focus_nodes)

        try:
            scores = nx.pagerank(
                self._graph,
                alpha=alpha,
                personalization=personalization,
            )
        except nx.PowerIterationFailedConvergence:
            scores = {n: 1.0 / len(self._graph) for n in self._graph.nodes}

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        result = []
        for node_id, score in ranked:
            data = self._graph.nodes.get(node_id, {})
            result.append(RankedNode(
                node_id=node_id,
                score=score,
                name=data.get("name", ""),
                kind=data.get("kind", ""),
                file_path=data.get("file_path", ""),
                line=data.get("line", 0),
            ))

        if limit:
            result = result[:limit]
        return result
