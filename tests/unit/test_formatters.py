import json
import pytest
from code_brain.formatters.json_formatter import JsonFormatter
from code_brain.formatters.text_formatter import TextFormatter

SAMPLE_FIND_RESULT = [
    {"name": "User", "kind": "class", "file_path": "models/user.py",
     "line": 1, "signature": "class User"},
]

SAMPLE_HIERARCHY = {"class": "AdminUser", "parents": ["User"]}


def test_json_format_list():
    fmt = JsonFormatter()
    result = fmt.format(SAMPLE_FIND_RESULT)
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    assert parsed[0]["name"] == "User"


def test_json_format_dict():
    fmt = JsonFormatter()
    result = fmt.format(SAMPLE_HIERARCHY)
    parsed = json.loads(result)
    assert parsed["class"] == "AdminUser"


def test_text_format_find_results():
    fmt = TextFormatter()
    result = fmt.format_symbols(SAMPLE_FIND_RESULT)
    assert "User" in result
    assert "models/user.py" in result


def test_text_format_hierarchy():
    fmt = TextFormatter()
    result = fmt.format_hierarchy(SAMPLE_HIERARCHY)
    assert "AdminUser" in result
    assert "User" in result
