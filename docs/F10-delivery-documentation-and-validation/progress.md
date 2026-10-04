# Implementation Progress: Delivery Documentation and Validation

**Status:** success
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
**Commit:** 03931ba feat(F10): delivery README and static delivery checks

## Stage 3: Clean-Clone Verification and Delivery — ✅ done (step 10 awaits user approval)

- [x] **8. Clean-Clone Run**
- [x] **9. Validator Output**
- [ ] **10. Delivery on main** — not performed on purpose: opening the PR into `main` needs the user's explicit approval (spec A29). Nothing was pushed.

**Observations:**
- Clean clone: `git clone --branch feat/a2a-agent-and-mcp-server-implementation` of the local repo into a fresh temp dir (commit 03931ba), venv created with `py -3 -m venv`, editable install of both packages, secret exported in PowerShell, both processes started with `python -m`, as in the README's Windows subsection. Validator ran 3 times with both processes restarted each time: 36/36, exit 0, 8 `mcp` stderr rows carrying the run's trace-id every time.
- Roteiro: the bash blocks were extracted verbatim from the README and executed in Git Bash against that clone, with the MCP restart between step 12's two blocks (same secret). Every expected value of spec A16 matched; the trace-id grep found 11 rows in the first server process's stderr.
- Bug found only by the clean clone: `tests/test_entrega.py` was untracked in the working copy, so `test_no_secret_in_tracked_files` never scanned it; once tracked it flagged its own secret-assignment literals (the patterns it scans for). Fixed by excluding that one file from the scan.
- `pip.exe` was blocked by a Windows Application Control policy on this machine; the run used `python -m pip install ...` (same command). The README now mentions that fallback. Not a repo defect.
- WSL Ubuntu here has no `python3-venv` (needs `sudo apt install`), so no venv could be created there. The README prerequisites now say to install it on Debian/Ubuntu. The Linux-specific V5 check still ran in WSL on a fresh clone: `.sh` files are `-rwxr-xr-x`, LF shebang, and `./subir-agente.sh` prints the missing-venv message and exits 1.
- Validator output in the README is run 3 of the clean clone (Windows 11, Python 3.14.4).

**Validation:** clean-clone validator ×3 36/36 exit 0 ✅ · Roteiro 7–13 ✅ · `tests` 15/15 ✅ · `servidor-mcp` 443 passed / 3 skipped ✅ · `agente` 489 passed / 1 skipped ✅ · starter dirs unchanged ✅
**Commit:** _(this commit)_

## Final verification

**Status:** success

- Full suite: `python -m pytest tests` 15/15, `servidor-mcp` 443 passed / 3 skipped, `agente` 489 passed / 1 skipped. Same counts as the end of F09 for the two packages. No lint or typecheck tooling exists in the repo.
- Component Overview walk-through: `README.md`, the four `subir-*` scripts, `.env.example`, `.gitattributes`, `tests/test_entrega.py` all exist with the described content; `.gitignore` unchanged. `git diff b598d0a HEAD` over `servidor-mcp`, `agente`, `dados`, `validador`, `exemplos` and `.gitignore` is empty. `git diff 263f17e -- dados validador exemplos` is empty.
- Missing from spec: none. Regressions: none. Pre-existing failures: none.
- Acceptance criteria: all eight F10 criteria map to a passing test or to the clean-clone run (see the chat report).

**Soft-fails / unverified:**
- V1: no Python 3.10 interpreter was available (only 3.14.4 on Windows and in WSL), so the "Python ≥ 3.10" claim rests on `requires-python` and the pins, not on a 3.10 run.
- The README's bash path (`source .venv/bin/activate`, `python3 -m venv`) was not run end to end on Linux/macOS; WSL could not create a venv. Windows PowerShell and Git Bash (via the scripts and the Roteiro blocks) were exercised, and the Linux checks were limited to V5.
- The PowerShell scripts were exercised with a fake venv only; the `.sh` scripts were exercised with both a fake venv and the real one.

**Open follow-up:**
- Step 10: open a PR from this branch into `main` of the public fork, after the user approves. The final delivery on `main` is a user action (PRD Capabilities 7).
- `spec.md` and `plan.md` of F10 are still untracked in the working tree (they were untracked when this run started); commit them with the PR or earlier if wanted.
