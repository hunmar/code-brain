# Code-Brain Future Roadmap

**Date:** 2026-03-01
**Context:** Real-world testing against the cognee repo (19,685 symbols, ast-index only)

---

## Current State

**Working today (structural tier -- ast-index only, no Docker):**
- `code_find_symbol`, `code_hierarchy`, `code_usages`, `code_outline`, `code_dependencies`
- These 5 MCP tools work with just `ast-index rebuild`. Zero backend dependencies.

**Not working without `code-brain ingest` (needs graph):**
- `code_map`, `code_architecture`, `code_hotspots`, `code_impact`, `code_review_diff`
- These 5 tools require the NetworkX graph, which `ingest` builds.
- `ingest` currently also tries semantic ingestion (Neo4j + Qdrant), so it fails without Docker.

**Not working without Docker (needs semantic backends):**
- `code_ask`, `code_explain`
- These require cognee with Neo4j + Qdrant running.

---

## Phase 1: Graph-Only Mode + MCP Error Handling

*Biggest bang for buck. Unlocks 5 more tools with zero Docker dependency.*

### 1.1 Make `--skip-semantic` the reliable path

The `--skip-semantic` flag exists on `ingest` but the graph-building portion is the
only thing needed for `code_map`, `code_architecture`, `code_hotspots`, `code_impact`,
and `code_review_diff`. Today it works in code (lines 322-336 of `cli.py` are guarded
by `if not skip_semantic`), but:

- **Document it prominently.** The README and `--help` should make clear that
  `code-brain ingest --skip-semantic` is a fully supported mode, not a workaround.
- **Test the path end-to-end.** Add an integration test that runs
  `ingest --skip-semantic` on a small fixture repo and verifies the graph pickle
  is created with the expected node/edge counts.
- **Consider making `--skip-semantic` the default.** Semantic ingestion could become
  opt-in (`--with-semantic`) since most users will not have Docker running.

### 1.2 MCP error handling: graceful degradation

When graph or semantic backends are missing, MCP tools crash with raw Python
tracebacks (e.g., `sqlite3.OperationalError`, `FileNotFoundError` on the pickle).
Each tool should catch errors and return a helpful JSON response instead.

**Implementation:**

Wrap `_dispatch` in `mcp_server.py` with per-tool error handling:

```python
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = await _dispatch(name, arguments, ...)
    except FileNotFoundError:
        result = {
            "error": "Code graph not found. Run: code-brain ingest --skip-semantic"
        }
    except Exception as e:
        result = {
            "error": f"Tool '{name}' failed: {e}. Run: code-brain doctor"
        }
    text = json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
    return [TextContent(type="text", text=text)]
```

Specific cases to handle:
- **AST index missing:** structural tools should say "Run: code-brain ingest"
- **Graph pickle missing:** graph tools should say "Run: code-brain ingest --skip-semantic"
- **Semantic backends unreachable:** `code_ask`/`code_explain` should say "Run: code-brain up"
- **Never return raw tracebacks** to the LLM client.

### 1.3 Lazy initialization in MCP server

`create_server()` currently initializes everything eagerly (line 192-199), including
`CogneeAdapter()` and `_load_graph()`. If any of these fail, the entire server crashes
on startup.

**Fix:** Initialize each engine lazily on first use, with try/except per engine:

```python
def create_server(config: CodeBrainConfig) -> Server:
    server = Server("code-brain")
    _engines = {}  # lazy cache

    def get_structural():
        if "structural" not in _engines:
            reader = ASTIndexReader(config.project_root)
            _engines["structural"] = StructuralQueryEngine(reader)
        return _engines["structural"]

    def get_graph():
        if "graph" not in _engines:
            graph = _load_graph(config)
            _engines["graph"] = GraphQueryEngine(graph)
        return _engines["graph"]
    # ... etc
```

This way the server starts even if only the AST index is available, and tools
that need missing backends return helpful errors instead of crashing the process.

---

## Phase 2: Query Improvements

*Polish the tools that already work. Better output, better search.*

### 2.1 Outline deduplication / filtering

**Problem:** `ast-index` lists each import separately. For a file like
`cognee/infrastructure/databases/relational/config.py`, the outline includes
entries like `Union` (import), `BinaryIO` (import), `List` (import) -- 6 import
entries that add noise.

**Fix options (pick one):**
- **Filter by kind:** Only return `class`, `function`, and top-level `variable` kinds.
  Drop `import` entries entirely from outline output.
- **Group imports:** Collapse all imports from the same module into a single entry
  (e.g., `from typing import Union, BinaryIO, List` as one line).
- **Add a `--kind` filter** to the outline command/tool so callers can choose.

Recommended: filter imports by default, add `--include-imports` flag for those who
want them.

### 2.2 Partial / fuzzy symbol search

**Problem:** `code_find_symbol` only does exact name match via `WHERE name = ?`.
Users often want to find all symbols containing a substring (e.g., "Config", "Handler").

**Implementation:**
- Add `LIKE` search: `WHERE name LIKE ?` with `%pattern%` wrapping.
- Default behavior: exact match if the query looks like a full symbol name,
  substring match otherwise (or always substring with exact match ranked first).
- Add a `--pattern` or `--like` flag to the CLI `find` command.
- In the MCP tool, if no exact match is found, automatically fall back to LIKE search.

SQL change in `ASTIndexReader.find()`:

```python
if name:
    # Try exact first
    rows = conn.execute("SELECT ... WHERE name = ?", (name,)).fetchall()
    if not rows:
        # Fall back to LIKE
        rows = conn.execute("SELECT ... WHERE name LIKE ?", (f"%{name}%",)).fetchall()
```

### 2.3 Improved MCP tool descriptions

Current descriptions are minimal. LLMs need more context to choose the right tool.
Update `TOOLS` in `mcp_server.py`:

| Tool | Current | Proposed |
|------|---------|----------|
| `code_find_symbol` | "Find symbols by name and/or kind." | "Search for functions, classes, or variables by name. Returns file path, line number, and signature. Use this first to locate code before reading files." |
| `code_outline` | "Get an outline of all symbols defined in a file." | "List all classes, functions, and variables defined in a specific file. Shows the structure without reading the full source. Use relative paths (e.g., src/models/user.py)." |
| `code_usages` | "Find all usages of a symbol across the codebase." | "Find everywhere a function, class, or variable is used. Shows file, line, and surrounding context. Useful for understanding impact before refactoring." |
| `code_map` | "Generate a ranked repository map." | "Generate a ranked overview of the most important symbols in the repo, scored by PageRank and usage. Useful for understanding codebase structure at a glance." |
| `code_impact` | "Analyze the impact of changing a symbol." | "Analyze the blast radius of changing a symbol: who depends on it, how often it changes, and risk level. Use before making breaking changes." |

---

## Phase 3: Semantic Pipeline Polish

*For users who want the full experience with Neo4j + Qdrant.*

### 3.1 Make semantic truly optional at the package level

Currently `mcp_server.py` imports `CogneeAdapter` and `SemanticQueryEngine` at
module level (lines 17-19). If cognee dependencies are not installed, the import
fails and the entire MCP server is unusable.

**Fix:**
- Move semantic imports behind `try/except ImportError` guards.
- If cognee is not installed, semantic tools return: "Semantic features require
  cognee. Install with: pip install code-brain[semantic]"
- Use an extras group in `pyproject.toml`: `[project.optional-dependencies]
  semantic = ["cognee", ...]`

### 3.2 Lighter vector DB alternative

Qdrant requires Docker. Consider supporting ChromaDB as a local alternative:
- ChromaDB runs in-process, pip-installable, no Docker needed.
- Would require an adapter interface so the semantic engine is backend-agnostic.
- Could be the default for local development, with Qdrant for production.

This is a larger refactor. Scope it as a separate design doc.

### 3.3 Better Docker onboarding

For users who do want the full semantic pipeline:
- `code-brain up` should verify services are healthy before returning (poll health endpoints).
- `code-brain doctor` already checks Neo4j and Qdrant reachability -- good.
- Add a `code-brain up --wait` flag that blocks until services are ready.
- Include troubleshooting in error messages (port conflicts, Docker not running, etc.).

---

## Summary: What Each Phase Unlocks

| Phase | Effort | Tools Unlocked | Docker Required |
|-------|--------|---------------|-----------------|
| Phase 1 | ~2-3 days | `code_map`, `code_architecture`, `code_hotspots`, `code_impact`, `code_review_diff` | No |
| Phase 2 | ~1-2 days | Better results from existing tools | No |
| Phase 3 | ~3-5 days | `code_ask`, `code_explain` (polished) | Optional |

After Phase 1, code-brain delivers **10 of 12 tools** with zero Docker dependency.
Only `code_ask` and `code_explain` (semantic search) require backends.
