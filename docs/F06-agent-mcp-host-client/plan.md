# Implementation Plan: Agent MCP Host Client

**Prerequisites:**
- F01, F02 and F07 implemented. The repo-root virtualenv has both projects installed in editable mode with their `dev` extras
- Python 3.10 or newer
- Pinned packages (spec Section 3.3, A1): `httpx==0.28.1` becomes a runtime dependency of `agente`, with the same pin `servidor-mcp` uses; existing pins unchanged (`starlette==1.7.0`, `uvicorn==0.54.0`, `pytest==9.1.1`, `setuptools==84.0.0`)
- Environment variables: `MCP_URL` (new, default `http://localhost:7301/mcp`); `REQUEST_STATE_SECRET` exported only for running the MCP server in integration tests
- Read-only inputs: `exemplos/wire/01`–`06` and `11` as the MCP wire contract, and the F01 server's stderr request log as the evidence format; no import of `servidor_mcp` from agent code

### Stage 1: Configuration and Dependency

**1. Runtime HTTP Client Dependency** - Promote the async HTTP client to a runtime dependency of the agent project, with the pin it already has, and remove it from the development extra. Reinstall the agent project in the shared virtualenv.

**2. Dependency and Wire Confirmation** - Confirm each "verify at implementation" item of the spec against the installed HTTP client and a running MCP server. Record any divergence in the spec's decisions table and apply the fallback the spec gives before building on it.

**3. MCP URL Setting and Messages** - Extend the agent settings with the MCP endpoint URL, its default and its startup validation, so an invalid value stops the process with the spec's message and exit code. Add every F06 failure text and the new startup error to the central messages module.

### Stage 2: Protocol Building Blocks

**4. Trace Context** - Implement W3C trace-context handling: recognize a valid incoming header, keep its trace-id and flags, generate a trace-id once per Task when the header is absent or invalid, produce a fresh span-id for every request, and derive the trace context for a continuation, all as the spec describes.

**5. Request Envelope and Headers** - Implement the builder for stateless MCP request bodies, with the mandatory envelope metadata and the field order of the wire examples. Implement the matching mirrored headers for each method, including the retry variant that carries input responses and the stored opaque state.

**6. Response Decoding** - Implement decoding of server responses delivered as plain JSON or as a single server-sent event, whatever the HTTP status. Recognize only well-formed JSON-RPC responses that answer the current request, following the spec's decoding rules.

**7. Outcome Model and Normalization** - Define the four tool-call outcomes and the input-response builders. Implement the normalization of tool results and JSON-RPC errors into those outcomes, including the supported input-required shape, the exact failure texts, and the guarantee that the opaque state never appears in any textual representation.

### Stage 3: MCP Client and Per-Task Context

**8. MCP Client Core** - Implement the client that owns the pooled HTTP connection, the process-wide request id counter and the per-request time limit. Map every transport failure to the unavailable-server outcome without retries, and keep cancellation intact.

**9. Discovery and Policy Read** - Add tool discovery with pagination, and the policy resource read that selects the policy entry's text, to the client. Both return either their data or a failure outcome.

**10. Tool Call and Retry Invocation** - Add the tool invocation and the retry invocation to the client. The retry re-sends the same tool name and original arguments under a new id with the stored key and the stored state unchanged, and both return a normalized outcome.

**11. Per-Task Context Opener** - Implement the opener that, for a new Task, runs discovery, checks the required tool, reads the policy and extracts its version, in the order and with the failure messages defined in the spec. It returns the context F08 consumes.

### Stage 4: Composition

**12. Client Lifecycle in the Registration Hook** - Build the single MCP client from the settings inside the handler registration hook and register its shutdown, keeping the F07 stub handlers in place. Document in the hook how F08 and F09 receive the same client instance.

**13. Public Surface and Consumer Contract** - Expose the client, the opener, the trace context, the outcome types and the response builders from the new package. Document there the boundary rules F08 and F09 must follow, especially around the opaque state.
