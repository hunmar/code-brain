import pytest
from code_brain.mcp_server import TOOL_NAMES


def test_server_has_expected_tools():
    assert "code_find_symbol" in TOOL_NAMES
    assert "code_map" in TOOL_NAMES
    assert "code_impact" in TOOL_NAMES
    assert len(TOOL_NAMES) == 12
