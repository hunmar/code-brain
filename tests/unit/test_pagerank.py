# code-brain/tests/unit/test_pagerank.py
import networkx as nx
import pytest
from code_brain.graph.pagerank import PageRankScorer, RankedNode


@pytest.fixture
def sample_graph():
    g = nx.DiGraph()
    g.add_node(1, name="User", kind="class", file_path="models/user.py",
               line=1, signature="class User", change_frequency=5)
    g.add_node(2, name="AdminUser", kind="class", file_path="models/user.py",
               line=10, signature="class AdminUser", change_frequency=0)
    g.add_node(3, name="AuthService", kind="class", file_path="services/auth.py",
               line=1, signature="class AuthService", change_frequency=2)
    g.add_node(4, name="UserRepo", kind="class", file_path="repos/user_repo.py",
               line=1, signature="class UserRepo", change_frequency=1)

    g.add_edge(2, 1, type="inherits")
    g.add_edge(3, 1, type="uses")
    g.add_edge(3, 4, type="uses")
    g.add_edge(4, 1, type="uses")
    return g


def test_rank_all(sample_graph):
    scorer = PageRankScorer(sample_graph)
    ranked = scorer.rank()
    assert len(ranked) == 4
    assert all(isinstance(r, RankedNode) for r in ranked)
    # User should be most central (most incoming edges)
    assert ranked[0].node_id == 1


def test_rank_with_focus(sample_graph):
    scorer = PageRankScorer(sample_graph)
    ranked = scorer.rank(focus_nodes=[3])  # Focus on AuthService
    assert len(ranked) == 4
    # AuthService or its direct connections should rank high
    top_ids = [r.node_id for r in ranked[:2]]
    assert 3 in top_ids or 1 in top_ids


def test_rank_with_limit(sample_graph):
    scorer = PageRankScorer(sample_graph)
    ranked = scorer.rank(limit=2)
    assert len(ranked) == 2


def test_ranked_node_has_score(sample_graph):
    scorer = PageRankScorer(sample_graph)
    ranked = scorer.rank()
    for r in ranked:
        assert r.score > 0
        assert r.name is not None
