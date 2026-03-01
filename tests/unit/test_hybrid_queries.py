import networkx as nx
import pytest
from unittest.mock import AsyncMock, MagicMock
from code_brain.query.hybrid import HybridQueryEngine
from code_brain.query.structural import StructuralQueryEngine
from code_brain.query.semantic import SemanticQueryEngine


@pytest.fixture
def sample_graph():
    g = nx.DiGraph()
    g.add_node(1, type="symbol", name="User", kind="class",
               file_path="models/user.py", line=1, signature="class User",
               change_frequency=3)
    g.add_node(2, type="symbol", name="AuthService", kind="class",
               file_path="services/auth.py", line=1, signature="class AuthService",
               change_frequency=1)
    g.add_edge(2, 1, type="uses")
    return g


@pytest.fixture
def hybrid_engine(sample_graph):
    structural = MagicMock(spec=StructuralQueryEngine)
    structural.find.return_value = [
        {"id": 1, "name": "User", "kind": "class",
         "file_path": "models/user.py", "line": 1, "signature": "class User"}
    ]
    structural.usages.return_value = [
        {"file_path": "services/auth.py", "line": 5, "context": "user: User"}
    ]
    semantic = MagicMock(spec=SemanticQueryEngine)
    semantic.ask = AsyncMock(return_value=[{"text": "Core user model"}])
    return HybridQueryEngine(structural, semantic, sample_graph)


@pytest.mark.asyncio
async def test_impact_analysis(hybrid_engine):
    result = await hybrid_engine.impact("User")
    assert result["symbol"] == "User"
    assert "dependents" in result
    assert "risk_level" in result


@pytest.mark.asyncio
async def test_dead_code(hybrid_engine):
    hybrid_engine._structural.usages.side_effect = lambda s, **kw: (
        [] if s == "AuthService" else [{"file_path": "x.py", "line": 1, "context": ""}]
    )
    result = await hybrid_engine.dead_code()
    assert isinstance(result, list)
