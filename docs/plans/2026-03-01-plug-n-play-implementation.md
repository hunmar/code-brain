# Plug-n-Play UX Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical bugs and make the first-time experience seamless — from install to first query without friction.

**Architecture:** Fix bugs in-place, add `doctor` command and auto-indexing to `ingest`. No new abstractions. Path normalization added to `StructuralQueryEngine.outline()` so it handles all path formats.

**Tech Stack:** Python 3.11+, typer, sqlite3, subprocess, urllib.request (for health checks)

---

### Task 1: Fix `find` command — add positional name argument

**Files:**
- Modify: `src/code_brain/cli.py:197-213`
- Test: `tests/unit/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_cli.py`:

```python
def test_find_positional_name(tmp_path, monkeypatch):
    """code-brain find UserService should work as a positional arg."""
    from unittest.mock import patch, MagicMock

    mock_engine = MagicMock()
    mock_engine.find.return_value = [
        {"id": 1, "name": "UserService", "kind": "class",
         "file_path": "src/svc.py", "line": 5, "signature": "class UserService"}
    ]

    with patch("code_brain.cli._get_structural_engine", return_value=mock_engine):
        result = runner.invoke(app, ["find", "UserService"])
    assert result.exit_code == 0
    assert "UserService" in result.stdout
    mock_engine.find.assert_called_once_with(name="UserService", kind=None, limit=100)


def test_find_no_args_lists_all(tmp_path, monkeypatch):
    """code-brain find (no args) should list all symbols."""
    from unittest.mock import patch, MagicMock

    mock_engine = MagicMock()
    mock_engine.find.return_value = []

    with patch("code_brain.cli._get_structural_engine", return_value=mock_engine):
        result = runner.invoke(app, ["find"])
    assert result.exit_code == 0
    mock_engine.find.assert_called_once_with(name=None, kind=None, limit=100)
```

**Step 2: Run test to verify it fails**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py::test_find_positional_name -v`
Expected: FAIL — `find` doesn't accept positional argument, exits with "Got unexpected extra argument"

**Step 3: Write minimal implementation**

In `src/code_brain/cli.py`, replace the `find` command (lines 197-213) with:

```python
@app.command()
def find(
    name: Optional[str] = typer.Argument(None, help="Symbol name to search"),
    kind: Optional[str] = typer.Option(None, help="Symbol kind (class, function, etc.)"),
    limit: int = typer.Option(100, help="Max results"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Find symbols in the codebase."""
    cfg = _get_config(project)
    engine = _get_structural_engine(cfg)
    results = engine.find(name=name, kind=kind, limit=limit)
    if json:
        typer.echo(json_fmt.format(results))
    else:
        typer.echo(text_fmt.format_symbols(results))
```

The only change: `name` goes from `typer.Option(None)` to `typer.Argument(None)` — optional positional argument.

**Step 4: Run test to verify it passes**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/code_brain/cli.py tests/unit/test_cli.py
git commit -m "fix: make find command accept positional name argument"
```

---

### Task 2: Fix `serve` command — broken import and signature

**Files:**
- Modify: `src/code_brain/cli.py:382-395`
- Modify: `src/code_brain/mcp_server.py:281-285`
- Test: `tests/unit/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_cli.py`:

```python
def test_serve_import_works():
    """Verify the serve command can import run_server without error."""
    from code_brain.mcp_server import run_server
    assert callable(run_server)
```

**Step 2: Run test to verify it fails**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py::test_serve_import_works -v`
Expected: PASS (the function exists as `run_server`, the bug is in the cli import)

Now test the actual CLI command:

```python
def test_serve_command_exists():
    """Verify serve command is registered and help works."""
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "MCP" in result.stdout or "server" in result.stdout.lower()
```

**Step 3: Write minimal implementation**

In `src/code_brain/cli.py`, replace the `serve` command (lines 382-395) with:

```python
@app.command()
def serve(
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Start the MCP server (stdio transport)."""
    cfg = _get_config(project)
    from code_brain.mcp_server import run_server

    asyncio.run(run_server(cfg))
```

Changes:
- Removed `host` and `port` params (MCP uses stdio, not HTTP)
- Fixed import from `serve` to `run_server`
- Pass `cfg` (CodeBrainConfig) instead of host/port

**Step 4: Run test to verify it passes**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/code_brain/cli.py tests/unit/test_cli.py
git commit -m "fix: serve command uses correct import and passes config"
```

---

### Task 3: Fix `outline` path normalization

**Files:**
- Modify: `src/code_brain/query/structural.py:41-51`
- Test: `tests/unit/test_structural_queries.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_structural_queries.py`:

```python
def test_outline_with_dot_slash(engine):
    """./src/models/user.py should match src/models/user.py."""
    result = engine.outline("./src/models/user.py")
    assert len(result) == 2


def test_outline_with_absolute_path(engine, sample_db):
    """Absolute path should be stripped to relative."""
    abs_path = str(sample_db / "src/models/user.py")
    result = engine.outline(abs_path, project_root=sample_db)
    assert len(result) == 2


def test_outline_suffix_match(engine):
    """user.py alone should match src/models/user.py."""
    result = engine.outline("user.py")
    assert len(result) == 2
```

**Step 2: Run test to verify they fail**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_structural_queries.py::test_outline_with_dot_slash -v`
Expected: FAIL — returns 0 results because exact match `./src/models/user.py` doesn't match `src/models/user.py`

**Step 3: Write minimal implementation**

Replace `StructuralQueryEngine.outline()` in `src/code_brain/query/structural.py`:

```python
class StructuralQueryEngine:
    def __init__(self, reader: ASTIndexReader, project_root: Path | None = None):
        self._reader = reader
        self._project_root = project_root

    # ... (keep find, hierarchy, usages, deps unchanged)

    def outline(self, file_path: str, project_root: Path | None = None) -> list[dict]:
        root = project_root or self._project_root
        normalized = file_path

        # Strip leading ./
        if normalized.startswith("./"):
            normalized = normalized[2:]

        # Strip project root prefix if absolute
        if root and normalized.startswith(str(root)):
            normalized = normalized[len(str(root)):].lstrip("/")

        # Try exact match first
        symbols = self._reader.get_file_outline(normalized)

        # Fallback: suffix match (user gave "user.py", DB has "src/models/user.py")
        if not symbols and "/" not in normalized:
            symbols = self._reader.get_file_outline_by_suffix(normalized)

        return [
            {
                "name": s.name,
                "kind": s.kind,
                "line": s.line,
                "signature": s.signature,
            }
            for s in symbols
        ]
```

Also add `get_file_outline_by_suffix` to `src/code_brain/ingestion/ast_index.py` after `get_file_outline`:

```python
def get_file_outline_by_suffix(self, filename: str) -> list[Symbol]:
    conn = self._get_conn()
    rows = conn.execute("""
        SELECT s.id, s.name, s.kind, f.path, s.line, s.signature, s.parent_id
        FROM symbols s
        JOIN files f ON s.file_id = f.id
        WHERE f.path LIKE ?
        ORDER BY s.line
    """, (f"%/{filename}",)).fetchall()
    return [Symbol(
        id=r["id"], name=r["name"], kind=r["kind"],
        file_path=r["path"], line=r["line"],
        signature=r["signature"] or "", parent_id=r["parent_id"]
    ) for r in rows]
```

Also update `_get_structural_engine` in `cli.py` to pass project_root:

```python
def _get_structural_engine(cfg: CodeBrainConfig):
    from code_brain.ingestion.ast_index import ASTIndexReader
    from code_brain.query.structural import StructuralQueryEngine

    reader = ASTIndexReader(cfg.project_root)
    if not reader.is_available():
        typer.echo("Error: AST index not found. Run 'code-brain ingest' to build it.")
        raise typer.Exit(1)
    return StructuralQueryEngine(reader, project_root=cfg.project_root)
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_structural_queries.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/code_brain/ingestion/ast_index.py src/code_brain/query/structural.py src/code_brain/cli.py tests/unit/test_structural_queries.py
git commit -m "fix: normalize file paths in outline command"
```

---

### Task 4: Auto-run `ast-index rebuild` during `ingest`

**Files:**
- Modify: `src/code_brain/cli.py:116-194` (ingest command)
- Modify: `src/code_brain/ingestion/ast_index.py` (expose `_find_ast_index_bin`)
- Test: `tests/unit/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_cli.py`:

```python
def test_ingest_runs_ast_index_when_no_db(tmp_path, monkeypatch):
    """ingest should try ast-index rebuild when no DB exists."""
    from unittest.mock import patch, MagicMock, call

    # Set up minimal project
    (tmp_path / ".code-brain").mkdir()
    monkeypatch.setenv("CODE_BRAIN_PROJECT", str(tmp_path))

    mock_run = MagicMock()
    mock_run.return_value.returncode = 1  # ast-index rebuild fails

    with patch("subprocess.run", mock_run):
        result = runner.invoke(app, ["ingest"])

    # Should have attempted ast-index rebuild
    calls = [str(c) for c in mock_run.call_args_list]
    assert any("ast-index" in c and "rebuild" in c for c in calls), \
        f"Expected ast-index rebuild call, got: {calls}"


def test_ingest_rebuild_flag(tmp_path, monkeypatch):
    """ingest --rebuild should force ast-index rebuild even if DB exists."""
    from unittest.mock import patch, MagicMock

    (tmp_path / ".code-brain").mkdir()
    # Create a fake DB so it would normally skip
    db_dir = tmp_path / ".ast-index"
    db_dir.mkdir()
    (db_dir / "db.sqlite3").touch()
    monkeypatch.setenv("CODE_BRAIN_PROJECT", str(tmp_path))

    mock_run = MagicMock()
    mock_run.return_value.returncode = 0

    with patch("subprocess.run", mock_run):
        with patch("code_brain.cli._get_structural_engine") as mock_engine:
            mock_engine.side_effect = SystemExit(1)  # will fail after rebuild
            result = runner.invoke(app, ["ingest", "--rebuild"])

    calls = [str(c) for c in mock_run.call_args_list]
    assert any("rebuild" in c for c in calls)
```

**Step 2: Run test to verify it fails**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py::test_ingest_runs_ast_index_when_no_db -v`
Expected: FAIL — current `ingest` doesn't call ast-index rebuild

**Step 3: Write minimal implementation**

In `src/code_brain/cli.py`, update the `ingest` command to add auto-indexing at the top:

```python
@app.command()
def ingest(
    project: Optional[str] = typer.Option(None, help="Project root"),
    skip_semantic: bool = typer.Option(False, "--skip-semantic", help="Skip semantic ingestion"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Force ast-index rebuild"),
):
    """Build the code graph and ingest into backends."""
    cfg = _get_config(project)
    cfg.ensure_dirs()

    from code_brain.ingestion.ast_index import ASTIndexReader, _find_ast_index_bin

    reader = ASTIndexReader(cfg.project_root)

    # Auto-run ast-index rebuild if DB missing or --rebuild flag
    if rebuild or not reader.is_available():
        ast_bin = _find_ast_index_bin()
        typer.echo(f"Running ast-index rebuild (binary: {ast_bin})...")
        try:
            result = subprocess.run(
                [ast_bin, "rebuild"],
                cwd=cfg.project_root,
                check=False,
                timeout=300,
            )
            if result.returncode != 0:
                typer.echo("Warning: ast-index rebuild failed. Continuing with existing index if available.")
        except FileNotFoundError:
            typer.echo(
                "Error: ast-index not installed.\n"
                "Install via: cargo install --git https://github.com/nickarash/ast-index ast-index\n"
                "Or visit: https://github.com/nickarash/ast-index"
            )
            raise typer.Exit(1)
        except subprocess.TimeoutExpired:
            typer.echo("Error: ast-index rebuild timed out after 5 minutes.")
            raise typer.Exit(1)

        # Re-create reader to pick up new DB path
        reader = ASTIndexReader(cfg.project_root)

    if not reader.is_available():
        typer.echo("Error: AST index not found after rebuild. Check ast-index installation.")
        raise typer.Exit(1)

    typer.echo("Reading AST index...")
    symbols = reader.get_symbols()

    # ... rest of ingest unchanged from line 137 onward
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/code_brain/cli.py tests/unit/test_cli.py
git commit -m "feat: auto-run ast-index rebuild during ingest when DB missing"
```

---

### Task 5: Add `doctor` command

**Files:**
- Modify: `src/code_brain/cli.py` (add new command)
- Test: `tests/unit/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_cli.py`:

```python
def test_doctor_command_runs(tmp_path, monkeypatch):
    """doctor should report status without crashing."""
    monkeypatch.setenv("CODE_BRAIN_PROJECT", str(tmp_path))
    (tmp_path / ".code-brain").mkdir()

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "ast-index" in result.stdout.lower()


def test_doctor_shows_all_checks(tmp_path, monkeypatch):
    """doctor should check ast-index, graph, docker, neo4j, qdrant."""
    monkeypatch.setenv("CODE_BRAIN_PROJECT", str(tmp_path))
    (tmp_path / ".code-brain").mkdir()

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    output = result.stdout.lower()
    assert "ast-index binary" in output or "ast-index" in output
    assert "graph" in output
```

**Step 2: Run test to verify it fails**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py::test_doctor_command_runs -v`
Expected: FAIL — no `doctor` command exists

**Step 3: Write minimal implementation**

Add to `src/code_brain/cli.py` (after the `status` command, around line 114):

```python
@app.command()
def doctor(
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Check system health and diagnose setup issues."""
    import shutil

    root = None
    if project:
        root = Path(project)
    else:
        env_project = os.environ.get("CODE_BRAIN_PROJECT")
        if env_project:
            root = Path(env_project)
        else:
            root = find_project_root(Path.cwd())

    typer.echo("Code Brain Doctor")
    typer.echo("=" * 40)

    # 1. Project
    if root and (root / ".code-brain").is_dir():
        typer.echo(f"  Project:        OK ({root})")
        cfg = CodeBrainConfig(project_root=root)
    else:
        typer.echo(f"  Project:        NOT INITIALIZED")
        typer.echo("    Run: code-brain init <path>")
        cfg = None

    # 2. ast-index binary
    from code_brain.ingestion.ast_index import _find_ast_index_bin
    ast_bin = _find_ast_index_bin()
    ast_found = shutil.which(ast_bin) is not None or Path(ast_bin).is_file()
    if ast_found:
        typer.echo(f"  ast-index binary: OK ({ast_bin})")
    else:
        typer.echo(f"  ast-index binary: NOT FOUND")
        typer.echo("    Install: cargo install --git https://github.com/nickarash/ast-index ast-index")

    # 3. ast-index DB
    if cfg:
        from code_brain.ingestion.ast_index import ASTIndexReader
        reader = ASTIndexReader(cfg.project_root)
        if reader.is_available():
            try:
                count = len(reader.get_symbols())
                typer.echo(f"  AST index DB:   OK ({count} symbols)")
                reader.close()
            except Exception as e:
                typer.echo(f"  AST index DB:   ERROR ({e})")
        else:
            typer.echo(f"  AST index DB:   NOT FOUND")
            typer.echo("    Run: code-brain ingest")
    else:
        typer.echo(f"  AST index DB:   SKIPPED (no project)")

    # 4. Graph
    if cfg and cfg.graph_path.is_file():
        try:
            from code_brain.graph.builder import GraphBuilder
            graph = GraphBuilder().load(cfg.graph_path)
            typer.echo(f"  Graph:          OK ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges)")
        except Exception as e:
            typer.echo(f"  Graph:          ERROR ({e})")
    elif cfg:
        typer.echo(f"  Graph:          NOT FOUND")
        typer.echo("    Run: code-brain ingest")
    else:
        typer.echo(f"  Graph:          SKIPPED (no project)")

    # 5. Docker
    docker_found = shutil.which("docker") is not None
    if docker_found:
        typer.echo(f"  Docker:         OK")
    else:
        typer.echo(f"  Docker:         NOT FOUND")
        typer.echo("    Required for semantic features (Neo4j + Qdrant)")

    # 6. Neo4j
    if cfg:
        try:
            import urllib.request
            url = cfg.neo4j_uri.replace("bolt://", "http://").replace(":7687", ":7474")
            urllib.request.urlopen(url, timeout=3)
            typer.echo(f"  Neo4j:          OK ({cfg.neo4j_uri})")
        except Exception:
            typer.echo(f"  Neo4j:          NOT REACHABLE ({cfg.neo4j_uri})")
            typer.echo("    Run: code-brain up")
    else:
        typer.echo(f"  Neo4j:          SKIPPED (no project)")

    # 7. Qdrant
    if cfg:
        try:
            import urllib.request
            urllib.request.urlopen(cfg.qdrant_url, timeout=3)
            typer.echo(f"  Qdrant:         OK ({cfg.qdrant_url})")
        except Exception:
            typer.echo(f"  Qdrant:         NOT REACHABLE ({cfg.qdrant_url})")
            typer.echo("    Run: code-brain up")
    else:
        typer.echo(f"  Qdrant:         SKIPPED (no project)")
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/code_brain/cli.py tests/unit/test_cli.py
git commit -m "feat: add doctor command for system health checks"
```

---

### Task 6: Improve error messages

**Files:**
- Modify: `src/code_brain/cli.py` (multiple locations)
- Test: `tests/unit/test_cli.py`

**Step 1: Write the failing test**

Add to `tests/unit/test_cli.py`:

```python
def test_error_message_mentions_ingest(tmp_path, monkeypatch):
    """When AST index missing, error should mention 'ingest'."""
    monkeypatch.setenv("CODE_BRAIN_PROJECT", str(tmp_path))
    (tmp_path / ".code-brain").mkdir()

    result = runner.invoke(app, ["find", "Foo"])
    assert "ingest" in result.stdout.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py::test_error_message_mentions_ingest -v`
Expected: FAIL — current error says "Run ast-index first", not "ingest"

**Step 3: Write minimal implementation**

Update `_get_structural_engine` in `src/code_brain/cli.py`:

```python
def _get_structural_engine(cfg: CodeBrainConfig):
    from code_brain.ingestion.ast_index import ASTIndexReader
    from code_brain.query.structural import StructuralQueryEngine

    reader = ASTIndexReader(cfg.project_root)
    if not reader.is_available():
        typer.echo(
            "Error: AST index not found.\n"
            "  Run: code-brain ingest\n"
            "  Or check: code-brain doctor"
        )
        raise typer.Exit(1)
    return StructuralQueryEngine(reader, project_root=cfg.project_root)
```

Update `_load_graph` in `src/code_brain/cli.py`:

```python
def _load_graph(cfg: CodeBrainConfig):
    from code_brain.graph.builder import GraphBuilder

    if not cfg.graph_path.is_file():
        typer.echo(
            "Error: Code graph not found.\n"
            "  Run: code-brain ingest\n"
            "  Or check: code-brain doctor"
        )
        raise typer.Exit(1)
    return GraphBuilder().load(cfg.graph_path)
```

Update `up` command to handle Docker not found:

```python
@app.command()
def up(project: Optional[str] = typer.Option(None, help="Project root")):
    """Start backend services (Neo4j, Qdrant) via docker compose."""
    import shutil

    if not shutil.which("docker"):
        typer.echo(
            "Error: Docker not found.\n"
            "  Install Docker: https://docs.docker.com/get-docker/\n"
            "  Or use --skip-semantic with ingest to skip semantic features."
        )
        raise typer.Exit(1)

    cfg = _get_config(project)
    compose_file = cfg.code_brain_dir / "docker-compose.yml"
    if not compose_file.is_file():
        typer.echo("No docker-compose.yml found. Creating default...")
        compose_file.write_text(_default_compose())
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        check=True,
    )
    typer.echo("Services started.")
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/exedev/code-brain && uv run pytest tests/unit/test_cli.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/code_brain/cli.py tests/unit/test_cli.py
git commit -m "fix: improve error messages with actionable suggestions"
```

---

### Task 7: Fix README mismatches

**Files:**
- Modify: `README.md`

**Step 1: Fix `--tokens` → `--budget`**

In `README.md`, line 89, change:

```
code-brain map --tokens 8000      # Larger context budget
```

to:

```
code-brain map --budget 8000      # Larger context budget
```

**Step 2: Update `find` examples**

The find examples are already positional in the README (lines 75-76), which is correct now that Task 1 is done. No change needed.

**Step 3: Add `doctor` command**

Add to the Usage section after the `code-brain serve` line:

```bash
# Diagnose setup
code-brain doctor                  # Check what's installed and working
```

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: fix README to match actual CLI flags"
```

---

### Task 8: Run full test suite and push

**Step 1: Run all tests**

Run: `cd /home/exedev/code-brain && uv run pytest -v`
Expected: ALL PASS

**Step 2: Push**

```bash
git push
```

**Step 3: Manual smoke test against cognee repo**

```bash
cd /home/exedev/cognee
code-brain init .
code-brain doctor
code-brain find CogneeConfig
code-brain outline cognee/infrastructure/databases/relational/config.py
code-brain outline config.py
```

Expected:
- `doctor` shows ast-index OK, DB OK (from earlier rebuild)
- `find CogneeConfig` returns results
- `outline` with full path works
- `outline` with just filename works via suffix match
