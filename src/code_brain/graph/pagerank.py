"""PageRank-based relevance scoring for code graphs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import networkx as nx


@dataclass(frozen=True)
class ScoredNode:
    """A graph node with its PageRank score."""

    node_id: str
    score: float
    node_data: dict[str, Any]


class PageRankScorer:
    """Scores code graph nodes using personalized PageRank.

    Wraps networkx.pagerank with support for personalization vectors,
    node-type filtering, and top-N retrieval.
    """

    def __init__(
        self,
        alpha: float = 0.85,
        max_iter: int = 100,
        tol: float = 1e-6,
    ):
        self.alpha = alpha
        self.max_iter = max_iter
        self.tol = tol

    def score(
        self,
        graph: nx.DiGraph,
        personalization: dict[str, float] | None = None,
    ) -> list[ScoredNode]:
        """Run PageRank on the graph and return scored nodes sorted by score descending."""
        if len(graph) == 0:
            return []

        scores = nx.pagerank(
            graph,
            alpha=self.alpha,
            personalization=personalization,
            max_iter=self.max_iter,
            tol=self.tol,
        )

        return sorted(
            [
                ScoredNode(
                    node_id=node_id,
                    score=score,
                    node_data=dict(graph.nodes[node_id]),
                )
                for node_id, score in scores.items()
            ],
            key=lambda n: n.score,
            reverse=True,
        )

    def score_filtered(
        self,
        graph: nx.DiGraph,
        node_type: str,
        personalization: dict[str, float] | None = None,
    ) -> list[ScoredNode]:
        """Run PageRank and return only nodes matching the given type."""
        all_scored = self.score(graph, personalization)
        return [n for n in all_scored if n.node_data.get("type") == node_type]

    def top_n(
        self,
        graph: nx.DiGraph,
        n: int,
        personalization: dict[str, float] | None = None,
    ) -> list[ScoredNode]:
        """Return the top N nodes by PageRank score."""
        return self.score(graph, personalization)[:n]
