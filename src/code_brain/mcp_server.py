"""MCP server exposing code-brain tools for code intelligence."""
from __future__ import annotations

import json
import time
from typing import Awaitable

import networkx as nx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from code_brain.config import CodeBrainConfig
from code_brain.graph.builder import GraphBuilder
from code_brain.graph.queries import GraphQueryEngine
from code_brain.ingestion.ast_index import ASTIndexReader
from code_brain.ingestion.cognee_adapter import CogneeAdapter
from code_brain.query.hybrid import HybridQueryEngine
from code_brain.query.semantic import SemanticQueryEngine
from code_brain.query.structural import StructuralQueryEngine
from code_brain.telemetry import log_tool_event

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

TOOLS = [
    Tool(
        name="code_find_symbol",
        description="Find symbols (functions, classes, variables) by name and/or kind.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Symbol name to search for"},
                "kind": {"type": "string", "description": "Symbol kind (function, class, variable)"},
                "limit": {"type": "integer", "description": "Max results", "default": 100},
            },
        },
    ),
    Tool(
        name="code_hierarchy",
        description="Get the inheritance hierarchy for a class.",
        inputSchema={
            "type": "object",
            "properties": {
                "class_name": {"type": "string", "description": "Class name to look up"},
            },
            "required": ["class_name"],
        },
    ),
    Tool(
        name="code_dependencies",
        description="Get module-level dependencies for a given module.",
        inputSchema={
            "type": "object",
            "properties": {
                "module": {"type": "string", "description": "Module name"},
            },
            "required": ["module"],
        },
    ),
    Tool(
        name="code_usages",
        description="Find all usages of a symbol across the codebase.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol name to find usages of"},
                "limit": {"type": "integer", "description": "Max results", "default": 100},
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="code_outline",
        description="Get an outline of all symbols defined in a file.",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "File path to outline"},
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="code_ask",
        description="Ask a natural language question about the codebase with graph-backed semantic context.",
        inputSchema={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question to ask"},
            },
            "required": ["question"],
        },
    ),
    Tool(
        name="code_explain",
        description="Explain a symbol with structural location details and semantic context.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol name to explain"},
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="code_impact",
        description="Analyze change impact: dependents, risk level, and semantic business impact.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol name to analyze"},
                "token_budget": {"type": "integer", "description": "Token budget", "default": 8000},
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="code_review_diff",
        description="Review a diff for potential issues using semantic coding-rule analysis.",
        inputSchema={
            "type": "object",
            "properties": {
                "diff": {"type": "string", "description": "Diff text to review"},
            },
            "required": ["diff"],
        },
    ),
    Tool(
        name="code_map",
        description="Generate a ranked repository map of the most important symbols.",
        inputSchema={
            "type": "object",
            "properties": {
                "focus_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to focus on",
                },
                "token_budget": {"type": "integer", "description": "Token budget", "default": 4000},
            },
        },
    ),
    Tool(
        name="code_hotspots",
        description="Find frequently changed code hotspots.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results", "default": 10},
            },
        },
    ),
    Tool(
        name="code_architecture",
        description="Generate an architecture diagram of module dependencies.",
        inputSchema={
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["mermaid", "text"],
                    "description": "Output format",
                    "default": "mermaid",
                },
            },
        },
    ),
    Tool(
        name="code_search",
        description="Fast semantic search using vector chunks, optimized for quick concept lookup.",
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
        description="Run chain-of-thought-style graph reasoning for complex architecture questions.",
        inputSchema={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Complex question requiring reasoning"},
            },
            "required": ["question"],
        },
    ),
]


def _load_graph(config: CodeBrainConfig) -> nx.DiGraph:
    if config.graph_path.is_file():
        return GraphBuilder().load(config.graph_path)
    return nx.DiGraph()


def _missing_argument(tool_name: str, argument_name: str) -> dict:
    return {
        "error": f"Missing required argument '{argument_name}' for tool '{tool_name}'.",
        "hint": "Use list_tools to inspect the required input schema.",
    }


def _is_semantic_backend_error(error_message: str) -> bool:
    lowered = error_message.lower()
    patterns = [
        "operationalerror",
        "connection refused",
        "unable to open database file",
        "neo4j",
        "qdrant",
        "timed out",
        "timeout",
    ]
    return any(pattern in lowered for pattern in patterns)


async def _safe_semantic_call(coro: Awaitable[dict | list | str]) -> dict | list | str:
    try:
        return await coro
    except Exception as exc:  # noqa: BLE001
        details = str(exc)
        if _is_semantic_backend_error(details):
            return {
                "answer": "Semantic features are currently unavailable.",
                "evidence": [],
                "confidence": "low",
                "degraded": True,
                "warnings": [
                    "Run: code-brain up && code-brain ingest",
                    details,
                ],
            }
        return {
            "answer": "",
            "evidence": [],
            "confidence": "low",
            "degraded": True,
            "warnings": [f"Semantic query failed: {details}"],
        }


def create_server(config: CodeBrainConfig) -> Server:
    server = Server("code-brain")

    reader = ASTIndexReader(config.project_root)
    adapter = CogneeAdapter()
    graph = _load_graph(config)

    structural = StructuralQueryEngine(reader, project_root=config.project_root)
    semantic = SemanticQueryEngine(adapter)
    hybrid = HybridQueryEngine(structural, semantic, graph)
    graph_engine = GraphQueryEngine(graph)

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        start = time.perf_counter()
        result = await _dispatch(
            name,
            args,
            structural,
            semantic,
            hybrid,
            graph_engine,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        log_tool_event(
            config.events_path,
            tool=name,
            arguments=args,
            result=result,
            duration_ms=duration_ms,
        )
        text = json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
        return [TextContent(type="text", text=text)]

    return server


async def _dispatch(
    name: str,
    arguments: dict,
    structural: StructuralQueryEngine,
    semantic: SemanticQueryEngine,
    hybrid: HybridQueryEngine,
    graph_engine: GraphQueryEngine,
) -> dict | list | str:
    if name == "code_find_symbol":
        return structural.find(
            name=arguments.get("name"),
            kind=arguments.get("kind"),
            limit=arguments.get("limit", 100),
        )

    if name == "code_hierarchy":
        class_name = arguments.get("class_name")
        if not class_name:
            return _missing_argument(name, "class_name")
        return structural.hierarchy(class_name)

    if name == "code_dependencies":
        module = arguments.get("module")
        if not module:
            return _missing_argument(name, "module")
        return structural.deps(module)

    if name == "code_usages":
        symbol = arguments.get("symbol")
        if not symbol:
            return _missing_argument(name, "symbol")
        return structural.usages(
            symbol,
            limit=arguments.get("limit", 100),
        )

    if name == "code_outline":
        file_path = arguments.get("file_path")
        if not file_path:
            return _missing_argument(name, "file_path")
        return structural.outline(file_path)

    if name == "code_ask":
        question = arguments.get("question")
        if not question:
            return _missing_argument(name, "question")
        return await _safe_semantic_call(semantic.ask(question))

    if name == "code_explain":
        symbol_name = arguments.get("symbol")
        if not symbol_name:
            return _missing_argument(name, "symbol")
        found = structural.find(name=symbol_name)
        structural_info = found[0] if found else None
        return await _safe_semantic_call(
            semantic.explain(symbol_name, structural_info)
        )

    if name == "code_impact":
        symbol = arguments.get("symbol")
        if not symbol:
            return _missing_argument(name, "symbol")
        return await _safe_semantic_call(
            hybrid.impact(
                symbol,
                token_budget=arguments.get("token_budget", 8000),
            )
        )

    if name == "code_review_diff":
        diff = arguments.get("diff")
        if not diff:
            return _missing_argument(name, "diff")
        return await _safe_semantic_call(semantic.review_diff(diff))

    if name == "code_map":
        return graph_engine.repo_map(
            focus_files=arguments.get("focus_files"),
            token_budget=arguments.get("token_budget", 4000),
        )

    if name == "code_hotspots":
        return graph_engine.hotspots(limit=arguments.get("limit", 10))

    if name == "code_architecture":
        return graph_engine.architecture(fmt=arguments.get("format", "mermaid"))

    if name == "code_search":
        query = arguments.get("query")
        if not query:
            return _missing_argument(name, "query")
        return await _safe_semantic_call(
            semantic.search_fast(query, top_k=arguments.get("top_k", 10))
        )

    if name == "code_reason":
        question = arguments.get("question")
        if not question:
            return _missing_argument(name, "question")
        return await _safe_semantic_call(semantic.reason(question))

    return {
        "error": f"Unknown tool: {name}",
        "available_tools": TOOL_NAMES,
    }


async def run_server(config: CodeBrainConfig, port: int | None = None) -> None:
    server = create_server(config)
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)
