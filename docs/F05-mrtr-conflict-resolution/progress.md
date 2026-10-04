# Implementation Progress: MRTR Conflict Resolution

**Status:** success
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

## Stage 3: MRTR Tool Flow — ✅ done

- [x] **6. Round Protocol Helpers**
- [x] **7. Tool Signature Widening**
- [x] **8. First-Round Conflict Resolution**
- [x] **9. Retry Handling**
- [x] **10. Interim Leftovers Removal**

**Observations:**
- Hand-rolled MRTR as in A1; the S1 signature (`Annotated[CallToolResult, ReservaOut] | InputRequiredResult`, `ctx: Context`) keeps the `tools/list` descriptor equal to the wire capture (existing descriptor test still green).
- `_retomar` falls through to the recompute branch for both "answer outside the offer / bad content" and "chosen room taken" (decision rows 5-6), recomputing for the original sealed room (A13).
- Tests for A19: `time.time` is patched via `monkeypatch.setattr(time, "time", ...)`; the expired-state test moves the SDK envelope clock too and is rejected by the boundary before the body runs.
- `test_no_state_kept_between_rounds` captures the decorated function with a fake server and asserts its only free variable is `dominio` (no reliance on SDK private attributes).
- `test_source_tree_has_no_hardcoded_secret` also scans repo-root files, `agente/src` and the server tests for 64+ hex string literals; none found.
- Gated tests activated: `test_cross_feature_f01` x2, `test_cross_feature_f03` x1, `test_cross_feature_f04` x1; the agent's 4 pause/retry tests in `test_mcp_host_against_server.py` now run and pass.
- `mensagens.SALA_OCUPADA` and `_responder_conflito` removed; `need_mrtr` removed from `test_cross_feature_f01.py` (callers use `need_tool`).
- Extra tests beyond the spec: `test_32021_matches_wire_capture`, `test_new_round_state_is_usable_for_the_next_retry`, `test_offer_never_contains_requested_room`, `test_startup_with_valid_secret_prints_banner`.

**Validation:** lint — no tooling (soft-fail) · typecheck — none (soft-fail) · server tests 443 passed, 3 skipped ✅ · agent tests 354 passed, 16 skipped (all F08-gated) ✅ · `validador/validar.py` checks 1-20 PASS against a real `python -m servidor_mcp` (21-36 need the agent process)
**Commit:** feat(F05): MRTR conflict resolution flow

## Final verification

- Full suite, server (`servidor-mcp/`): 443 passed, 3 skipped (the POSIX/root-only skips from F04), 0 failed. Baseline on entry was 322 passed, 7 skipped.
- Full suite, agent (`agente/`): 354 passed, 16 skipped; all skips are `consumer feature not registered yet (F08)`.
- Component Overview walk-through: `seguranca.py`, `alternativas.py`, `estado_pedido.py`, `mrtr.py`, modified `primitives/reservar_sala.py`, `__main__.py`, `mensagens.py` and the conftest/test adjustments are all present with the contracts of the spec.
- AC re-check: all 13 F05 acceptance criteria pass in a fresh run of their mapped tests (ACs 10 and 12-13 run against real subprocesses).
- Runtime smoke: real server process driven by the repository validator, checks 13-20 PASS.
- Soft-fails: no lint/typecheck tooling exists in the project.
- Open follow-up: F09 must store the key from `inputRequests` and resend byte-identical `arguments`; F10 README must quote the facts in spec 3.3 (AEAD AES-256-GCM via `RequestStateSecurity`, not HMAC).
