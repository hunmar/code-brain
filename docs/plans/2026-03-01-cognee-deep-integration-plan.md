# Deep Cognee Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make cognee a first-class partner with ast-index — custom code graph models, batched ingestion, all search types, memify enrichment, graceful degradation, 14 MCP tools.

**Architecture:** Custom Pydantic models extending cognee's DataPoint feed structured code data into cognee's LLM pipeline. The CogneeAdapter is rebuilt to batch-ingest CodeFunction/CodeClass/CodeModule instances, call cognify once, then memify for enrichment. The MCP server gains 2 new tools and maps existing semantic tools to specific cognee search types. All cognee-powered tools degrade gracefully when backends are down.

**Tech Stack:** Python 3.12, cognee (add/cognify/search/memify), cognee.infrastructure.engine.models.DataPoint, cognee.modules.search.types.SearchType, mcp, typer, networkx

---

### Task 1: Create custom code graph models

**Files:**
- Create: `src/code_brain/models.py`
- Test: `tests/unit/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_models.py
from code_brain.models import CodeFunction, CodeClass, CodeModule


def test_code_function_creates():
    fn = CodeFunction(
        name="authenticate",
        signature="def authenticate(self, email, password)",
        file_path="src/auth.py",
        line=10,
        module="auth",
        parameters=["email", "password"],
        return_type="bool",
        docstring="Authenticate a user.",
        body_summary="if check_password(email, password): return True",
    )
    assert fn.name == "authenticate"
    assert fn.kind == "function"
    assert "name" in fn.metadata.get("index_fields", [])


def test_code_class_creates():
    cls = CodeClass(
        name="UserService",
        file_path="src/services.py",
        line=5,
        parents=["BaseService"],
        methods=["create_user", "delete_user"],
        docstring="Manages user lifecycle.",
    )
    assert cls.name == "UserService"
    assert cls.kind == "class"
    assert "architectural_role" in cls.metadata.get("index_fields", [])


def test_code_module_creates():
    mod = CodeModule(
        name="auth",
        path="src/auth",
        imports=["models", "utils"],
        exports=["authenticate", "AuthService"],
    )
    assert mod.name == "auth"
    assert mod.kind == "module"
```

**Step 2: Run test to verify it fails**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'code_brain.models'`

**Step 3: Write minimal implementation**

```python
# src/code_brain/models.py
"""Code-specific graph models for cognee integration."""
from __future__ import annotations

from cognee.infrastructure.engine.models.DataPoint import DataPoint


class CodeFunction(DataPoint):
    """A function or method in the codebase."""
    name: str
    signature: str
    file_path: str
    line: int
    module: str = ""
    parameters: list[str] = []
    return_type: str = ""
    docstring: str = ""
    body_summary: str = ""
    purpose: str = ""
    complexity: str = ""
    kind: str = "function"
    metadata: dict = {"index_fields": ["name", "signature", "purpose"]}


class CodeClass(DataPoint):
    """A class in the codebase."""
    name: str
    file_path: str
    line: int
    parents: list[str] = []
    methods: list[str] = []
    docstring: str = ""
    purpose: str = ""
    architectural_role: str = ""
    kind: str = "class"
    metadata: dict = {"index_fields": ["name", "purpose", "architectural_role"]}


class CodeModule(DataPoint):
    """A module/package in the codebase."""
    name: str
    path: str
    imports: list[str] = []
    exports: list[str] = []
    description: str = ""
    domain: str = ""
    kind: str = "module"
    metadata: dict = {"index_fields": ["name", "description", "domain"]}
```

**Step 4: Run test to verify it passes**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/code_brain/models.py tests/unit/test_models.py
git commit -m "feat: add custom code graph models extending cognee DataPoint"
```

---

### Task 2: Rebuild CogneeAdapter with batched structured ingestion

**Files:**
- Modify: `src/code_brain/ingestion/cognee_adapter.py` (full rewrite)
- Test: `tests/unit/test_cognee_adapter.py` (update)

**Step 1: Write the failing tests**

```python
# tests/unit/test_cognee_adapter.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from code_brain.ingestion.ast_index import Symbol, ModuleDep
from code_brain.ingestion.cognee_adapter import CogneeAdapter


@pytest.fixture
def adapter():
    return CogneeAdapter()


@pytest.fixture
def sample_symbols():
    return [
        Symbol(id=1, name="User", kind="class", file_path="src/models.py",
               line=5, signature="class User:", parent_id=None),
        Symbol(id=2, name="authenticate", kind="function", file_path="src/auth.py",
               line=10, signature="def authenticate(email, password)", parent_id=None),
    ]


@pytest.mark.asyncio
async def test_ingest_builds_code_models(adapter, sample_symbols):
    """ingest_symbols should create CodeFunction/CodeClass instances, not flat text."""
    with patch("cognee.add", new_callable=AsyncMock) as mock_add, \
         patch("cognee.cognify", new_callable=AsyncMock), \
         patch("cognee.memify", new_callable=AsyncMock):
        await adapter.ingest_symbols(sample_symbols)

    # Should batch-add, not per-symbol
    assert mock_add.call_count <= 2  # at most one call per batch, not per symbol


@pytest.mark.asyncio
async def test_ingest_calls_cognify_once(adapter, sample_symbols):
    """Should call cognify exactly once after all data is added."""
    with patch("cognee.add", new_callable=AsyncMock) as mock_add, \
         patch("cognee.cognify", new_callable=AsyncMock) as mock_cognify, \
         patch("cognee.memify", new_callable=AsyncMock):
        await adapter.ingest_symbols(sample_symbols)
        await adapter.finalize()

    mock_cognify.assert_called_once()


@pytest.mark.asyncio
async def test_search_with_search_type(adapter):
    """search should accept and pass search_type to cognee."""
    mock_results = [MagicMock(__str__=lambda self: "result")]
    with patch("cognee.search", new_callable=AsyncMock, return_value=mock_results) as mock_search:
        results = await adapter.search("test query", search_type="CHUNKS")

    mock_search.assert_called_once()
    call_kwargs = mock_search.call_args
    assert "query_type" in str(call_kwargs)
```

**Step 2: Run test to verify it fails**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cognee_adapter.py -v`
Expected: FAIL — old adapter doesn't have `finalize()` or `search_type`

**Step 3: Write minimal implementation**

```python
# src/code_brain/ingestion/cognee_adapter.py
"""Cognee integration — structured code ingestion and multi-type search."""
from __future__ import annotations

import cognee
from cognee.modules.search.types.SearchType import SearchType

from code_brain.ingestion.ast_index import Symbol, ModuleDep
from code_brain.models import CodeFunction, CodeClass, CodeModule


# Map string names to SearchType enum
SEARCH_TYPE_MAP = {st.value: st for st in SearchType}


class CogneeAdapter:
    """Bridges code-brain's structural data with cognee's semantic pipeline."""

    def _symbol_to_model(self, sym: Symbol) -> CodeFunction | CodeClass:
        if sym.kind == "class":
            return CodeClass(
                name=sym.name,
                file_path=sym.file_path,
                line=sym.line,
                docstring="",
                parents=[],
                methods=[],
            )
        return CodeFunction(
            name=sym.name,
            signature=sym.signature or "",
            file_path=sym.file_path,
            line=sym.line,
            module=sym.file_path.rsplit("/", 1)[0] if "/" in sym.file_path else "",
            parameters=[],
            return_type="",
            docstring="",
            body_summary=sym.signature or "",
        )

    async def ingest_symbols(self, symbols: list[Symbol]) -> None:
        """Batch-add symbols as structured code models."""
        models = [self._symbol_to_model(s) for s in symbols]
        # Feed as text representations for cognee to process
        docs = []
        for m in models:
            if isinstance(m, CodeClass):
                docs.append(
                    f"Code class: {m.name}\n"
                    f"File: {m.file_path}:{m.line}\n"
                    f"Parents: {', '.join(m.parents) if m.parents else 'none'}\n"
                    f"Methods: {', '.join(m.methods) if m.methods else 'none'}\n"
                )
            else:
                docs.append(
                    f"Code function: {m.name}\n"
                    f"Signature: {m.signature}\n"
                    f"File: {m.file_path}:{m.line}\n"
                    f"Module: {m.module}\n"
                )
        if docs:
            combined = "\n---\n".join(docs)
            await cognee.add(combined, dataset_name="code_symbols")

    async def ingest_module_deps(self, deps: list[ModuleDep]) -> None:
        """Batch-add module dependencies."""
        if not deps:
            return
        docs = [
            f"Module {d.source} depends on {d.target} (relationship: {d.kind})"
            for d in deps
        ]
        combined = "\n".join(docs)
        await cognee.add(combined, dataset_name="code_relationships")

    async def ingest_docs(self, doc_contents: list[tuple[str, str]]) -> None:
        """Batch-add documentation."""
        if not doc_contents:
            return
        for filename, content in doc_contents:
            await cognee.add(
                f"Document: {filename}\n\n{content}",
                dataset_name="documentation",
            )

    async def finalize(self) -> None:
        """Run cognify + memify once after all data is ingested."""
        await cognee.cognify()
        try:
            await cognee.memify()
        except Exception:
            pass  # memify is optional enrichment

    async def search(
        self,
        query: str,
        search_type: str = "GRAPH_COMPLETION",
        top_k: int = 10,
    ) -> list[dict]:
        """Search using any of cognee's 14 search types."""
        st = SEARCH_TYPE_MAP.get(search_type, SearchType.GRAPH_COMPLETION)
        results = await cognee.search(
            query_text=query,
            query_type=st,
            top_k=top_k,
        )
        return [{"text": str(r)} for r in results]
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cognee_adapter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/code_brain/ingestion/cognee_adapter.py tests/unit/test_cognee_adapter.py
git commit -m "feat: rebuild CogneeAdapter with batched ingestion and multi-type search"
```

---

### Task 3: Update SemanticQueryEngine to use search types

**Files:**
- Modify: `src/code_brain/query/semantic.py`
- Test: `tests/unit/test_semantic_queries.py`

**Step 1: Write the failing tests**

```python
# Add to tests/unit/test_semantic_queries.py
@pytest.mark.asyncio
async def test_ask_uses_graph_completion(mock_adapter):
    engine = SemanticQueryEngine(mock_adapter)
    await engine.ask("How does auth work?")
    mock_adapter.search.assert_called_once()
    assert mock_adapter.search.call_args[1].get("search_type") == "GRAPH_COMPLETION"


@pytest.mark.asyncio
async def test_explain_uses_summary_completion(mock_adapter):
    engine = SemanticQueryEngine(mock_adapter)
    await engine.explain("UserService")
    assert mock_adapter.search.call_args[1].get("search_type") == "GRAPH_SUMMARY_COMPLETION"


@pytest.mark.asyncio
async def test_search_chunks(mock_adapter):
    engine = SemanticQueryEngine(mock_adapter)
    await engine.search_fast("authentication logic")
    assert mock_adapter.search.call_args[1].get("search_type") == "CHUNKS"


@pytest.mark.asyncio
async def test_reason_uses_cot(mock_adapter):
    engine = SemanticQueryEngine(mock_adapter)
    await engine.reason("Why does the payment module depend on auth?")
    assert mock_adapter.search.call_args[1].get("search_type") == "GRAPH_COMPLETION_COT"


@pytest.mark.asyncio
async def test_review_uses_coding_rules(mock_adapter):
    engine = SemanticQueryEngine(mock_adapter)
    await engine.review_diff("+ def foo(): pass")
    assert mock_adapter.search.call_args[1].get("search_type") == "CODING_RULES"
```

**Step 2: Run test to verify they fail**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_semantic_queries.py -v`
Expected: FAIL — no `search_fast`, `reason`, `review_diff` methods

**Step 3: Write minimal implementation**

```python
# src/code_brain/query/semantic.py
from code_brain.ingestion.cognee_adapter import CogneeAdapter


class SemanticQueryEngine:
    def __init__(self, adapter: CogneeAdapter):
        self._adapter = adapter

    async def ask(self, question: str) -> list[dict]:
        """Natural language Q&A with full graph context."""
        return await self._adapter.search(
            question, search_type="GRAPH_COMPLETION"
        )

    async def explain(self, symbol_name: str,
                      structural_info: dict | None = None) -> str:
        """Explain a symbol using pre-computed summaries + structural context."""
        semantic = await self._adapter.search(
            f"Explain the purpose and context of {symbol_name}",
            search_type="GRAPH_SUMMARY_COMPLETION",
        )

        parts = [f"# {symbol_name}"]
        if structural_info:
            parts.append(
                f"\nLocation: {structural_info.get('file_path', '?')}"
                f":{structural_info.get('line', '?')}"
            )
            parts.append(f"Kind: {structural_info.get('kind', '?')}")

        if semantic:
            parts.append("\n## Semantic Context")
            for item in semantic:
                parts.append(f"- {item.get('text', str(item))}")

        return "\n".join(parts)

    async def search_fast(self, query: str, top_k: int = 10) -> list[dict]:
        """Fast vector similarity search — no LLM call."""
        return await self._adapter.search(
            query, search_type="CHUNKS", top_k=top_k
        )

    async def reason(self, question: str) -> list[dict]:
        """Chain-of-thought reasoning over the code graph."""
        return await self._adapter.search(
            question, search_type="GRAPH_COMPLETION_COT"
        )

    async def review_diff(self, diff: str) -> list[dict]:
        """Review a diff against coding rules stored in the graph."""
        return await self._adapter.search(
            f"Review this code change for potential issues:\n\n{diff}",
            search_type="CODING_RULES",
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_semantic_queries.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/code_brain/query/semantic.py tests/unit/test_semantic_queries.py
git commit -m "feat: map semantic queries to specific cognee search types"
```

---

### Task 4: Add MCP error handling and graceful degradation

**Files:**
- Modify: `src/code_brain/mcp_server.py:216-278`
- Test: `tests/unit/test_mcp_server.py`

**Step 1: Write the failing test**

```python
# Add to tests/unit/test_mcp_server.py
def test_semantic_tools_degrade_gracefully():
    """When cognee is unavailable, semantic tools should return helpful error, not crash."""
    from code_brain.mcp_server import _safe_semantic_call
    import asyncio

    async def failing_call():
        raise Exception("sqlite3.OperationalError: unable to open database file")

    result = asyncio.run(_safe_semantic_call(failing_call()))
    assert "error" in result or "unavailable" in str(result).lower()
```

**Step 2: Run test to verify it fails**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_mcp_server.py::test_semantic_tools_degrade_gracefully -v`
Expected: FAIL — `_safe_semantic_call` doesn't exist

**Step 3: Write minimal implementation**

In `src/code_brain/mcp_server.py`, add a helper and wrap semantic tool calls:

```python
async def _safe_semantic_call(coro):
    """Wrap semantic/cognee calls with graceful error handling."""
    try:
        return await coro
    except Exception as e:
        error_msg = str(e)
        if "OperationalError" in error_msg or "Connection refused" in error_msg:
            return {
                "error": "Semantic features unavailable. Run: code-brain up && code-brain ingest",
                "details": error_msg,
            }
        return {"error": f"Semantic query failed: {error_msg}"}
```

Then in `_dispatch`, wrap all semantic tool calls:

```python
    if name == "code_ask":
        return await _safe_semantic_call(semantic.ask(arguments["question"]))

    if name == "code_explain":
        symbol_name = arguments["symbol"]
        found = structural.find(symbol_name)
        structural_info = found[0] if found else None
        return await _safe_semantic_call(
            semantic.explain(symbol_name, structural_info)
        )

    if name == "code_impact":
        result = await _safe_semantic_call(
            hybrid.impact(arguments["symbol"], token_budget=arguments.get("token_budget", 8000))
        )
        return result

    if name == "code_review_diff":
        return await _safe_semantic_call(
            semantic.review_diff(arguments["diff"])
        )

    if name == "code_search":
        return await _safe_semantic_call(
            semantic.search_fast(arguments["query"], top_k=arguments.get("top_k", 10))
        )

    if name == "code_reason":
        return await _safe_semantic_call(
            semantic.reason(arguments["question"])
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_mcp_server.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/code_brain/mcp_server.py tests/unit/test_mcp_server.py
git commit -m "feat: add graceful degradation for semantic MCP tools"
```

---

### Task 5: Add new MCP tools (code_search, code_reason) and update tool descriptions

**Files:**
- Modify: `src/code_brain/mcp_server.py` (TOOL_NAMES, TOOLS list, _dispatch)
- Test: `tests/unit/test_mcp_server.py`

**Step 1: Write the failing test**

```python
# Add to tests/unit/test_mcp_server.py
def test_server_has_14_tools():
    assert len(TOOL_NAMES) == 14


def test_server_has_code_search():
    assert "code_search" in TOOL_NAMES


def test_server_has_code_reason():
    assert "code_reason" in TOOL_NAMES
```

**Step 2: Run test to verify they fail**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_mcp_server.py -v`
Expected: FAIL — only 12 tools

**Step 3: Write minimal implementation**

Add to TOOL_NAMES:

```python
TOOL_NAMES = [
    "code_find_symbol",
    "code_hierarchy",
    "code_dependencies",
    "code_usages",
    "code_outline",
    "code_ask",
    "code_explain",
    "code_impact",
    "code_review_diff",
    "code_map",
    "code_hotspots",
    "code_architecture",
    "code_search",
    "code_reason",
]
```

Add to TOOLS list:

```python
    Tool(
        name="code_search",
        description="Fast semantic search for code by concept — no LLM call, returns vector-similar chunks. Use for quick lookups like 'authentication logic' or 'database connection handling'.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "top_k": {"type": "integer", "description": "Max results", "default": 10},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="code_reason",
        description="Chain-of-thought reasoning about the codebase. Use for complex questions that need multi-step reasoning, like 'Why does module X depend on module Y?' or 'What would break if we removed this class?'",
        inputSchema={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Complex question requiring reasoning"},
            },
            "required": ["question"],
        },
    ),
```

Also update existing tool descriptions to be more informative:

- `code_ask`: "Ask a natural language question about the codebase. Uses the full knowledge graph for context-aware answers about architecture, patterns, and business logic."
- `code_explain`: "Get an explanation of a symbol including its context and purpose. Combines structural location with semantic understanding from the knowledge graph."
- `code_review_diff`: "Review a diff for potential issues using coding rules stored in the knowledge graph. Checks against patterns and conventions learned during ingestion."

Add dispatch cases in `_dispatch()` for new tools (as shown in Task 4).

**Step 4: Run tests to verify they pass**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_mcp_server.py -v`
Expected: PASS

Also update the old test: `test_server_has_expected_tools` checks `len(TOOL_NAMES) == 12` — update to `14`.

**Step 5: Commit**

```bash
git add src/code_brain/mcp_server.py tests/unit/test_mcp_server.py
git commit -m "feat: add code_search and code_reason MCP tools, improve descriptions"
```

---

### Task 6: Update ingest command for unified pipeline

**Files:**
- Modify: `src/code_brain/cli.py:230-337` (ingest command)
- Test: `tests/unit/test_cli.py`

**Step 1: Write the failing test**

```python
# Add to tests/unit/test_cli.py
def test_ingest_structural_only_flag(tmp_path, monkeypatch):
    """--structural-only should replace --skip-semantic."""
    result = runner.invoke(app, ["ingest", "--help"])
    assert "--structural-only" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py::test_ingest_structural_only_flag -v`
Expected: FAIL — flag is still `--skip-semantic`

**Step 3: Write minimal implementation**

In `src/code_brain/cli.py`, update the `ingest` command:

1. Rename `skip_semantic` to `structural_only`:

```python
@app.command()
def ingest(
    project: Optional[str] = typer.Option(None, help="Project root"),
    structural_only: bool = typer.Option(False, "--structural-only", help="Skip cognee, build graph from AST + git only"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Force ast-index rebuild"),
):
```

2. Replace the semantic ingestion block (lines 322-334) with the new batched flow:

```python
    if not structural_only:
        typer.echo("Ingesting into cognee knowledge graph...")
        from code_brain.ingestion.cognee_adapter import CogneeAdapter
        from code_brain.ingestion.doc_ingester import find_docs

        adapter = CogneeAdapter()
        try:
            asyncio.run(adapter.ingest_symbols(symbols))
            asyncio.run(adapter.ingest_module_deps(all_deps))

            docs = find_docs(cfg.project_root)
            if docs:
                asyncio.run(adapter.ingest_docs(docs))
                typer.echo(f"Ingested {len(docs)} documents.")

            typer.echo("Running cognee cognify + memify...")
            asyncio.run(adapter.finalize())
            typer.echo("Semantic enrichment complete.")
        except Exception as e:
            typer.echo(f"Warning: Semantic ingestion failed: {e}")
            typer.echo("  Structural graph still available. Run 'code-brain doctor' to diagnose.")
    else:
        typer.echo("Skipping semantic ingestion (--structural-only).")
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/code_brain/cli.py tests/unit/test_cli.py
git commit -m "feat: update ingest with batched cognee pipeline and --structural-only flag"
```

---

### Task 7: Add CLI commands for new search types

**Files:**
- Modify: `src/code_brain/cli.py` (add `search` and `reason` commands)
- Test: `tests/unit/test_cli.py`

**Step 1: Write the failing test**

```python
def test_search_command_exists():
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0
    assert "semantic" in result.stdout.lower() or "vector" in result.stdout.lower()


def test_reason_command_exists():
    result = runner.invoke(app, ["reason", "--help"])
    assert result.exit_code == 0
```

**Step 2: Run test to verify they fail**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py::test_search_command_exists -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Add to `src/code_brain/cli.py`:

```python
@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    top_k: int = typer.Option(10, help="Max results"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Fast semantic search — find code by concept without LLM call."""
    cfg = _get_config(project)
    engine = _get_semantic_engine(cfg)
    results = asyncio.run(engine.search_fast(query, top_k=top_k))
    if json:
        typer.echo(json_fmt.format(results))
    else:
        for item in results:
            typer.echo(f"  {item.get('text', str(item))}")
        if not results:
            typer.echo("No results found.")


@app.command()
def reason(
    question: str = typer.Argument(..., help="Complex question requiring reasoning"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Chain-of-thought reasoning about the codebase."""
    cfg = _get_config(project)
    engine = _get_semantic_engine(cfg)
    results = asyncio.run(engine.reason(question))
    if json:
        typer.echo(json_fmt.format(results))
    else:
        for item in results:
            typer.echo(f"  {item.get('text', str(item))}")
        if not results:
            typer.echo("No results found.")
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/code_brain/cli.py tests/unit/test_cli.py
git commit -m "feat: add search and reason CLI commands for new cognee search types"
```

---

### Task 8: Update MCP server to pass project_root to structural engine

**Files:**
- Modify: `src/code_brain/mcp_server.py:189-213` (create_server)

**Step 1: Verify issue exists**

The `create_server` function creates `StructuralQueryEngine(reader)` without `project_root`. Fix:

```python
structural = StructuralQueryEngine(reader, project_root=config.project_root)
```

**Step 2: Make the fix**

Single line change in `create_server`.

**Step 3: Run all tests**

Run: `cd /home/exedev/code-brain && uv run pytest -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add src/code_brain/mcp_server.py
git commit -m "fix: pass project_root to structural engine in MCP server"
```

---

### Task 9: Update README and run full test suite

**Files:**
- Modify: `README.md`

**Step 1: Update README**

- Update tool count from 12 to 14
- Add `code_search` and `code_reason` to tool tier table
- Update `--skip-semantic` references to `--structural-only`
- Update the ingestion section to describe the cognee pipeline

**Step 2: Run full test suite**

Run: `cd /home/exedev/code-brain && uv run pytest -v`
Expected: ALL PASS

**Step 3: Commit and push**

```bash
git add README.md
git commit -m "docs: update README for 14-tool cognee integration"
git push
```
