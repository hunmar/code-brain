# Deep Cognee Integration Implementation Plan (Reviewed + Enhanced)

**Date:** 2026-03-01  
**Scope:** `code-brain` deep semantic integration with cognee as a first-class runtime dependency.

## 1. Review Summary

The original draft had strong intent but several execution risks. This revised plan addresses them directly:

1. `DataPoint` model examples used mutable defaults (`[]`, `{}`), which can leak state across instances.
2. Adapter tests patched `cognee.add` directly, but runtime imports use module-scoped `code_brain.ingestion.cognee_adapter.cognee`; patch targets should match actual call sites.
3. "Structured ingestion" converted models back into plain text strings; this weakens schema benefits and makes behavior harder to validate.
4. Search type mapping assumed one enum representation (`value`) and could break if `SearchType` uses a different format (`name` or mixed-case values).
5. Graceful degradation design did not define typed errors, fallback boundaries, or which tools may safely degrade.
6. Test strategy lacked integration gates for backend-down behavior and for one-shot `cognify`/`memify` execution.
7. Rollout instructions mixed implementation and release actions (`git push`) in the plan; this version separates engineering completion from release decisions.

## 2. Enhanced Core Idea

The core idea is upgraded from "semantic add-on" to an **evidence-backed intelligence loop**:

1. **Structural truth layer (ast-index):** exact symbol/file/line relationships remain the source of factual grounding.
2. **Semantic meaning layer (cognee):** purpose, intent, architectural role, and concept-level relationships are inferred and enriched.
3. **Unified answer contract:** semantic answers should include structural anchors and confidence, not only free-form prose.
4. **Staged retrieval policy:** start with lower-cost retrieval (`CHUNKS` or summary modes), then escalate to heavier reasoning (`GRAPH_COMPLETION_COT`) only when needed.
5. **Resilience by design:** when semantic systems fail, return structural evidence with explicit degraded status.

### Semantic Response Contract

Semantic endpoints should return a stable shape where possible:

```json
{
  "answer": "short synthesized answer",
  "evidence": [
    {"symbol": "AuthService", "file_path": "src/auth/service.py", "line": 42}
  ],
  "confidence": "low|medium|high",
  "degraded": false,
  "warnings": []
}
```

This lets CLI/MCP consumers reason about trust and fallback quality.

## 3. Goals, Non-Goals, and Success Criteria

### Goals

1. Make cognee integration schema-driven (code models) and batch-oriented.
2. Expand semantic functionality from 12 to 14 MCP tools (`code_search`, `code_reason`).
3. Map semantic APIs to explicit cognee search types.
4. Add graceful degradation when semantic backends are unavailable.
5. Keep structural workflows fully operational when semantic layer is down.
6. Ensure semantic outputs are evidence-backed and confidence-scored.

### Non-Goals

1. Replacing ast-index or the NetworkX graph model.
2. Introducing distributed ingestion workers.
3. Reworking CLI UX outside semantic-related commands.

### Success Criteria

1. Unit and integration tests pass for new behavior.
2. `code-brain ingest` performs one semantic finalization cycle (`cognify`, optional `memify`) per run.
3. MCP reports 14 tools and new tools are callable.
4. Semantic tool failures return actionable responses without crashing server process.
5. README and command help reflect new semantics (`--structural-only`, new tools/commands).
6. `code_ask`, `code_reason`, and `code_explain` provide evidence anchors in output or explicit degraded warnings.

## 4. Preconditions and Constraints

1. Python requirement remains `>=3.11` (per current `pyproject.toml`).
2. Confirm cognee API compatibility before coding:
   - `cognee.add(...)`
   - `cognee.cognify()`
   - `cognee.memify()`
   - `cognee.search(query_text=..., query_type=..., top_k=...)`
3. Docker-backed services (Neo4j/Qdrant) are required for semantic integration tests.
4. Structural features must remain available when semantic dependencies are missing or unreachable.

## 5. Implementation Strategy (Phased)

### Phase 0: Contract Check and Baseline

**Files:**
- `src/code_brain/ingestion/cognee_adapter.py`
- `tests/unit/test_cognee_adapter.py`

**Actions:**
1. Add focused tests that lock expected call contracts for add/cognify/memify/search.
2. Introduce a single helper for search type resolution that supports enum names and values.
3. Define error taxonomy in adapter layer (`semantic_unavailable`, `semantic_query_failed`, `semantic_validation_failed`).

**Exit Criteria:**
1. Adapter tests fail with current implementation for the right reasons (missing features).
2. API contract is documented in test names and assertions.

---

### Phase 1: Introduce Code-Specific Data Models

**Files:**
- Create: `src/code_brain/models.py`
- Create/Modify: `tests/unit/test_models.py`

**Actions:**
1. Add `CodeFunction`, `CodeClass`, `CodeModule` extending cognee `DataPoint`.
2. Use `Field(default_factory=...)` for lists/dicts to avoid shared mutable state.
3. Include explicit index metadata fields for semantic retrieval tuning.

**Model Requirements:**
1. `CodeFunction`: name, signature, location, parameters, return type, purpose hints.
2. `CodeClass`: name, location, parents, methods, architectural role hints.
3. `CodeModule`: module identity, import/export boundaries, domain hint.

**Exit Criteria:**
1. Model construction tests pass.
2. No mutable-default lint/test regressions.

---

### Phase 2: Rebuild `CogneeAdapter` for Batched Structured Ingestion

**Files:**
- Modify: `src/code_brain/ingestion/cognee_adapter.py`
- Modify: `tests/unit/test_cognee_adapter.py`

**Actions:**
1. Convert symbols/deps/docs into typed model payloads before ingestion.
2. Batch `add` calls by dataset category (`code_symbols`, `code_relationships`, `documentation`).
3. Move `cognify` and `memify` out of per-ingest methods into `finalize()`.
4. Add `finalize(run_memify: bool = True)` and make memify non-fatal.
5. Implement `search(query, search_type, top_k)` with robust search type normalization.

**Testing Requirements:**
1. `ingest_symbols` does not call `cognify` directly.
2. `finalize()` calls `cognify` exactly once.
3. `memify` failures are captured and surfaced as warning context, not fatal crashes.
4. Search uses resolved `query_type` and passes `top_k`.

**Exit Criteria:**
1. Adapter unit tests pass.
2. No semantic calls are executed in per-item loops.

---

### Phase 3: Expand Semantic Query Engine with Explicit Search Modes

**Files:**
- Modify: `src/code_brain/query/semantic.py`
- Modify: `tests/unit/test_semantic_queries.py`

**Actions:**
1. Map methods to search types:
   - `ask` -> `GRAPH_COMPLETION`
   - `explain` -> `GRAPH_SUMMARY_COMPLETION`
   - `search_fast` -> `CHUNKS`
   - `reason` -> `GRAPH_COMPLETION_COT`
   - `review_diff` -> `CODING_RULES`
2. Add evidence extraction hooks so semantic responses include symbol/file/line anchors when available.
3. Add confidence scoring heuristic:
   - `high`: multiple consistent structural anchors
   - `medium`: at least one direct structural anchor
   - `low`: semantic-only answer with weak/no anchor
4. Keep `explain` behavior as hybrid output (structural context + semantic context).
5. Preserve output shape consistency across methods.

**Exit Criteria:**
1. Semantic query tests verify correct `search_type` dispatch.
2. Existing `ask`/`explain` behavior remains backward compatible.
3. Evidence and confidence fields are populated or explicitly marked unavailable.

---

### Phase 4: MCP Server Hardening + Tool Expansion (14 Tools)

**Files:**
- Modify: `src/code_brain/mcp_server.py`
- Modify: `tests/unit/test_mcp_server.py`

**Actions:**
1. Add tools:
   - `code_search`
   - `code_reason`
2. Update tool descriptions to clarify semantics and expected usage.
3. Add `_safe_semantic_call(...)` wrapper with typed fallback responses.
4. Wrap semantic/hybrid calls, but keep structural calls direct.
5. Pass `project_root` to `StructuralQueryEngine` in server construction.

**Degradation Rules:**
1. If semantic backends unavailable: return actionable message (`code-brain up && code-brain ingest`).
2. If structural fallback is feasible (for hybrid endpoints), return partial results with warning field.
3. Never raise uncaught semantic exceptions from `_dispatch`.
4. Degraded semantic responses should set `degraded=true` and preserve available structural evidence.

**Exit Criteria:**
1. MCP tool count is 14.
2. New tools are discoverable via `list_tools` and executable via `call_tool`.
3. Backend-down tests verify non-crashing responses.

---

### Phase 5: CLI Integration and Migration

**Files:**
- Modify: `src/code_brain/cli.py`
- Modify: `tests/unit/test_cli.py`

**Actions:**
1. Replace `--skip-semantic` with `--structural-only`.
2. Keep backward compatibility for one release:
   - Accept legacy `--skip-semantic` as hidden alias.
   - Emit deprecation message directing users to `--structural-only`.
3. Update ingest flow:
   - ingest structural data
   - batch semantic ingestion
   - single finalize step
   - warning-only failure path for semantic layer
4. Add commands:
   - `code-brain search`
   - `code-brain reason`

**Exit Criteria:**
1. Help output shows `--structural-only`.
2. Legacy flag works with deprecation warning.
3. New semantic commands execute and format output in text/json modes.

---

### Phase 6: Documentation and Operator Guidance

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-03-01-cognee-deep-integration-design.md` (only if drift exists)

**Actions:**
1. Update MCP tool count from 12 -> 14.
2. Document `code_search` and `code_reason` usage examples.
3. Replace `--skip-semantic` references with migration note to `--structural-only`.
4. Document degraded-mode behavior and recommended recovery commands.
5. Document evidence/confidence semantics so client consumers can reason about answer trust.

**Exit Criteria:**
1. README command list and MCP list align with code.
2. No stale flag/tool references remain.

---

### Phase 7: Validation, Rollout, and Sign-Off

**Validation Suite:**
1. `uv run pytest tests/unit -v`
2. `uv run pytest tests/integration -v` (semantic tests gated by backend availability)
3. `uv run pytest -v`
4. Manual smoke checks:
   - `code-brain ingest --structural-only`
   - `code-brain ingest`
   - `code-brain ask "..."`
   - `code-brain search "..."`
   - `code-brain reason "..."`
   - MCP `code_search`, `code_reason` calls
   - verify `evidence`, `confidence`, and `degraded` fields on semantic outputs

**Sign-Off Criteria:**
1. All required tests pass.
2. Backward compatibility behavior is verified.
3. Error messages are actionable and non-ambiguous.
4. Evidence and degraded-mode semantics are stable and documented.

## 6. Test Matrix

| Area | Unit | Integration | Manual |
|---|---|---|---|
| Models | `test_models.py` | n/a | instantiate sample models |
| Adapter batching/finalize | `test_cognee_adapter.py` | semantic ingest tests | run ingest with/without backends |
| Semantic query routing | `test_semantic_queries.py` | semantic search tests | ask/search/reason CLI |
| Evidence contract | semantic + MCP shape tests | backend-up/down parity checks | inspect `evidence`, `confidence`, `degraded` fields |
| MCP tool surface | `test_mcp_server.py` | MCP call tests | list/call tools in client |
| CLI migration | `test_cli.py` | end-to-end ingest | help + legacy flag checks |

## 7. Risks and Mitigations

1. **Cognee API drift**
   - Mitigation: lock expected adapter contract in tests before refactor.
2. **Performance regression during ingest**
   - Mitigation: require batched add behavior; track add-call counts in tests.
3. **Semantic instability blocks all queries**
   - Mitigation: strict separation of structural vs semantic failure paths.
4. **CLI breaking change from flag rename**
   - Mitigation: one-release compatibility alias + warning.
5. **Inconsistent tool metadata vs dispatch behavior**
   - Mitigation: tool list and dispatch assertions in MCP tests.
6. **Low-trust semantic output**
   - Mitigation: enforce evidence/confidence contract and degrade explicitly when anchors are missing.

## 8. Rollback Plan

If post-merge semantic regressions occur:

1. Run structural-only ingest path (`code-brain ingest --structural-only`).
2. Disable semantic calls at MCP layer by routing semantic endpoints to degraded responses.
3. Revert adapter/search-type changes only, keeping structural and graph functionality active.
4. Keep docs updated with temporary degraded-mode notice until semantic fix is released.

## 9. Deliverables Checklist

1. `src/code_brain/models.py` added with tested schema models.
2. `CogneeAdapter` supports batched structured ingest, finalize, and typed search.
3. `SemanticQueryEngine` includes `search_fast`, `reason`, `review_diff`, explicit search-type mapping, and evidence/confidence output.
4. MCP server exposes 14 tools with graceful semantic error handling.
5. CLI supports `search`, `reason`, and `--structural-only` migration path.
6. README updated for 14-tool surface and revised ingest flow.
7. Unit + integration + smoke validation completed.
