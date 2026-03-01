"""Tests for code-brain data models (DataPoint subclasses)."""

import uuid
import pytest
from code_brain.models import CodeFunction, CodeClass, CodeModule


# ---------------------------------------------------------------------------
# CodeFunction
# ---------------------------------------------------------------------------

class TestCodeFunction:
    def test_basic_construction(self):
        fn = CodeFunction(
            id=uuid.uuid4(),
            name="authenticate",
            file_path="services/auth.py",
            line=42,
            signature="def authenticate(user: str, password: str) -> bool",
        )
        assert fn.name == "authenticate"
        assert fn.file_path == "services/auth.py"
        assert fn.line == 42

    def test_defaults(self):
        fn = CodeFunction(
            id=uuid.uuid4(),
            name="foo",
            file_path="a.py",
            line=1,
        )
        assert fn.parameters == []
        assert fn.return_type == ""
        assert fn.purpose == ""
        assert fn.kind == "function"

    def test_mutable_default_isolation(self):
        fn1 = CodeFunction(id=uuid.uuid4(), name="a", file_path="a.py", line=1)
        fn2 = CodeFunction(id=uuid.uuid4(), name="b", file_path="b.py", line=2)
        fn1.parameters.append("x")
        assert fn2.parameters == [], "Mutable default leaked across instances"

    def test_with_all_fields(self):
        fn = CodeFunction(
            id=uuid.uuid4(),
            name="process",
            file_path="core.py",
            line=10,
            signature="def process(data: list) -> dict",
            parameters=["data"],
            return_type="dict",
            purpose="Transforms raw data into structured output",
        )
        assert fn.parameters == ["data"]
        assert fn.return_type == "dict"
        assert fn.purpose.startswith("Transforms")


# ---------------------------------------------------------------------------
# CodeClass
# ---------------------------------------------------------------------------

class TestCodeClass:
    def test_basic_construction(self):
        cls = CodeClass(
            id=uuid.uuid4(),
            name="UserRepository",
            file_path="repos/user_repo.py",
            line=5,
        )
        assert cls.name == "UserRepository"
        assert cls.kind == "class"

    def test_defaults(self):
        cls = CodeClass(
            id=uuid.uuid4(),
            name="Foo",
            file_path="foo.py",
            line=1,
        )
        assert cls.parents == []
        assert cls.methods == []
        assert cls.role == ""

    def test_mutable_default_isolation(self):
        c1 = CodeClass(id=uuid.uuid4(), name="A", file_path="a.py", line=1)
        c2 = CodeClass(id=uuid.uuid4(), name="B", file_path="b.py", line=1)
        c1.parents.append("Base")
        c1.methods.append("run")
        assert c2.parents == [], "parents leaked"
        assert c2.methods == [], "methods leaked"

    def test_with_inheritance(self):
        cls = CodeClass(
            id=uuid.uuid4(),
            name="AuthService",
            file_path="services/auth.py",
            line=3,
            parents=["BaseService"],
            methods=["login", "logout"],
            role="authentication",
        )
        assert cls.parents == ["BaseService"]
        assert len(cls.methods) == 2
        assert cls.role == "authentication"


# ---------------------------------------------------------------------------
# CodeModule
# ---------------------------------------------------------------------------

class TestCodeModule:
    def test_basic_construction(self):
        mod = CodeModule(
            id=uuid.uuid4(),
            name="services.auth",
            file_path="services/auth.py",
        )
        assert mod.name == "services.auth"

    def test_defaults(self):
        mod = CodeModule(
            id=uuid.uuid4(),
            name="main",
            file_path="main.py",
        )
        assert mod.imports == []
        assert mod.exports == []
        assert mod.domain == ""

    def test_mutable_default_isolation(self):
        m1 = CodeModule(id=uuid.uuid4(), name="a", file_path="a.py")
        m2 = CodeModule(id=uuid.uuid4(), name="b", file_path="b.py")
        m1.imports.append("os")
        m1.exports.append("run")
        assert m2.imports == [], "imports leaked"
        assert m2.exports == [], "exports leaked"

    def test_with_all_fields(self):
        mod = CodeModule(
            id=uuid.uuid4(),
            name="api.routes",
            file_path="api/routes.py",
            imports=["flask", "services.auth"],
            exports=["router"],
            domain="web",
        )
        assert "flask" in mod.imports
        assert mod.domain == "web"


# ---------------------------------------------------------------------------
# DataPoint inheritance
# ---------------------------------------------------------------------------

def test_models_extend_datapoint():
    from cognee.infrastructure.engine import DataPoint
    assert issubclass(CodeFunction, DataPoint)
    assert issubclass(CodeClass, DataPoint)
    assert issubclass(CodeModule, DataPoint)
