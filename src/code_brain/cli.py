import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from code_brain import __version__
from code_brain.config import CodeBrainConfig, find_project_root
from code_brain.formatters.json_formatter import JsonFormatter
from code_brain.formatters.text_formatter import TextFormatter

app = typer.Typer(name="code-brain", help="Unified code intelligence for LLM agents")
json_fmt = JsonFormatter()
text_fmt = TextFormatter()


def _version_callback(value: bool):
    if value:
        print(f"code-brain {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
    ),
):
    pass


def _get_config(project: str | None = None) -> CodeBrainConfig:
    root = None
    if project:
        root = Path(project)
    else:
        env_project = os.environ.get("CODE_BRAIN_PROJECT")
        if env_project:
            root = Path(env_project)
        else:
            root = find_project_root(Path.cwd())
    if root is None:
        typer.echo("Error: not initialized. Run 'code-brain init <path>' first.")
        raise typer.Exit(1)
    return CodeBrainConfig(project_root=root)


@app.command()
def init(path: str = typer.Argument(".", help="Project root path")):
    """Initialize code-brain for a project."""
    root = Path(path).resolve()
    cfg = CodeBrainConfig(project_root=root)
    cfg.ensure_dirs()
    typer.echo(f"Initialized code-brain at {cfg.code_brain_dir}")


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


@app.command()
def down(project: Optional[str] = typer.Option(None, help="Project root")):
    """Stop backend services."""
    cfg = _get_config(project)
    compose_file = cfg.code_brain_dir / "docker-compose.yml"
    if not compose_file.is_file():
        typer.echo("No docker-compose.yml found.")
        raise typer.Exit(1)
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "down"],
        check=True,
    )
    typer.echo("Services stopped.")


@app.command()
def status(project: Optional[str] = typer.Option(None, help="Project root")):
    """Show project status."""
    root = None
    if project:
        root = Path(project)
    else:
        env_project = os.environ.get("CODE_BRAIN_PROJECT")
        if env_project:
            root = Path(env_project)
        else:
            root = find_project_root(Path.cwd())

    if root is None:
        typer.echo("Status: not initialized")
        typer.echo("Run 'code-brain init <path>' to get started.")
        raise typer.Exit(0)

    cfg = CodeBrainConfig(project_root=root)
    typer.echo(f"Project root: {cfg.project_root}")
    typer.echo(f"Config dir:   {cfg.code_brain_dir}")
    typer.echo(f"Config exists: {cfg.code_brain_dir.is_dir()}")
    typer.echo(f"Graph exists:  {cfg.graph_path.is_file()}")
    typer.echo(f"AST index:     {cfg.ast_index_db_path.is_file()}")


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
        typer.echo(f"  Project:          OK ({root})")
        cfg = CodeBrainConfig(project_root=root)
    else:
        typer.echo("  Project:          NOT INITIALIZED")
        typer.echo("    Run: code-brain init <path>")
        cfg = None

    # 2. ast-index binary
    from code_brain.ingestion.ast_index import _find_ast_index_bin
    ast_bin = _find_ast_index_bin()
    ast_found = shutil.which(ast_bin) is not None or Path(ast_bin).is_file()
    if ast_found:
        typer.echo(f"  ast-index binary: OK ({ast_bin})")
    else:
        typer.echo("  ast-index binary: NOT FOUND")
        typer.echo("    Install: cargo install --git https://github.com/nickarash/ast-index ast-index")

    # 3. ast-index DB
    if cfg:
        from code_brain.ingestion.ast_index import ASTIndexReader
        reader = ASTIndexReader(cfg.project_root)
        if reader.is_available():
            try:
                count = len(reader.get_symbols())
                typer.echo(f"  AST index DB:     OK ({count} symbols)")
                reader.close()
            except Exception as e:
                typer.echo(f"  AST index DB:     ERROR ({e})")
        else:
            typer.echo("  AST index DB:     NOT FOUND")
            typer.echo("    Run: code-brain ingest")
    else:
        typer.echo("  AST index DB:     SKIPPED (no project)")

    # 4. Graph
    if cfg and cfg.graph_path.is_file():
        try:
            from code_brain.graph.builder import GraphBuilder
            graph = GraphBuilder().load(cfg.graph_path)
            typer.echo(f"  Graph:            OK ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges)")
        except Exception as e:
            typer.echo(f"  Graph:            ERROR ({e})")
    elif cfg:
        typer.echo("  Graph:            NOT FOUND")
        typer.echo("    Run: code-brain ingest")
    else:
        typer.echo("  Graph:            SKIPPED (no project)")

    # 5. Docker
    docker_found = shutil.which("docker") is not None
    if docker_found:
        typer.echo("  Docker:           OK")
    else:
        typer.echo("  Docker:           NOT FOUND")
        typer.echo("    Required for semantic features (Neo4j + Qdrant)")

    # 6. Neo4j
    if cfg:
        try:
            import urllib.request
            url = cfg.neo4j_uri.replace("bolt://", "http://").replace(":7687", ":7474")
            urllib.request.urlopen(url, timeout=3)
            typer.echo(f"  Neo4j:            OK ({cfg.neo4j_uri})")
        except Exception:
            typer.echo(f"  Neo4j:            NOT REACHABLE ({cfg.neo4j_uri})")
            typer.echo("    Run: code-brain up")
    else:
        typer.echo("  Neo4j:            SKIPPED (no project)")

    # 7. Qdrant
    if cfg:
        try:
            import urllib.request
            urllib.request.urlopen(cfg.qdrant_url, timeout=3)
            typer.echo(f"  Qdrant:           OK ({cfg.qdrant_url})")
        except Exception:
            typer.echo(f"  Qdrant:           NOT REACHABLE ({cfg.qdrant_url})")
            typer.echo("    Run: code-brain up")
    else:
        typer.echo("  Qdrant:           SKIPPED (no project)")


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
    from code_brain.ingestion.git_analyzer import GitAnalyzer
    from code_brain.graph.builder import GraphBuilder

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
                "  Install via: cargo install --git https://github.com/nickarash/ast-index ast-index\n"
                "  Or visit: https://github.com/nickarash/ast-index"
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

    typer.echo("Collecting inheritance...")
    inheritance: dict[str, list[str]] = {}
    for sym in symbols:
        if sym.kind == "class":
            parents = reader.get_parents(sym.name)
            if parents:
                inheritance[sym.name] = parents

    typer.echo("Collecting module dependencies...")
    modules = set()
    for sym in symbols:
        parts = sym.file_path.replace("/", ".").removesuffix(".py")
        modules.add(parts)
    all_deps = []
    for mod in modules:
        all_deps.extend(reader.get_module_deps(mod))

    typer.echo("Collecting usages...")
    all_usages: dict[str, list] = {}
    for sym in symbols:
        usages_list = reader.get_usages(sym.name, limit=50)
        if usages_list:
            all_usages[sym.name] = usages_list

    typer.echo("Analyzing git history...")
    git = GitAnalyzer(cfg.project_root)
    hot_spots = git.hot_spots()
    co_changes = git.co_changes()

    typer.echo("Building graph...")
    builder = GraphBuilder()
    graph = builder.build(
        symbols=symbols,
        inheritance=inheritance,
        module_deps=all_deps,
        usages=all_usages,
        hot_spots=hot_spots,
        co_changes=co_changes,
    )
    builder.save(graph, cfg.graph_path)
    typer.echo(f"Graph saved: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    if not skip_semantic:
        typer.echo("Ingesting into semantic store...")
        from code_brain.ingestion.cognee_adapter import CogneeAdapter
        from code_brain.ingestion.doc_ingester import find_docs

        adapter = CogneeAdapter()
        asyncio.run(adapter.ingest_symbols(symbols))
        asyncio.run(adapter.ingest_module_deps(all_deps))

        docs = find_docs(cfg.project_root)
        if docs:
            asyncio.run(adapter.ingest_docs(docs))
            typer.echo(f"Ingested {len(docs)} documents.")

    typer.echo("Ingestion complete.")
    reader.close()


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


@app.command()
def hierarchy(
    class_name: str = typer.Argument(..., help="Class name"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Show class hierarchy."""
    cfg = _get_config(project)
    engine = _get_structural_engine(cfg)
    result = engine.hierarchy(class_name)
    if json:
        typer.echo(json_fmt.format(result))
    else:
        typer.echo(text_fmt.format_hierarchy(result))


@app.command()
def usages(
    symbol: str = typer.Argument(..., help="Symbol name"),
    limit: int = typer.Option(100, help="Max results"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Find usages of a symbol."""
    cfg = _get_config(project)
    engine = _get_structural_engine(cfg)
    results = engine.usages(symbol, limit=limit)
    if json:
        typer.echo(json_fmt.format(results))
    else:
        typer.echo(text_fmt.format_usages(results))


@app.command()
def deps(
    module: str = typer.Argument(..., help="Module name"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Show module dependencies."""
    cfg = _get_config(project)
    engine = _get_structural_engine(cfg)
    results = engine.deps(module)
    if json:
        typer.echo(json_fmt.format(results))
    else:
        typer.echo(text_fmt.format_deps(results))


@app.command()
def outline(
    file_path: str = typer.Argument(..., help="File path"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Show file outline (symbols in a file)."""
    cfg = _get_config(project)
    engine = _get_structural_engine(cfg)
    results = engine.outline(file_path)
    if json:
        typer.echo(json_fmt.format(results))
    else:
        typer.echo(text_fmt.format_symbols(results))


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Ask a semantic question about the codebase."""
    cfg = _get_config(project)
    engine = _get_semantic_engine(cfg)
    results = asyncio.run(engine.ask(question))
    if json:
        typer.echo(json_fmt.format(results))
    else:
        for item in results:
            typer.echo(f"  {item.get('text', str(item))}")
        if not results:
            typer.echo("No results found.")


@app.command(name="map")
def repo_map(
    focus: Optional[str] = typer.Option(None, help="Comma-separated focus files"),
    budget: int = typer.Option(4000, help="Token budget"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Generate a repository map."""
    cfg = _get_config(project)
    graph = _load_graph(cfg)
    from code_brain.graph.queries import GraphQueryEngine

    engine = GraphQueryEngine(graph)
    focus_files = [f.strip() for f in focus.split(",")] if focus else None
    result = engine.repo_map(focus_files=focus_files, token_budget=budget)
    typer.echo(result)


@app.command()
def hotspots(
    limit: int = typer.Option(10, help="Max results"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Show change hotspots."""
    cfg = _get_config(project)
    graph = _load_graph(cfg)
    from code_brain.graph.queries import GraphQueryEngine

    engine = GraphQueryEngine(graph)
    results = engine.hotspots(limit=limit)
    if json:
        typer.echo(json_fmt.format(results))
    else:
        for h in results:
            typer.echo(f"  {h['file_path']}  ({h['change_frequency']} changes)  {h['kind']} {h['name']}")
        if not results:
            typer.echo("No hotspots found.")


@app.command()
def arch(
    fmt: str = typer.Option("mermaid", help="Output format: mermaid or text"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Show architecture diagram."""
    cfg = _get_config(project)
    graph = _load_graph(cfg)
    from code_brain.graph.queries import GraphQueryEngine

    engine = GraphQueryEngine(graph)
    result = engine.architecture(fmt=fmt)
    typer.echo(result)


@app.command()
def impact(
    symbol: str = typer.Argument(..., help="Symbol name"),
    budget: int = typer.Option(8000, help="Token budget"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Analyze impact of changing a symbol."""
    cfg = _get_config(project)
    graph = _load_graph(cfg)
    structural = _get_structural_engine(cfg)
    semantic = _get_semantic_engine(cfg)

    from code_brain.query.hybrid import HybridQueryEngine

    engine = HybridQueryEngine(structural=structural, semantic=semantic, graph=graph)
    result = asyncio.run(engine.impact(symbol, token_budget=budget))
    if json:
        typer.echo(json_fmt.format(result))
    else:
        typer.echo(f"Symbol: {result.get('symbol')}")
        typer.echo(f"Location: {result.get('location', '?')}")
        typer.echo(f"Risk: {result.get('risk_level', '?')}")
        typer.echo(f"Dependents: {result.get('dependent_count', 0)}")
        typer.echo(f"Change frequency: {result.get('change_frequency', 0)}")
        if result.get("error"):
            typer.echo(f"Error: {result['error']}")


@app.command()
def serve(
    project: Optional[str] = typer.Option(None, help="Project root"),
):
    """Start the MCP server (stdio transport)."""
    cfg = _get_config(project)
    from code_brain.mcp_server import run_server

    asyncio.run(run_server(cfg))


# ── helpers ──────────────────────────────────────────────────────────────


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


def _get_semantic_engine(cfg: CodeBrainConfig):
    from code_brain.ingestion.cognee_adapter import CogneeAdapter
    from code_brain.query.semantic import SemanticQueryEngine

    adapter = CogneeAdapter()
    return SemanticQueryEngine(adapter)


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


def _default_compose() -> str:
    return """\
services:
  neo4j:
    image: neo4j:5
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/codebrain
    volumes:
      - neo4j_data:/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  neo4j_data:
  qdrant_data:
"""
