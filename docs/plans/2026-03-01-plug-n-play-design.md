# Plug-n-Play UX Improvements Design

**Goal:** Make code-brain work seamlessly from first install to first query — fix critical bugs and remove friction from the first-time experience.

**Scope:** Critical bugs + first-time flow. No new features, no UX polish beyond what's broken.

---

## 1. Fix `find` command — positional name argument

**Problem:** README shows `code-brain find UserService` but CLI requires `--name UserService`. First command users try from the README fails.

**Fix:** Add optional positional argument for name, keeping `--name` as alias. Matches the pattern used by `usages`, `hierarchy`, `deps`, `outline`.

## 2. Fix `serve` command — broken import

**Problem:** `cli.py` imports `serve` from `mcp_server` but the function is named `run_server`. Also passes `host`/`port` but `run_server` expects `config`/`port`.

**Fix:** Fix import to use `run_server`, pass `CodeBrainConfig` instead of host. MCP uses stdio transport so `host` param is misleading — simplify to `--project` only.

## 3. Fix `outline` path normalization

**Problem:** ast-index stores relative paths (e.g., `src/models/user.py`) but users may pass `./src/models/user.py` or absolute paths. Only exact matches work.

**Fix:** Normalize user input before querying:
- Strip leading `./`
- If absolute, strip project root prefix
- If no results on exact match, try suffix matching

## 4. Auto `ast-index rebuild` during `ingest`

**Problem:** Users must manually install and run ast-index before `code-brain ingest`. No guidance when ast-index is missing.

**Fix:** During `ingest`, if no ast-index DB found:
- Locate binary via `_find_ast_index_bin()`
- Run `ast-index rebuild` as subprocess
- If binary not found, show installation instructions and exit
- Add `--rebuild` flag to force re-index even when DB exists

## 5. Add `doctor` command

**Problem:** No way to diagnose what's working and what's not. Users hit cryptic errors from missing dependencies.

**Fix:** `code-brain doctor` checks and reports status of:
- ast-index binary (installed / not found + install instructions)
- ast-index DB (found with symbol count / not found)
- Graph pickle (found with node count / not found)
- Docker (available / not found)
- Neo4j (reachable / not reachable)
- Qdrant (reachable / not reachable)

## 6. Fix README mismatches

- `--tokens` → `--budget` in map example
- Update `find` examples to match actual CLI
- Add `doctor` command to usage section

## 7. Better error messages

- ast-index missing: install instructions with `cargo install` command
- Docker missing: mention `--skip-semantic` flag
- Graph missing: mention `code-brain ingest`
