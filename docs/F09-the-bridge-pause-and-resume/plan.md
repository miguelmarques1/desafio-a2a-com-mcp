# Implementation Plan: The Bridge: Pause and Resume

**Prerequisites:**
- F05, F06, F07 and F08 implemented. The repo-root virtualenv has `servidor-mcp` and `agente` installed in editable mode with their `dev` extras.
- Python 3.10 or newer
- No new packages. Existing pins are unchanged (`starlette==1.7.0`, `uvicorn==0.54.0`, `httpx==0.28.1`, `pytest==9.1.1`, `setuptools==84.0.0`).
- Environment variables: `MCP_URL` (default `http://localhost:7301/mcp`) for the agent. `REQUEST_STATE_SECRET` is needed only to run the MCP server.
- Read-only inputs:
  - `exemplos/wire/03`, `04`, `09`, `10` and `11` are the contract for the pause, the retry and the continuation shapes.
  - `validador/validar.py` checks 27–36 are the target behaviour.
  - No agent code imports `servidor_mcp`.

### Stage 1: Choice Parsing and Paused State

**1. Bridge Messages** - Add the alternatives line template and the decline confirmation to the central messages module, using the exact texts in the spec. Keep the existing stub texts.

**2. Choice Parser** - Implement the strict parser for the `escolha=<valor>` reply, then classify the value as an accepted alternative, a decline, or an invalid reply. Follow the spec's syntax and ordering rules. The parser knows nothing about rooms beyond the alternatives it is given.

**3. Paused Record** - Define the private paused record with the fields the spec lists. It is built from F08's hand-off, and it can produce the next round from a new input-required outcome. The opaque request state must stay out of every textual representation.

### Stage 2: Pause and Resume

**4. Pause** - Implement the pause step: store the paused record on the Task, then move the Task to input-required with the exact alternatives line. Expose it as the pause hook that F08's skill handler accepts. This is one of the two named bridge entry points the spec reserves for the README.

**5. Retry Invocation** - Implement the retry step. It sends the original tool call again through the shared MCP client, with the stored key and request state and the trace context the spec selects. This is the second named bridge entry point.

**6. Continuation Handler** - Implement the continuation handler factory. It reads the paused record, and on an invalid reply it re-prompts without any MCP traffic. On an accepted alternative or a decline, it moves the Task to working and performs the retry. It maps the result to completed, canceled, failed or a new pause: accept results reuse F08's mapping, and decline results use the decline mapping in the spec. It also covers the missing-record failure case.

### Stage 3: Registration and Activation

**7. Bridge Registration** - In the handler registration hook, give the skill handler the pause hook and replace the continuation stub with the bridge's continuation handler. Both use the same shared MCP client, and the client's shutdown hook stays in place. Update the hook's documentation to describe the final wiring.

**8. Test Fixture Extension** - Extend the MCP server start fixture so a test can restart the server on the same port, with either the same secret or a different one, as assumption A20 in the spec describes. Existing callers must keep working unchanged. Registering the bridge activates the previously gated F06 and F07 checks without any edits to them.
