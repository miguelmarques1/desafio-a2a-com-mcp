# Implementation Progress: Delivery Documentation and Validation

**Status:** in progress
**Branch:** feat/a2a-agent-and-mcp-server-implementation
**Started:** 2026-10-04
**Last updated:** 2026-10-04

## Stage 1: Run Support Files — ✅ done

- [x] **1. Line-Ending Policy**
- [x] **2. Environment Template**
- [x] **3. Start Scripts**

**Observations:**
- `.sh` scripts also fall back to `.venv/Scripts/activate` (Git Bash on Windows). Spec A10 only names `.venv/bin/activate`; the fallback is additive and the missing-venv message is unchanged.
- `.ps1` files are LF in the working tree and become CRLF in the index via `.gitattributes` (`eol=crlf`). Git may print an LF→CRLF warning on `git add`; expected.
- `.env` is ignored (`.gitignore` line 1), `.env.example` is not.
- Scripts parse `.env` (never `source` it). Verified on bash and PowerShell 5.1 with a fake venv: comments and blank lines skipped, whitespace trimmed, one pair of quotes stripped, CR stripped, already-exported key wins, empty `REQUEST_STATE_SECRET=` exports an empty value, missing venv → message + exit 1.
- `.sh` files staged with mode 100755 via `git update-index --chmod=+x`.

**Validation:** scripts: `bash -n` ✅ · fake-venv behaviour tests (bash, PowerShell 5.1) ✅ · lint/typecheck/pytest n/a (no package code touched)
**Commit:** df29734 feat(F10): run support files (env template, start scripts, line endings)

## Stage 2: Delivery README — ✅ done

- [x] **4. Evidence Gathering**
- [x] **5. Como rodar and Roteiro manual**
- [x] **6. Bridge and Decisions Sections**
- [x] **7. Delivery Guard**

**Observations:**
- Bridge anchors: `pause_task` is `bridge.py` line 70, `send_retry` line 80 (matches the spec). The README links `#L70` and `#L80`; `test_bridge_anchors_point_at_named_functions` guards them.
- SDK era routing (V4): `mcp==2.3.0`, `mcp/server/streamable_http_manager.py` lines 192–197 (comment `TODO(L49): header-only era-routing` at line 187). Re-observed with `curl` on `tools/list`: header `2025-11-25` and an absent header → HTTP 200; `2099-01-01` → 400 `-32020`; `Mcp-Method` mismatch → 400 `-32020`.
- V3 resolved, and it differs from spec A19's hedge: a retry with an intact, valid `requestState` but **edited `arguments`** is rejected by the SDK envelope with HTTP 400 `-32602 Invalid or expired requestState`. The unedited retry of the same state succeeds (also across an MCP restart with the same secret), so the rejection is argument binding, not a stale state. README documents both layers ("valores selados vencem" in `_retomar` + SDK binding) and offers the `curl` as optional step 11b.
- Roteiro prototyped live against fresh processes; every value in spec A16 matched (7: `sala-fusca, sala-mirante`; 8: COMPLETED/`sala-mirante`; 9: pause `sala-fusca` then CANCELED; 10: FAILED `Sala inexistente: sala-inexistente`; 11: `-32602`; 12: `complete`/`reservado: true` in `sala-fusca` after restart; 13: 400/`-32021`). The live `inputRequests` key is `reservar_sala:escolha_de_sala`, as the spec says.
- Gotcha hit while prototyping: an `export REQUEST_STATE_SECRET` does not survive into a restart from another shell, which loses the sealed state. The README warns about it and the `.env` shortcut avoids it.
- `python3` in Git Bash on this machine resolves to Python 3.14.4, so the Roteiro helpers ran as written. Only Python 3.14 is installed here (no 3.10 interpreter), so V1 (Python 3.10) remains unverified and is recorded for Stage 3.
- Deviation from spec A24: `test_no_secret_in_tracked_files` ignores `REQUEST_STATE_SECRET=` followed by a backtick (inline-code prose in README/PRD/progress). Real values and 64+ hex runs still fail.
- `test_validator_output_is_a_full_passing_run` checks for `^FAIL ` lines, not the substring `FAIL`: validator check 3x describes a Task "em FAILED", which is a legitimate PASS line.
- The validator output currently in the README comes from a fresh-process run on the development working copy (Windows 11, Python 3.14.4, via the `.sh` scripts). Stage 3 replaces it with the clean-clone run.

**Validation:** lint n/a · typecheck n/a (none configured) · `tests` 15/15 ✅ · `servidor-mcp` 443 passed / 3 skipped ✅ · `agente` 489 passed / 1 skipped ✅ · validator 36/36 exit 0 ✅
**Commit:** _(recorded in the next commit)_

## Stage 3: Clean-Clone Verification and Delivery — 🔄 in progress

- [ ] **8. Clean-Clone Run**
- [ ] **9. Validator Output**
- [ ] **10. Delivery on main**

**Observations:** _(none yet)_

**Validation:** _(not run)_
**Commit:** _(none)_
