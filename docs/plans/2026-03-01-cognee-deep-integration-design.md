# Unified Code Knowledge Graph — Deep Cognee Integration

**Philosophy:** ast-index is the eyes, cognee is the brain. Together they form a complete code intelligence system. Cognee is not optional — it's a first-class partner.

---

## 1. Custom Code Graph Models

Extend cognee's `DataPoint` with code-specific models that carry structural metadata AND enable LLM enrichment:

```python
class CodeFunction(DataPoint):
    name: str
    signature: str
    file_path: str
    line: int
    module: str
    parameters: list[str]
    return_type: str
    docstring: str
    body_summary: str          # first ~500 chars for LLM context
    purpose: str = ""          # populated by cognify
    complexity: str = ""       # simple/moderate/complex
    metadata: dict = {"index_fields": ["name", "signature", "purpose"]}

class CodeClass(DataPoint):
    name: str
    file_path: str
    line: int
    parents: list[str]
    methods: list[str]
    docstring: str
    purpose: str = ""
    architectural_role: str = ""  # controller, service, model, utility
    metadata: dict = {"index_fields": ["name", "purpose", "architectural_role"]}

class CodeModule(DataPoint):
    name: str
    path: str
    imports: list[str]
    exports: list[str]
    description: str = ""
    domain: str = ""             # auth, payments, api, storage
    metadata: dict = {"index_fields": ["name", "description", "domain"]}
```

---

## 2. Ingestion Pipeline

**Step 1** — ast-index reads structure (symbols, deps, usages, inheritance)
**Step 2** — Transform to CodeFunction / CodeClass / CodeModule instances, reading source bodies from actual files
**Step 3** — Batch feed to cognee:
  - `cognee.add(all_symbols, dataset_name="code_symbols")`
  - `cognee.add(all_relationships, dataset_name="code_relationships")`
  - `cognee.cognify()` — ONE call, LLM extracts purpose/intent/domain/roles
**Step 4** — Enrich:
  - `cognee.memify()` — consolidate descriptions, create triplet embeddings
**Step 5** — Build unified NetworkX graph merging:
  - AST structural edges (imports, calls, inherits)
  - Cognee semantic edges (relates_to, implements_concept)
  - Git history edges (co-changed)
  - PageRank on the unified graph → save graph.pkl

---

## 3. Search & MCP Tools (14 total)

### Structural tier (5 tools, instant, no backend needed)

| Tool | Source |
|------|--------|
| `code_find_symbol` | ast-index |
| `code_hierarchy` | ast-index |
| `code_usages` | ast-index |
| `code_outline` | ast-index |
| `code_dependencies` | ast-index |

### Semantic tier (9 tools, cognee-powered)

| Tool | Cognee Search Type | Description |
|------|-------------------|-------------|
| `code_ask` | GRAPH_COMPLETION | Natural language Q&A with code graph context |
| `code_explain` | GRAPH_SUMMARY_COMPLETION | Explain with pre-computed summaries + structural context |
| `code_impact` | Structural + GRAPH_COMPLETION | Structural dependents + semantic business impact |
| `code_review_diff` | CODING_RULES | Check diff against coding patterns in graph |
| `code_map` | Unified PageRank | Structural + semantic graph centrality |
| `code_hotspots` | Git + graph centrality | Change frequency + semantic importance |
| `code_architecture` | Module deps + cognee domains | Architecture diagram enriched with domain labels |
| `code_search` (NEW) | CHUNKS | Fast vector similarity, no LLM call |
| `code_reason` (NEW) | GRAPH_COMPLETION_COT | Chain-of-thought reasoning for complex questions |

---

## 4. Error Handling / Graceful Degradation

Every cognee-powered tool:
1. Checks if cognee backends are reachable
2. If not: returns helpful message ("Run: code-brain up && code-brain ingest")
3. If structural data available: falls back to structural-only results with a note

Example: `code_impact` returns just structural dependents when cognee is down, full semantic analysis when it's up.

---

## 5. CLI `ingest` Command

```
code-brain ingest
  ├── Auto-run ast-index rebuild (if DB missing)
  ├── Read structural data from ast-index
  ├── Transform symbols → CodeFunction/CodeClass/CodeModule
  ├── cognee.add() in batches
  ├── cognee.cognify() — LLM enrichment
  ├── cognee.memify() — graph enrichment
  ├── Build unified NetworkX graph (structural + semantic)
  └── Save graph.pkl

code-brain ingest --structural-only
  └── Skip cognee, build graph from ast-index + git only
```

`--structural-only` replaces `--skip-semantic` (positive framing).
