# Implementation Progress: MRTR Conflict Resolution

**Status:** in progress
**Branch:** feat/a2a-agent-and-mcp-server-implementation
**Started:** 2026-10-04
**Last updated:** 2026-10-04

## Stage 1: Request-State Security and Startup — ✅ done

- [x] **1. MRTR Messages** (F05 block appended; deletion of `SALA_OCUPADA` deferred to step 10, see observations)
- [x] **2. Secret Validation and Security Policy**
- [x] **3. Startup Wiring**

**Observations:**
- `mensagens.SALA_OCUPADA` is deliberately kept until Stage 3 (step 10): `_responder_conflito` still reads it and the interim conflict test still passes through it. Deleting it here would break a green commit.
- `SegredoInvalidoError` takes no arguments and builds its own message from `mensagens.SEGREDO_INVALIDO`.
- Startup process tests (`test_mrtr_process.py`) were added now for the secret check; the restart/log/grep tests of the spec arrive with Stage 3.

**Validation:** lint — no tooling declared (soft-fail) · typecheck — none declared (soft-fail) · tests 339 passed, 7 skipped ✅ (full suite; +17 new)
**Commit:** feat(F05): request-state security and startup

## Stage 2: Conflict Domain — ✅ done

- [x] **4. Alternatives Rule**
- [x] **5. Sealed Request Payload**

**Observations:**
- `EstadoDoPedido` declares the four constant fields (`v`, `ferramenta`, `chave`) with defaults after the required ones; `codificar` writes the A6 key order explicitly, so field order in the dataclass is irrelevant to the wire.
- `decodificar` rejects booleans for `v` and `expira` (`bool` is an `int` in Python) and non-string input (returns `None`, never raises).
- Extra tests beyond the spec list: spec-example byte-for-byte encoding, non-string input, bool rejection.

**Validation:** lint — no tooling (soft-fail) · typecheck — none (soft-fail) · tests 374 passed, 7 skipped ✅ (full suite; +35 new)
**Commit:** feat(F05): alternatives rule and sealed payload

## Stage 3: MRTR Tool Flow — ⬜ pending

- [ ] **6. Round Protocol Helpers**
- [ ] **7. Tool Signature Widening**
- [ ] **8. First-Round Conflict Resolution**
- [ ] **9. Retry Handling**
- [ ] **10. Interim Leftovers Removal**

**Observations:** _(none yet)_

**Validation:** _(not run)_
**Commit:** _(none)_
