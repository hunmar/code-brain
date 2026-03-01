import networkx as nx
import pytest
from code_brain.graph.queries import GraphQueryEngine


@pytest.fixture
def sample_graph():
    g = nx.DiGraph()
    g.add_node(1, type="symbol", name="User", kind="class",
               file_path="models/user.py", line=1, signature="class User",
               change_frequency=5)
    g.add_node(2, type="symbol", name="AuthService", kind="class",
               file_path="services/auth.py", line=1, signature="class AuthService",
               change_frequency=2)
    g.add_node(3, type="symbol", name="UserRepo", kind="class",
               file_path="repos/repo.py", line=1, signature="class UserRepo",
               change_frequency=0)
    g.add_node("mod:models", type="module")
    g.add_node("mod:services", type="module")
    g.add_edge(2, 1, type="uses")
    g.add_edge(3, 1, type="uses")
    g.add_edge(2, 3, type="uses")
    g.add_edge("mod:services", "mod:models", type="module_dep")
    return g


def test_repo_map(sample_graph):
    engine = GraphQueryEngine(sample_graph)
    result = engine.repo_map(token_budget=2000)
    assert "User" in result
    assert "AuthService" in result


def test_repo_map_with_focus(sample_graph):
    engine = GraphQueryEngine(sample_graph)
    result = engine.repo_map(focus_files=["services/auth.py"], token_budget=2000)
    assert len(result) > 0


def test_hotspots(sample_graph):
    engine = GraphQueryEngine(sample_graph)
    result = engine.hotspots(limit=10)
    assert len(result) >= 1
    assert result[0]["name"] == "User"
    assert result[0]["change_frequency"] == 5


def test_architecture_mermaid(sample_graph):
    engine = GraphQueryEngine(sample_graph)
    result = engine.architecture(fmt="mermaid")
    assert "graph" in result.lower() or "flowchart" in result.lower()
    assert "models" in result
    assert "services" in result


def test_architecture_text(sample_graph):
    engine = GraphQueryEngine(sample_graph)
    result = engine.architecture(fmt="text")
    assert "models" in result
    assert "services" in result
