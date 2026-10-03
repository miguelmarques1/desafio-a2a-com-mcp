# Implementation Plan: MCP Server Foundation

**Prerequisites:**
- Python 3.10 or newer with `pip` and the standard `venv` module
- One virtualenv at the repository root (`python3 -m venv .venv`), activated before installing or running anything
- Pinned packages (spec Sections 3.2 and 4): `mcp==2.3.0`, `uvicorn==0.54.0`; build backend `setuptools==84.0.0`; development extra `pytest==9.1.1`, `httpx==0.28.1`
- Environment variables: `MCP_PORT` (default `7301`), `MCP_HOST` (default `127.0.0.1`), `MCP_DADOS_DIR` (optional override), `REQUEST_STATE_SECRET` (read but not used until F05)
- Configuration files: `servidor-mcp/pyproject.toml` (new), root `.gitignore` (extended)
- Read-only inputs: `dados/salas.json`, `dados/reservas.json`, `dados/politica-de-uso.md` (never modified); `exemplos/wire/` as the reference for request and response shapes

### Stage 1: Project Scaffold and SDK Baseline

**1. Project Manifest** - Replace the placeholder in `servidor-mcp/` with the project manifest that declares the src-layout package, the pinned runtime dependencies, the development extra, both entry points and the test configuration listed in the spec. Extend the root `.gitignore` with the generated artifacts the spec names.

**2. SDK Surface Confirmation** - Install the server project in editable mode with its development extra into the repo-root virtualenv, then confirm against the installed SDK source each item the spec lists as "verify at implementation". Record any divergence in the spec's decisions table and apply the fallback the spec gives for that item before building on it.

**3. Package Skeleton, Messages and Registry** - Create the package with its version, the central module holding every exact user-facing startup and banner string, and the empty primitives registry that F02–F05 will extend, documenting its registration contract as described in the spec.

### Stage 2: Configuration and In-Memory Domain

**4. Runtime Configuration** - Implement loading of host, port, the optional data-directory override and the raw request-state secret slot from the environment, with the defaults and the invalid-port failure defined in the spec.

**5. Data Directory Resolution** - Implement the repository-root search and the ordered resolution of the `dados/` directory so the server finds its data from any working directory, following the precedence in the spec.

**6. Domain Model** - Implement the immutable room, reservation and policy types, the ordered room catalog, the lock-protected append-only reservation ledger and the aggregate handed to every registrar, with the invariants listed in the spec's data model.

**7. Domain Loader** - Implement read-only loading of the three data files in the specified order, with shape validation, verbatim policy text, policy version extraction, and the two startup error types carrying the exact messages from the spec.

### Stage 3: MCP Transport and Observability

**8. Server Factory** - Implement the factory that creates the `central-de-salas` server with its fixed identity and quiet logging, forwards an optional request-state security object when one is provided, and runs every registrar from the registry against the loaded domain.

**9. Per-Request Context Accessors** - Implement the accessors that expose the current request's client capabilities and the strict form-elicitation check that F05 will consume, reading only the value the SDK built from that request's envelope.

**10. Request Log Middleware** - Implement the ASGI middleware and its pure formatting rules so that every JSON-RPC request posted to `/mcp`, including unparseable and rejected ones, produces its stderr line before processing, while the body reaches the SDK unchanged.

**11. ASGI Application Assembly** - Build the application by obtaining the SDK's Streamable HTTP app in stateless, JSON-response mode on `/mcp` and wrapping it with the request log middleware so the SDK app keeps its own lifespan and its inbound validation ladder stays enabled.

### Stage 4: Process Startup

**12. Listening Socket** - Implement creation and binding of the listening socket with the platform-specific options from the spec, distinguishing a port already in use from any other bind failure.

**13. Entry Point and Startup Sequence** - Implement the module entry point and console script that run configuration, the reserved F05 secret slot, data resolution, domain loading, server and app assembly, socket binding, the stderr banner and the uvicorn run on the pre-bound socket, mapping each startup failure to its message and exit code as listed in the spec's error handling table.
