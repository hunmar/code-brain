from enum import Enum


class QueryType(Enum):
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    GRAPH = "graph"


_COMMAND_MAP = {
    "find": QueryType.STRUCTURAL,
    "hierarchy": QueryType.STRUCTURAL,
    "deps": QueryType.STRUCTURAL,
    "usages": QueryType.STRUCTURAL,
    "outline": QueryType.STRUCTURAL,
    "imports": QueryType.STRUCTURAL,
    "ask": QueryType.SEMANTIC,
    "explain": QueryType.SEMANTIC,
    "impact": QueryType.HYBRID,
    "review": QueryType.HYBRID,
    "dead-code": QueryType.HYBRID,
    "map": QueryType.GRAPH,
    "hotspots": QueryType.GRAPH,
    "arch": QueryType.GRAPH,
}


class QueryRouter:
    @staticmethod
    def classify(command: str) -> QueryType:
        return _COMMAND_MAP.get(command, QueryType.SEMANTIC)
