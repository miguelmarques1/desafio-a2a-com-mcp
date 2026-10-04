# Implementation Progress: Agent MCP Host Client

**Status:** success
**Branch:** feat/a2a-agent-and-mcp-server-implementation
**Started:** 2026-10-03
**Last updated:** 2026-10-03

## Stage 1: Configuration and Dependency — ✅ done

- [x] **1. Runtime HTTP Client Dependency**
- [x] **2. Dependency and Wire Confirmation**
- [x] **3. MCP URL Setting and Messages**

**Observations:**
- Verified V1 (`ConnectError`, `ReadTimeout`, `ConnectTimeout`, `RemoteProtocolError` are `httpx.TransportError` subclasses), V2 (`AsyncClient(trust_env=False, follow_redirects=False, timeout=Timeout(10.0))`, `MockTransport`) and V5 (`httpx 0.28.1` already in the shared venv, no conflict) against the installed package. V3 (real server answers `Host: localhost:<port>` without 421, no `-32602`/`-32020`) is covered by `test_no_request_is_rejected_by_the_ladder`. V4 (Windows `localhost` → `::1` delay) was not measured separately: the integration tests use `localhost` and finish well inside the limit.
- `Settings.mcp_url` is the last field with a default, so existing three-field construction keeps working. `MCP_URL` is kept verbatim (trailing slash preserved), unlike `AGENT_PUBLIC_URL`.
- No lint/typecheck tooling is declared in either manifest; none run.

**Validation:** lint n/a · typecheck n/a · config tests ✅
**Commit:** see git log (`feat(F06): runtime dependency, MCP_URL setting and failure messages`)

## Stage 2: Protocol Building Blocks — ✅ done

- [x] **4. Trace Context**
- [x] **5. Request Envelope and Headers**
- [x] **6. Response Decoding**
- [x] **7. Outcome Model and Normalization**

**Observations:**
- Response-id matching (A13) lives in `wire.decode_response`: a `result` must carry the request id, an `error` may carry it or `null`; anything else decodes to `None` → `Resposta inesperada do servidor MCP`.
- `error_failure` strips the message itself (`Erro do servidor MCP: -32602 bad` for `" bad "`).
- `TraceContext._parent_id` is `compare=False, repr=False` so it never affects equality of stored traces.

**Validation:** lint n/a · typecheck n/a · unit tests ✅ (see final run)
**Commit:** see Stage 3 (stages 2–4 share one commit, see Deviations in Stage 3)

## Stage 3: MCP Client and Per-Task Context — ✅ done

- [x] **8. MCP Client Core**
- [x] **9. Discovery and Policy Read**
- [x] **10. Tool Call and Retry Invocation**
- [x] **11. Per-Task Context Opener**

**Observations:**
- **Deviation (commits):** stages 2–4 were written and validated together and committed as one commit. The package `__init__` re-exports from every module and the tests import through it, so intermediate per-stage commits would not have been independently green.
- Server's `reservar_sala` on the working tree is F04 only: a conflict returns `CompleteError("Sala ocupada no intervalo: sala-garagem")`, not `input_required` (that is F05). The four pause/retry integration tests therefore skip through the `reserving_server` fixture, which probes the conflict once and skips unless it yields `InputRequired`. Run them again once F05 lands.
- Client-side import note: `tests/` use `--import-mode=importlib`, so shared test helpers cannot be imported from `conftest`; `json_answer` is defined locally in the two test modules that need it.
- `read_resource` returns `""` when no entry has text; `open_task_context` maps that to `Politica de uso sem versao declarada`.

**Validation:** lint n/a · typecheck n/a · `pytest agente` 350 passed / 20 skipped ✅
**Commit:** see Stage 4

## Stage 4: Composition — ✅ done

- [x] **12. Client Lifecycle in the Registration Hook**
- [x] **13. Public Surface and Consumer Contract**

**Observations:**
- `build_handlers` builds one `McpClient(settings.mcp_url)` and registers `client.aclose` in `Handlers.aclose`; the stub handlers stay. `app.py` already awaits `aclose` on shutdown.
- `test_agent_starts_without_mcp_server` checks the agent prints only its three banner lines (no MCP traffic or extra stderr at startup).
- The Task-level tests in `test_cross_feature_f06.py` skip while F08 (new Tasks) / F09 (continuations) are stubs. They are written but have not run against a real consumer.

**Validation:** lint n/a · typecheck n/a · `pytest agente` 350 passed / 20 skipped ✅
**Commit:** `feat(F06): MCP host client, per-Task context and registration hook`

## Final verification

- Full suite (`python -m pytest agente`): 350 passed, 20 skipped, 0 failed.
- Component Overview walk-through: every listed file exists (`pyproject.toml`, `config.py`, `mensagens.py`, `mcp_host/{__init__,trace_context,wire,outcomes,client,task_context}.py`, `skills/__init__.py`); `__main__.py` needs no change.
- Soft-fails: 12 Task-level tests in `test_cross_feature_f06.py` (F08/F09 not registered), 3 in `test_cross_feature_f07.py` (pre-existing gating), 4 pause/retry integration tests (F05 not on the server).
- Open follow-up: re-run the 16 gated F06 tests once F05, F08 and F09 land.
