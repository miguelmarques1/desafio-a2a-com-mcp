# Implementation Plan: Availability and Policy Validation

**Prerequisites:**
- F01 MCP Server Foundation implemented (`servidor-mcp/` package, domain loader, `primitives.REGISTRARS` registration hook)
- Repo-root virtualenv activated with the server installed in editable mode with its development extra (`pip install -e "./servidor-mcp[dev]"`)
- Pinned packages: `mcp==2.3.0` (existing). `pydantic==2.13.5` becomes a declared direct dependency; it is already installed transitively (spec Section 3.2, A21)
- No new environment variables
- Read-only references: `dados/salas.json`, `dados/reservas.json`, and `exemplos/wire/01-tools-list.json` (the expected tool descriptor). Never modified
- Coordination: F02 is developed in parallel and owns the first registry position (spec Section 3.3)

### Stage 1: Shared Policy Rules

**1. Validation Messages and Dependency Declaration** - Append an F03 block to the central messages module with the five exact validation messages and the tool description listed in the spec, without touching existing constants. Declare the direct dependency the spec names in the server manifest.

**2. Timestamp Interpretation** - Implement the strict, Python-version-independent interpretation of ISO 8601 timestamps with an explicit offset, and their conversion to the fixed policy time zone, following the grammar and edge cases in spec Section 5.4.

**3. Shared Validation Routine** - Implement the pure routine that checks room existence, timestamps, interval validity, usage window and maximum duration in the order the spec defines. It returns either a validated request or the first failure with its exact message, as described in spec Sections 5.3 and 6.

**4. Conflict Detection** - Implement the half-open interval overlap and the per-room lookup of conflicting reservations in the in-memory ledger. Results are ordered and filtered as the spec requires, so F04 and F05 can reuse them unchanged.

### Stage 2: Availability Tool

**5. Execution-Error Result Builder** - Implement the shared builder that turns a failure message into a complete execution-error tool result carrying exactly that text, for reuse by the later booking tools.

**6. Availability Tool Module** - Create the primitive module with the output models and the registrar for `consultar_disponibilidade`. Connect the validation routine, conflict detection and result builder so that the tool descriptor and responses match spec Section 5.

**7. Registry Wiring** - Add the new registrar to the primitives registry in the position the spec defines: after F02's registrar and before the future booking registrar. If the edit collides with F02, keep both entries in the documented order.
