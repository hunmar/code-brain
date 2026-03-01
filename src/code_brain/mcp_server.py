"""MCP server exposing code-brain tools for code intelligence."""
from __future__ import annotations

import json
import pickle
from pathlib import Path

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
        description="Ask a natural language question about the codebase.",
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
        description="Get an explanation of a symbol including its context and purpose.",
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
        description="Analyze the impact of changing a symbol: dependents, risk level, change frequency.",
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
        description="Review a diff for potential issues using semantic analysis.",
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
]


def _load_graph(config: CodeBrainConfig) -> nx.DiGraph:
    if config.graph_path.is_file():
        return GraphBuilder().load(config.graph_path)
    return nx.DiGraph()


def create_server(config: CodeBrainConfig) -> Server:
    server = Server("code-brain")

    reader = ASTIndexReader(config.project_root)
    adapter = CogneeAdapter()
    graph = _load_graph(config)

    structural = StructuralQueryEngine(reader)
    semantic = SemanticQueryEngine(adapter)
    hybrid = HybridQueryEngine(structural, semantic, graph)
    graph_engine = GraphQueryEngine(graph)

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
        result = await _dispatch(
            name, arguments, structural, semantic, hybrid, graph_engine,
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
        return structural.hierarchy(arguments["class_name"])

    if name == "code_dependencies":
        return structural.deps(arguments["module"])

    if name == "code_usages":
        return structural.usages(
            arguments["symbol"],
            limit=arguments.get("limit", 100),
        )

    if name == "code_outline":
        return structural.outline(arguments["file_path"])

    if name == "code_ask":
        return await semantic.ask(arguments["question"])

    if name == "code_explain":
        symbol_name = arguments["symbol"]
        found = structural.find(symbol_name)
        structural_info = found[0] if found else None
        return await semantic.explain(symbol_name, structural_info)

    if name == "code_impact":
        return await hybrid.impact(
            arguments["symbol"],
            token_budget=arguments.get("token_budget", 8000),
        )

    if name == "code_review_diff":
        return await semantic.ask(
            f"Review the following diff for potential issues:\n\n{arguments['diff']}"
        )

    if name == "code_map":
        return graph_engine.repo_map(
            focus_files=arguments.get("focus_files"),
            token_budget=arguments.get("token_budget", 4000),
        )

    if name == "code_hotspots":
        return graph_engine.hotspots(limit=arguments.get("limit", 10))

    if name == "code_architecture":
        return graph_engine.architecture(fmt=arguments.get("format", "mermaid"))

    return {"error": f"Unknown tool: {name}"}


async def run_server(config: CodeBrainConfig, port: int | None = None) -> None:
    server = create_server(config)
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)
