# Implementation Progress: Availability and Policy Validation

**Status:** in progress
**Branch:** feat/a2a-agent-and-mcp-server-implementation
**Started:** 2026-10-03
**Last updated:** 2026-10-03

## Stage 1: Shared Policy Rules — ✅ done

- [x] **1. Validation Messages and Dependency Declaration**
- [x] **2. Timestamp Interpretation**
- [x] **3. Shared Validation Routine**
- [x] **4. Conflict Detection**

**Observations:**
- Offset hours/minutes are range-checked by hand (hour <= 23, minute <= 59) before building the `timezone`, so the grammar never depends on Python's `timezone` limits.
- `tests/unit/test_regras.py` also loads `validador/validar.py` by path to compare its `ERRO_*` constants with `mensagens` (read-only).
- A24 (`fresh_app` defaults to production `REGISTRARS`) was already done by F02; no conftest change needed in F03.

**Validation:** lint — no tooling declared (soft-fail) · typecheck — none declared (soft-fail) · tests 231 passed, 9 skipped ✅ (new: 90 unit in test_regras.py)
**Commit:** feat(F03): shared policy rules

## Stage 2: Availability Tool — ⬜ pending

- [ ] **5. Execution-Error Result Builder**
- [ ] **6. Availability Tool Module**
- [ ] **7. Registry Wiring**

**Observations:** _(none yet)_

**Validation:** _(not run)_
**Commit:** _(none)_
