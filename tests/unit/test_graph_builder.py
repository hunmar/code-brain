import pytest
import networkx as nx
from code_brain.graph.builder import GraphBuilder
from code_brain.ingestion.ast_index import Symbol, ModuleDep, Usage
from code_brain.ingestion.git_analyzer import HotSpot, CoChange


@pytest.fixture
def sample_symbols():
    return [
        Symbol(1, "User", "class", "src/models/user.py", 1, "class User"),
        Symbol(2, "AdminUser", "class", "src/models/user.py", 10, "class AdminUser(User)"),
        Symbol(3, "AuthService", "class", "src/services/auth.py", 3, "class AuthService"),
        Symbol(4, "authenticate", "function", "src/services/auth.py", 7,
               "def authenticate(self, email, password)", parent_id=3),
    ]


@pytest.fixture
def sample_inheritance():
    return {"AdminUser": ["User"]}


@pytest.fixture
def sample_module_deps():
    return [ModuleDep("services", "models", "import")]


@pytest.fixture
def sample_usages():
    return {
        "User": [
            Usage("src/services/auth.py", 3, "from models import User"),
        ]
    }


@pytest.fixture
def sample_git_data():
    return {
        "hot_spots": [HotSpot("src/models/user.py", 5)],
        "co_changes": [CoChange("src/models/user.py", "src/services/auth.py", 3)],
    }


def test_build_graph_has_nodes(sample_symbols, sample_inheritance,
                                sample_module_deps, sample_usages,
                                sample_git_data):
    builder = GraphBuilder()
    g = builder.build(
        symbols=sample_symbols,
        inheritance=sample_inheritance,
        module_deps=sample_module_deps,
        usages=sample_usages,
        hot_spots=sample_git_data["hot_spots"],
        co_changes=sample_git_data["co_changes"],
    )
    assert isinstance(g, nx.DiGraph)
    assert len(g.nodes) >= 4  # at least 4 symbols


def test_graph_has_inheritance_edges(sample_symbols, sample_inheritance,
                                     sample_module_deps, sample_usages,
                                     sample_git_data):
    builder = GraphBuilder()
    g = builder.build(
        symbols=sample_symbols,
        inheritance=sample_inheritance,
        module_deps=sample_module_deps,
        usages=sample_usages,
        hot_spots=sample_git_data["hot_spots"],
        co_changes=sample_git_data["co_changes"],
    )
    inherits_edges = [
        (u, v) for u, v, d in g.edges(data=True) if d.get("type") == "inherits"
    ]
    assert len(inherits_edges) >= 1


def test_graph_has_usage_edges(sample_symbols, sample_inheritance,
                                sample_module_deps, sample_usages,
                                sample_git_data):
    builder = GraphBuilder()
    g = builder.build(
        symbols=sample_symbols,
        inheritance=sample_inheritance,
        module_deps=sample_module_deps,
        usages=sample_usages,
        hot_spots=sample_git_data["hot_spots"],
        co_changes=sample_git_data["co_changes"],
    )
    usage_edges = [
        (u, v) for u, v, d in g.edges(data=True) if d.get("type") == "uses"
    ]
    assert len(usage_edges) >= 1


def test_graph_has_hot_spot_attribute(sample_symbols, sample_inheritance,
                                      sample_module_deps, sample_usages,
                                      sample_git_data):
    builder = GraphBuilder()
    g = builder.build(
        symbols=sample_symbols,
        inheritance=sample_inheritance,
        module_deps=sample_module_deps,
        usages=sample_usages,
        hot_spots=sample_git_data["hot_spots"],
        co_changes=sample_git_data["co_changes"],
    )
    freqs = [
        d.get("change_frequency", 0)
        for _, d in g.nodes(data=True)
    ]
    assert max(freqs) > 0


def test_graph_serialization(tmp_path, sample_symbols, sample_inheritance,
                              sample_module_deps, sample_usages,
                              sample_git_data):
    builder = GraphBuilder()
    g = builder.build(
        symbols=sample_symbols,
        inheritance=sample_inheritance,
        module_deps=sample_module_deps,
        usages=sample_usages,
        hot_spots=sample_git_data["hot_spots"],
        co_changes=sample_git_data["co_changes"],
    )
    path = tmp_path / "graph.pkl"
    builder.save(g, path)
    loaded = builder.load(path)
    assert len(loaded.nodes) == len(g.nodes)
    assert len(loaded.edges) == len(g.edges)
