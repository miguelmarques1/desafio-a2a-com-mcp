# Implementation Plan: Reservation Skill Execution

**Prerequisites:**
- F04, F06 and F07 implemented; the repo-root virtualenv has `servidor-mcp` and `agente` installed in editable mode with their `dev` extras
- Python 3.10 or newer
- No new packages: existing pins unchanged (`starlette==1.7.0`, `uvicorn==0.54.0`, `httpx==0.28.1`, `pytest==9.1.1`, `setuptools==84.0.0`)
- Environment variables: `MCP_URL` (default `http://localhost:7301/mcp`) for the agent; `REQUEST_STATE_SECRET` only to run the MCP server
- Read-only inputs: `exemplos/wire/01`, `02`, `03`, `05` and `10` as the contract for MCP answers and the artifact text; `validador/validar.py` checks 24–26 and 35 as the target behaviour; no import of `servidor_mcp` from agent code
- F05 is not required: until it lands, a conflicting booking ends the Task failed with the server's interim text, and the input-required path is exercised only through the mocked transport

### Stage 1: Request Parsing and Outcome Mapping

**1. Skill Messages** - Add the usage message, the confirmation template and the stub pause message to the central messages module, with the exact texts listed in the spec. Leave the existing F07 stub texts in place.

**2. Fixed-Format Request Parser** - Implement the parser that turns the message text into the parsed booking request, or reports it as malformed, following the spacing, ordering, token and name rules of the spec. Provide the helper that rebuilds the tool-call arguments in the spec's key order, with no domain validation of any value.

**3. Outcome-to-Task Mapping** - Implement the shared mapping that completes a Task with the `reserva` artifact and the confirmation message, or fails it with the exact text, for each terminal outcome the spec lists. Include the payload checks for a successful booking and the artifact rendering that matches the wire example's text format.

### Stage 2: Skill Handler and Hand-off

**4. Input-Required Hand-off Contract** - Define the hand-off record that carries the original request, the policy version, the trace context and the input-required outcome, and the pause-hook contract F09 will implement. Add the stub pause hook that fails the Task with the fixed message until F09 exists, and keep the opaque state out of every textual representation.

**5. Reservation Skill Handler** - Implement the new-Task handler factory that runs the flow in the spec: reject malformed text without contacting the MCP server, move a valid Task to working, open the per-Task MCP context, call the reservation tool with the parsed arguments, and route the outcome to the mapping or to the pause hook.

### Stage 3: Registration and Activation

**6. Skill Registration** - Register the skill handler in the handler registration hook with the single shared MCP client, keeping the F07 continuation stub and the client's shutdown hook. Update the hook's documentation so F09 knows how to pass its pause hook and continuation handler.

**7. Activation of Previously Gated Cross-Feature Checks** - Registering the skill activates the F06 and F07 Task-level checks that were waiting for it. Change the one shared probe that would otherwise book the slot its checks request later, as the spec's assumption A20 describes, and leave everything else unchanged.

