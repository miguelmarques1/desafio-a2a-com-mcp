# Implementation Plan: Delivery Documentation and Validation

**Prerequisites:**
- F01–F09 implemented on this branch. The repo-root `.venv` has `servidor-mcp` and `agente` installed in editable mode with their `dev` extras.
- Python 3.10 or newer to run anything. A Python 3.10 interpreter is also needed for the clean-clone check (spec V1); if none is available, record the gap.
- `git`, `curl` and a bash shell (Linux/macOS, WSL or Git Bash) for the POSIX path, and PowerShell 5.1+ for the Windows path.
- No new packages and no pin changes.
- `REQUEST_STATE_SECRET` generated locally, never committed.
- Read-only inputs:
  - `exemplos/wire/` (Roteiro bodies)
  - `validador/validar.py` and `validador/README.md` (output format, re-run rule)
  - The F01, F05, F06, F07 and F09 specs and progress files (facts the README must carry)
  - The starter commit `263f17e`

### Stage 1: Run Support Files

**1. Line-Ending Policy** - Add the root attributes file that keeps shell scripts LF and PowerShell scripts CRLF, as the spec's decision table describes.

**2. Environment Template** - Add the committed environment template with an empty secret and the commented defaults, following the exact content in the spec. Confirm the real `.env` stays ignored and the template does not.

**3. Start Scripts** - Write the two bash scripts and the two PowerShell scripts that activate the repo-root venv, load `.env` by the spec's precedence rules, and start one process in the foreground. Mark the bash scripts executable in the git index, and check each failure mode in the spec's script behaviour table.

### Stage 2: Delivery README

**4. Evidence Gathering** - Collect the facts the README quotes: the current line numbers of the two bridge functions, the era-routing excerpt from the installed MCP SDK, and the observed behaviour of a retry with edited arguments (spec V3, V4). Note anything that contradicts the spec's assumptions before writing.

**5. Como rodar and Roteiro manual** - Replace the starter README with the delivery title, the summary and the "Como rodar" section: the bash walkthrough, the env table, the re-run rule, the scripts shortcut, the Windows subsection and the optional tests subsection. Then write the "Roteiro manual" for evaluator steps 7–13. It uses the wire-file extraction helpers and the expected values from the spec.

**6. Bridge and Decisions Sections** - Write the "Onde a ponte acontece" paragraph with the two anchored links, and the "Decisões técnicas" section with every decision and the SDK limitations (with evidence) that the spec lists.

**7. Delivery Guard** - Add the repo-root delivery check suite described in the spec. It must skip gracefully when git or the starter commit is unavailable.

### Stage 3: Clean-Clone Verification and Delivery

**8. Clean-Clone Run** - Clone the branch into an empty directory, follow only "Como rodar", and run the validator three times with both processes restarted before each run. Then run the Roteiro manual once, including the MCP restart and the trace-id grep. Fix every README or script mismatch found, and record defects in application code instead of patching them here.

**9. Validator Output** - Paste the full output of the last passing run into "Saída do validador", with the provenance sentence, then re-run every test suite (both packages and the delivery guard). Confirm that the starter directories are still unchanged.

**10. Delivery on main** - Prepare the merge of the feature branch into `main` of the public fork through a pull request. Open it only after the user explicitly approves.
