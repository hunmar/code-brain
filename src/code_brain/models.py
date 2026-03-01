"""Code-specific data models extending cognee DataPoint for structured ingestion."""

from __future__ import annotations

from pydantic import Field
from cognee.infrastructure.engine import DataPoint


class CodeFunction(DataPoint):
    """A function or method extracted from source code."""

    name: str
    file_path: str
    line: int
    signature: str = ""
    kind: str = "function"
    parameters: list[str] = Field(default_factory=list)
    return_type: str = ""
    purpose: str = ""

    _metadata: dict = {"index_fields": ["name", "signature", "purpose"]}


class CodeClass(DataPoint):
    """A class extracted from source code."""

    name: str
    file_path: str
    line: int
    kind: str = "class"
    parents: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    role: str = ""

    _metadata: dict = {"index_fields": ["name", "role"]}


class CodeModule(DataPoint):
    """A module representing a file or package in the codebase."""

    name: str
    file_path: str
    imports: list[str] = Field(default_factory=list)
    exports: list[str] = Field(default_factory=list)
    domain: str = ""

    _metadata: dict = {"index_fields": ["name", "domain"]}
