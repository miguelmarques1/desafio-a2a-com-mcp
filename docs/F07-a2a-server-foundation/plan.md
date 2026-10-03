# Implementation Plan: A2A Server Foundation

**Prerequisites:**
- Python 3.10 or newer with `pip` and the standard `venv` module
- The repo-root virtualenv shared with `servidor-mcp/` (`python3 -m venv .venv`), activated before installing or running anything
- Pinned packages (spec Sections 3.3 and 4): `starlette==1.7.0`, `uvicorn==0.54.0`; build backend `setuptools==84.0.0`; development extra `pytest==9.1.1`, `httpx==0.28.1` (pins shared with `servidor-mcp` must stay identical)
- Environment variables: `AGENT_PORT` (default `7300`), `AGENT_HOST` (default `127.0.0.1`), `AGENT_PUBLIC_URL` (default `http://localhost:<AGENT_PORT>`)
- Configuration files: `agente/pyproject.toml` (new), root `.gitignore` (entries ensured)
- Read-only inputs: `exemplos/wire/07`–`10` and `validador/validar.py` as the A2A contract (never modified); no runtime dependency on `servidor-mcp`

### Stage 1: Project Scaffold

**1. Project Manifest** - Replace the placeholder in `agente/` with the project manifest. It declares the src-layout package, the pinned runtime dependencies, the development extra, both entry points and the test configuration listed in the spec. Ensure the root `.gitignore` already ignores the generated artifacts the spec names.

**2. Dependency Surface Confirmation** - Install the agent project in editable mode, with its development extra, into the repo-root virtualenv alongside the MCP server project. Then confirm each item the spec lists as "verify at implementation". Record any divergence in the spec's decisions table and apply the fallback the spec gives for that item before building on it.

**3. Package Skeleton, Messages and Identifiers** - Create the package with its version and the central module holding every exact user-facing string, including errors, stub messages, banner and startup failures. Add the identifier generator for Task, context, message and artifact ids in the injectable form the spec describes.

### Stage 2: A2A Data Model and Task Lifecycle

**4. A2A Data Model and Wire Serialization** - Implement the A2A value types, the state and role enumerations, and their wire serialization. Keys must come out in exactly the order and with exactly the optional-field rules shown in `exemplos/wire/08`–`10`.

**5. Task State Machine** - Implement the table of allowed transitions and the terminal-state rules from the spec. Resuming a paused Task must only be possible inside an accepted continuation.

**6. In-Memory Task Store** - Implement the process-wide Task store and the per-Task handle given to handlers. The store covers Task creation, transitions with status messages, history and artifacts, detached snapshots, busy claims, settling of unfinished Tasks, and the private per-Task attachment that is never serialized and is dropped when a Task ends.

### Stage 3: JSON-RPC Endpoint and Extension Points

**7. JSON-RPC Envelope and Errors** - Implement envelope parsing, the standard and A2A-specific error model with its exact messages and structured details, response building, and the single JSON renderer used for every body.

**8. Request Parameters** - Implement validation of the `SendMessage` and `GetTask` parameters and parsing of the incoming user message into the form handlers receive, with the error precedence and detail texts from the spec.

**9. Extension Points and Stub Handlers** - Define the request context, the new-Task and continuation handler contracts, and the handler bundle. Add the registration hook through which F08 and F09 will plug in their handlers. Provide the documented stub handlers that fail the Task until those features exist.

**10. Method Dispatcher** - Implement the dispatcher, in the order the spec defines: version header check, method lookup, synchronous `SendMessage` with routing between new Tasks and continuations (including terminal and busy-Task rejections), and `GetTask`. Failures inside a handler must end the Task as an internal failure while the response still returns the Task.

**11. Agent Card** - Build the Agent Card from the public URL with the exact fields, texts and key order of `exemplos/wire/07`, rendered once at startup.

**12. Request Log and Application Assembly** - Implement the stderr request log line and its rendering rules. Assemble the Starlette application with the card route, the A2A route that feeds request headers and body to the dispatcher and writes one log line per request, and the shutdown hook for handler resources.

### Stage 4: Process Startup

**13. Runtime Configuration and Listening Socket** - Implement loading of host, port and public URL from the environment with the defaults and validation failures defined in the spec. Implement creation of the listening socket with the platform-specific options, distinguishing a port already in use from any other bind failure.

**14. Entry Point and Startup Sequence** - Implement the module entry point and console script. They run configuration, card construction, handler registration, application assembly, socket binding, the stderr banner and the uvicorn run on the pre-bound socket, mapping each startup failure to its message and exit code as listed in the spec's startup contract.
