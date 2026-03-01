import pytest
from code_brain.query.router import QueryRouter, QueryType


def test_classify_find():
    assert QueryRouter.classify("find") == QueryType.STRUCTURAL


def test_classify_hierarchy():
    assert QueryRouter.classify("hierarchy") == QueryType.STRUCTURAL


def test_classify_ask():
    assert QueryRouter.classify("ask") == QueryType.SEMANTIC


def test_classify_impact():
    assert QueryRouter.classify("impact") == QueryType.HYBRID


def test_classify_map():
    assert QueryRouter.classify("map") == QueryType.GRAPH


def test_classify_hotspots():
    assert QueryRouter.classify("hotspots") == QueryType.GRAPH


def test_classify_unknown():
    assert QueryRouter.classify("unknown_command") == QueryType.SEMANTIC
