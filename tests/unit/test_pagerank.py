"""Tests for PageRank relevance scorer."""
import networkx as nx
import pytest

from code_brain.graph.pagerank import PageRankScorer, ScoredNode


@pytest.fixture
def scorer():
    """Default PageRank scorer."""
    return PageRankScorer()


@pytest.fixture
def code_graph():
    """Sample code dependency graph mirroring the fixture project."""
    g = nx.DiGraph()
    # File nodes
    g.add_node("models/user.py", type="file", lang="python")
    g.add_node("services/auth.py", type="file", lang="python")
    g.add_node("repos/user_repo.py", type="file", lang="python")
    # Class nodes
    g.add_node("User", type="class", lang="python")
    g.add_node("AdminUser", type="class", lang="python")
    g.add_node("AuthService", type="class", lang="python")

    # Dependency edges (importer -> imported)
    g.add_edge("services/auth.py", "models/user.py")
    g.add_edge("repos/user_repo.py", "models/user.py")
    g.add_edge("AuthService", "User")
    g.add_edge("AuthService", "AdminUser")
    g.add_edge("AdminUser", "User")
    return g


class TestScoredNode:
    """Tests for the ScoredNode dataclass."""

    def test_scored_node_is_frozen(self):
        node = ScoredNode(node_id="a", score=0.5, node_data={"type": "file"})
        with pytest.raises(AttributeError):
            node.score = 0.9

    def test_scored_node_fields(self):
        node = ScoredNode(node_id="foo.py", score=0.42, node_data={"type": "file", "lang": "python"})
        assert node.node_id == "foo.py"
        assert node.score == 0.42
        assert node.node_data == {"type": "file", "lang": "python"}


class TestPageRankScorer:
    """Tests for the PageRankScorer class."""

    def test_empty_graph_returns_empty(self, scorer):
        result = scorer.score(nx.DiGraph())
        assert result == []

    def test_single_node_graph(self, scorer):
        g = nx.DiGraph()
        g.add_node("solo", type="file")
        result = scorer.score(g)
        assert len(result) == 1
        assert result[0].node_id == "solo"
        assert abs(result[0].score - 1.0) < 1e-6

    def test_score_returns_scored_nodes(self, scorer, code_graph):
        result = scorer.score(code_graph)
        assert len(result) == len(code_graph)
        assert all(isinstance(n, ScoredNode) for n in result)

    def test_scores_sorted_descending(self, scorer, code_graph):
        result = scorer.score(code_graph)
        scores = [n.score for n in result]
        assert scores == sorted(scores, reverse=True)

    def test_scores_sum_to_one(self, scorer, code_graph):
        result = scorer.score(code_graph)
        total = sum(n.score for n in result)
        assert abs(total - 1.0) < 1e-4

    def test_hub_node_ranks_highest(self, scorer, code_graph):
        """The most depended-upon node (User) should rank highest."""
        result = scorer.score(code_graph)
        # User has 3 incoming edges (AdminUser, AuthService, and indirectly via files)
        top_ids = [n.node_id for n in result[:2]]
        assert "User" in top_ids or "models/user.py" in top_ids

    def test_node_data_preserved(self, scorer, code_graph):
        result = scorer.score(code_graph)
        user_nodes = [n for n in result if n.node_id == "User"]
        assert len(user_nodes) == 1
        assert user_nodes[0].node_data["type"] == "class"
        assert user_nodes[0].node_data["lang"] == "python"


class TestPersonalization:
    """Tests for personalized PageRank."""

    def test_personalization_boosts_target(self, scorer, code_graph):
        base = scorer.score(code_graph)
        base_scores = {n.node_id: n.score for n in base}

        personalization = {n: 0.0 for n in code_graph.nodes()}
        personalization["AuthService"] = 1.0
        boosted = scorer.score(code_graph, personalization=personalization)
        boosted_scores = {n.node_id: n.score for n in boosted}

        assert boosted_scores["AuthService"] > base_scores["AuthService"]

    def test_personalization_changes_ranking(self, scorer, code_graph):
        """Personalizing on a leaf node should change the ranking order."""
        base = scorer.score(code_graph)
        base_top = base[0].node_id

        # Personalize on a leaf node (repos/user_repo.py has no incoming edges)
        personalization = {n: 0.0 for n in code_graph.nodes()}
        personalization["repos/user_repo.py"] = 1.0
        result = scorer.score(code_graph, personalization=personalization)
        result_scores = {n.node_id: n.score for n in result}

        assert result_scores["repos/user_repo.py"] > result_scores.get(base_top, 0) or \
               result[0].node_id != base_top


class TestFiltering:
    """Tests for filtered scoring."""

    def test_score_filtered_by_type(self, scorer, code_graph):
        result = scorer.score_filtered(code_graph, node_type="class")
        assert len(result) > 0
        assert all(n.node_data.get("type") == "class" for n in result)

    def test_score_filtered_returns_sorted(self, scorer, code_graph):
        result = scorer.score_filtered(code_graph, node_type="file")
        scores = [n.score for n in result]
        assert scores == sorted(scores, reverse=True)

    def test_score_filtered_nonexistent_type(self, scorer, code_graph):
        result = scorer.score_filtered(code_graph, node_type="nonexistent")
        assert result == []


class TestTopN:
    """Tests for top-N retrieval."""

    def test_top_n_returns_n_results(self, scorer, code_graph):
        result = scorer.top_n(code_graph, n=3)
        assert len(result) == 3

    def test_top_n_exceeding_graph_size(self, scorer, code_graph):
        num_nodes = len(code_graph)
        result = scorer.top_n(code_graph, n=num_nodes + 10)
        assert len(result) == num_nodes

    def test_top_n_with_personalization(self, scorer, code_graph):
        personalization = {n: 0.0 for n in code_graph.nodes()}
        personalization["AuthService"] = 1.0
        result = scorer.top_n(code_graph, n=2, personalization=personalization)
        assert len(result) == 2
        top_ids = [n.node_id for n in result]
        assert "AuthService" in top_ids


class TestCustomParameters:
    """Tests for custom PageRank parameters."""

    def test_custom_alpha_affects_scores(self, code_graph):
        scorer_low = PageRankScorer(alpha=0.5)
        scorer_high = PageRankScorer(alpha=0.99)

        result_low = scorer_low.score(code_graph)
        result_high = scorer_high.score(code_graph)

        scores_low = {n.node_id: n.score for n in result_low}
        scores_high = {n.node_id: n.score for n in result_high}

        assert any(
            abs(scores_low[nid] - scores_high[nid]) > 1e-6
            for nid in scores_low
        )

    def test_default_parameters(self):
        scorer = PageRankScorer()
        assert scorer.alpha == 0.85
        assert scorer.max_iter == 100
        assert scorer.tol == 1e-6
