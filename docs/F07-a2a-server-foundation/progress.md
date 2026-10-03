# Implementation Progress: A2A Server Foundation

**Status:** in progress
**Branch:** feat/a2a-agent-and-mcp-server-implementation
**Started:** 2026-10-03
**Last updated:** 2026-10-03

## Stage 1: Project Scaffold — ✅ done

- [x] **1. Project Manifest**
- [x] **2. Dependency Surface Confirmation**
- [x] **3. Package Skeleton, Messages and Identifiers**

**Observations:**
- Verified spec V1–V4 in the shared repo-root `.venv` (Python 3.14.4): V1 `Route(methods=["GET"])` answers GET and HEAD with 200, POST 405; V2 `agente.__file__` resolves to `agente/src/agente` both from the repo root and from an unrelated cwd (default editable install is fine, no `editable_mode=compat` needed); V3 `httpx.ASGITransport` serves concurrent requests; V4 `pip check` clean with `mcp 2.3.0`, `starlette 1.7.0`, `uvicorn 0.54.0`.
- `.gitignore` already ignores `*.egg-info/` and `.pytest_cache/` (added by F01); nothing to change.
- No lint/typecheck tooling is declared by the spec or manifests; none run.

**Validation:** `pip install -e "./agente[dev]"` ✅ · `pip check` ✅ · imports ✅
**Commit:** 246c8a9 feat(F07): project scaffold and dependency baseline

## Stage 2: A2A Data Model and Task Lifecycle — ✅ done

- [x] **4. A2A Data Model and Wire Serialization**
- [x] **5. Task State Machine**
- [x] **6. In-Memory Task Store**

**Observations:**
- `TaskStore.handle()` builds a `TaskHandle` that caches `context_id` (raises `TaskNotFoundError` for unknown ids). `TaskStore` also exposes `context_id_of`, an addition beyond the spec's list.
- Terminal Tasks raise `TaskImmutableError` from every handle write (checked before the transition table); `InvalidTransitionError` is raised for table violations and for `INPUT_REQUIRED -> WORKING` without a continuation claim.
- `settle` only fails `SUBMITTED`/`WORKING`; a paused (`INPUT_REQUIRED`) or terminal Task is left alone.
- Handles use `__slots__` and a `repr` without attachment content.
- `tests/conftest.py` currently holds `repo_root`, `wire`, `fixed_ids`, `free_port`; the app-level fixtures (`make_client`, `a2a_post`, `send`, `scripted`, `recording`, `start_agent`, `start_mcp_server`) are added in stage 3/4 when the modules they import exist.

**Validation:** lint n/a · typecheck n/a · tests 92/92 ✅ (ids, protocol, lifecycle, task_store)
**Commit:** 1cd863d feat(F07): A2A data model, state machine and task store

## Stage 3: JSON-RPC Endpoint and Extension Points — ✅ done

- [x] **7. JSON-RPC Envelope and Errors**
- [x] **8. Request Parameters**
- [x] **9. Extension Points and Stub Handlers**
- [x] **10. Method Dispatcher**
- [x] **11. Agent Card**
- [x] **12. Request Log and Application Assembly**

**Observations:**
- **Deviation (ordering):** `config.py` (plan step 13, stage 4) was written in this stage because `skills.build_handlers(settings)` and `build_app` take `Settings`. Its unit tests are in this commit; stage 4 only adds the socket and entry point.
- `parse_envelope` raises `EnvelopeError` (a `JsonRpcError` subclass carrying `rpc_id` and `method`) so the dispatcher can echo a valid id and log the method even when the envelope is invalid. Not in the spec's list; internal detail.
- Handler-failure diagnostics (exception type and frames, never the message) are written to the same stream as the request log (`log_stream`, `sys.stderr` in production), so tests can assert on them. An exception raised while the Task is paused (`INPUT_REQUIRED`) also fails the Task (`INPUT_REQUIRED -> FAILED`).
- `RequestLogger` / `Dispatcher` resolve `sys.stderr` at write time (`log_stream=None`) instead of binding it at import.
- Params detail for a non-object `params.message` is `params.message deve ser um objeto` (spec only listed the `ausente` case).
- Part handling: a part with a string `text` is a text part even if it also carries `raw`/`url`/`data`; a part with only those → `-32005`.
- Wire-fidelity tests reproduce wire 07–10 byte for byte (`json.dumps` comparison, key order included) through scripted handlers and fixed ids.
- Test helpers added to `conftest.py`: `Scripted` (steps: transition, artifact, append, attach, raise, wait, set, call), `Recorder`, `make_client`, `a2a_post`, `send`. `start_agent` / `start_mcp_server` come with stage 4.
- `test_routing_and_concurrency.py` builds its handlers' `asyncio.Event`s inside the running loop.

**Validation:** lint n/a · typecheck n/a · tests 212/212 ✅ (full `agente/` suite at this point)
**Commit:** _(pending)_
