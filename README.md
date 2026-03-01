# Code Brain

Unified code intelligence for LLM agents. Combines structural AST indexing ([ast-index](https://github.com/nickarash/ast-index)) with semantic knowledge graphs ([cognee](https://github.com/topoteretes/cognee)) and git history analysis into a single tool that Claude and other LLM agents can use to deeply understand large codebases.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Interfaces Layer                      │
│   CLI (code-brain)  │  MCP Server  │  Python API        │
└──────────┬──────────┴──────┬───────┴────────┬───────────┘
           │                 │                │
┌──────────▼─────────────────▼────────────────▼───────────┐
│                    Query Engine                          │
│   Query Router  │  PageRank Scorer  │  Context Budgeter  │
└────────┬────────┴────────┬──────────┴─────────┬─────────┘
         │                 │                    │
┌────────▼─────────────────▼────────────────────▼─────────┐
│               Unified Graph (NetworkX)                   │
│   AST nodes ←──→ Semantic nodes ←──→ Git history         │
│                                                          │
│   Structural Index        Semantic Store                 │
│   (ast-index SQLite)      (cognee: Neo4j + Qdrant)       │
└────────┬──────────────────────────────────┬──────────────┘
         │                                  │
┌────────▼──────────────────────────────────▼──────────────┐
│                  Ingestion Pipeline                       │
│   ast-index rebuild  │  cognee pipeline  │  git analysis  │
└──────────────────────────────────────────────────────────┘
```

## Features

- **Structural search** — find symbols, class hierarchies, dependencies, usages via AST index
- **Semantic search** — ask natural language questions about the codebase via cognee
- **Unified graph** — merged knowledge graph with PageRank-based relevance scoring
- **Impact analysis** — analyze ripple effects of changing a symbol
- **Dead code detection** — find unused symbols across the codebase
- **Repo map** — PageRank-ranked overview of the most important code, fitted to a token budget
- **Hot spots** — identify frequently-changed areas from git history
- **Architecture diagrams** — auto-generated module dependency diagrams (Mermaid or text)
- **MCP server** — 14 tools for Claude and other LLM agents
- **Local dashboard** — visualize MCP tool calls, latency, and errors in real time
- **Token budgeting** — compact/medium/full output depth based on context window limits

## Quick Start

Get structural queries working in under a minute:

```bash
# Install
pip install code-brain  # or: uv add code-brain

# Index your project
cd /your/project
ast-index rebuild       # or: code-brain ingest (auto-runs ast-index)

# Query
code-brain find UserService
code-brain outline src/main.py
code-brain doctor                  # Check what's working
```

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [ast-index](https://github.com/nickarash/ast-index) CLI installed
- Docker (for Neo4j + Qdrant — only needed for semantic queries)

### Installation

```bash
git clone https://github.com/hunmar/code-brain.git
cd code-brain
uv sync
```

### Usage

```bash
# Initialize for a project
code-brain init /path/to/your/project

# Start backend services
code-brain up

# Index the codebase
code-brain ingest

# Search for symbols
code-brain find UserService
code-brain find UserService --kind class

# Explore code structure
code-brain hierarchy AdminUser
code-brain usages AuthService
code-brain deps services
code-brain outline src/models/user.py

# Semantic queries (requires cognee backends running)
code-brain ask "How does authentication work?"
code-brain search "authentication middleware"
code-brain reason "Why does payments depend on auth?"

# Graph-powered analysis
code-brain map                    # PageRank-ranked repo overview
code-brain map --budget 8000      # Larger context budget
code-brain hotspots               # Frequently-changed code
code-brain arch                   # Module dependency diagram (Mermaid)
code-brain arch --format text     # Plain text diagram

# Impact analysis
code-brain impact User            # What breaks if User changes?

# Diagnose setup
code-brain doctor                  # Check what's installed and working

# Start MCP server for Claude
code-brain serve

# Visualize MCP tool activity
code-brain dashboard
```

## MCP Server

Code Brain exposes 14 tools via the [Model Context Protocol](https://modelcontextprotocol.io):

| Tool | Description |
|------|-------------|
| `code_find_symbol` | Find a class, function, or variable by name |
| `code_hierarchy` | Get inheritance tree for a class/interface |
| `code_dependencies` | Get module dependencies |
| `code_usages` | Find all places where a symbol is used |
| `code_outline` | Get all symbols defined in a file |
| `code_ask` | Ask a natural language question about the codebase |
| `code_explain` | Get a comprehensive explanation of a code entity |
| `code_impact` | Analyze the impact of changing a symbol |
| `code_review_diff` | Review current git diff with full context |
| `code_map` | Get a PageRank-ranked overview of important symbols |
| `code_hotspots` | Find frequently-changed code areas |
| `code_architecture` | Generate an architecture diagram |
| `code_search` | Fast semantic chunk search for concept lookup |
| `code_reason` | Multi-step reasoning for complex architecture questions |

### Tool Tiers

Not all tools require the full stack. Here is what each tier needs:

| Tier | Tools | Requirements |
|------|-------|-------------|
| Structural (works immediately) | `code_find_symbol`, `code_hierarchy`, `code_usages`, `code_outline`, `code_dependencies` | Just `ast-index rebuild` |
| Graph-powered | `code_map`, `code_architecture`, `code_hotspots`, `code_impact`, `code_review_diff` | `code-brain ingest` |
| Semantic | `code_ask`, `code_explain`, `code_search`, `code_reason` | `code-brain up` + `code-brain ingest` |

### Claude Code Setup

Add a `.mcp.json` file at user scope (`~/.claude/.mcp.json`) or project scope (`.mcp.json` in the project root):

```json
{
  "mcpServers": {
    "code-brain": {
      "command": "/path/to/code-brain/.venv/bin/code-brain",
      "args": ["serve", "--project", "/path/to/your/project"]
    }
  }
}
```

### Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "code-brain": {
      "command": "code-brain",
      "args": ["serve", "--project", "/path/to/your/project"]
    }
  }
}
```

### Semantic Response Contract

Semantic tools (`code_ask`, `code_explain`, `code_search`, `code_reason`) return a consistent response shape:

```json
{
  "answer": "AuthService manages session lifecycle",
  "evidence": [
    {"symbol": "AuthService", "file_path": "services/auth.py", "line": 3}
  ],
  "confidence": "medium",
  "degraded": false,
  "warnings": []
}
```

| Field | Description |
|-------|-------------|
| `answer` | Synthesized answer text |
| `evidence` | Structural anchors (symbol, file_path, line) extracted from results |
| `confidence` | `high` (2+ anchors), `medium` (1 anchor), `low` (no anchors) |
| `degraded` | `true` when semantic backends are unavailable |
| `warnings` | Recovery hints or error details when degraded |

When backends are down, semantic tools return `degraded: true` with actionable recovery hints instead of crashing. Structural tools are unaffected.

### Structural-Only Mode

Use `--structural-only` to skip semantic ingestion (useful when backends are unavailable):

```bash
code-brain ingest --structural-only
```

## Infrastructure

Code Brain uses Docker Compose for backend services:

```bash
code-brain up    # Start Neo4j + Qdrant
code-brain down  # Stop services
```

Services:
- **Neo4j 5** (Community) — knowledge graph storage for cognee (ports 7474, 7687)
- **Qdrant** — vector database for semantic search (port 6333)

## Project Structure

```
src/code_brain/
├── cli.py                  # Typer CLI entrypoint and commands
├── config.py               # Project config with env var overrides
├── models.py               # Code data models (DataPoint subclasses for cognee)
├── mcp_server.py           # MCP server with 14 tools
├── ui_server.py            # Local MCP activity dashboard server
├── telemetry.py            # MCP event logging + metrics helpers
├── ingestion/
│   ├── ast_index.py        # Read-only SQLite reader for ast-index
│   ├── git_analyzer.py     # Git history analysis (hot spots, co-changes)
│   ├── cognee_adapter.py   # Batched cognee ingestion adapter
│   └── doc_ingester.py     # Markdown documentation finder
├── graph/
│   ├── builder.py          # Unified NetworkX graph builder
│   ├── pagerank.py         # Personalized PageRank scoring
│   └── queries.py          # Graph queries (map, hotspots, architecture)
├── query/
│   ├── router.py           # Command → query type classification
│   ├── budgeter.py         # Token budget management
│   ├── structural.py       # AST-based structural queries
│   ├── semantic.py         # cognee-powered semantic queries (evidence + confidence)
│   └── hybrid.py           # Combined analysis (impact, dead code)
└── formatters/
    ├── json_formatter.py   # JSON output
    └── text_formatter.py   # Human-readable text output
```

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
|----------|---------|-------------|
| `CODE_BRAIN_PROJECT` | auto-detect | Project root path |
| `CODE_BRAIN_NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `CODE_BRAIN_NEO4J_USER` | `neo4j` | Neo4j username |
| `CODE_BRAIN_NEO4J_PASSWORD` | `codebrain` | Neo4j password |
| `CODE_BRAIN_QDRANT_URL` | `http://localhost:6333` | Qdrant URL |

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest -v

# Run with coverage
uv run pytest --cov=code_brain

# Run specific test file
uv run pytest tests/unit/test_pagerank.py -v
```

## How It Works

1. **Ingest** — `ast-index` parses the codebase into a SQLite database with symbols, inheritance, module dependencies, and cross-references. Git history is analyzed for change frequency and co-change patterns. Everything is fed into cognee for semantic indexing.

2. **Build Graph** — A unified NetworkX DiGraph merges AST nodes, semantic relationships, and git history. Each symbol becomes a node with edges for inheritance, usage, module dependencies, and co-changes.

3. **Query** — The query router classifies commands into structural (AST), semantic (cognee), hybrid (both), or graph (NetworkX) queries. Results pass through PageRank scoring for relevance and the context budgeter for token-aware output.

4. **Serve** — The MCP server exposes all capabilities as tools that Claude and other LLM agents can call directly.

## License

MIT
