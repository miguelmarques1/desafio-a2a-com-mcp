# Implementation Plan: MRTR Conflict Resolution

**Prerequisites:**
- F01 MCP Server Foundation, F03 Availability and Policy Validation and F04 Room Reservation implemented: request-state slot in the entry point, `build_server` forwarding of the security policy, per-request capability accessor, shared validation and conflict detection, atomic creation routine and `ReservaOut`
- Repo-root virtualenv activated with the server installed in editable mode with its development extra (`pip install -e "./servidor-mcp[dev]"`)
- Pinned packages unchanged: `mcp==2.3.0`, `pydantic==2.13.5`, `uvicorn==0.54.0`. No new dependency (`cryptography` is already present through `mcp`)
- Environment variable `REQUEST_STATE_SECRET` (at least 64 hex characters, generated with `python3 -c "import secrets; print(secrets.token_hex(32))"`) exported before starting the server. Never committed
- Read-only references, never modified: `dados/`, `exemplos/wire/01`, `03`, `04`, `06` and `11` (expected descriptor, round, retry, capability error and decline shapes), `validador/validar.py` (checks 13–20)
- Coordination: F05 extends the F04 tool module and adds no registrar (spec Section 3.3)

### Stage 1: Request-State Security and Startup

**1. MRTR Messages** - Append an F05 block to the central messages module with the startup secret message, the elicitation texts, the zero-alternatives message and the protocol error texts listed in the spec. Delete the F04 interim conflict message.

**2. Secret Validation and Security Policy** - Create the security module that validates the request-state secret and builds the SDK request-state policy with the 10-minute validity, as described in spec Sections 3.2 (A4) and 4.

**3. Startup Wiring** - Fill the reserved slot in the server entry point. The secret is checked before the domain data loads, so an invalid secret aborts with the exact message and exit code `1`, and the resulting policy is passed to the server factory (spec A5).

### Stage 2: Conflict Domain

**4. Alternatives Rule** - Create the pure module that computes the offered alternative rooms for a validated request from the catalog and the ledger, applying the exclusion, capacity, freeness, ordering and cap rules in spec Section 6.

**5. Sealed Request Payload** - Create the pure module that defines the payload sealed inside `requestState`: the original request, offered alternatives, issued key and expiry. Add its strict encoding, decoding and expiry check, following spec Section 6 and A6.

### Stage 3: MRTR Tool Flow

**6. Round Protocol Helpers** - Create the MCP-facing helper module that builds the `input_required` result with its single form elicitation, raises the missing-capability error and the invalid-state and missing-answer errors, and reads the client's answer under the sealed key (spec Sections 4 and 5.6).

**7. Tool Signature Widening** - Give `reservar_sala` access to the request context and let it return an `input_required` result, while keeping the published tool descriptor identical to the wire capture (spec Section 3.1, S1 and S2).

**8. First-Round Conflict Resolution** - Replace the interim conflict branch with the first-call decision order: a free room is booked; a conflict with no alternatives returns the zero-alternatives error; a client without form elicitation gets the capability error; otherwise the client is asked to choose (spec Section 5.2).

**9. Retry Handling** - Add the retry path that rebuilds the request from the sealed payload alone. It completes on decline or cancel, books an accepted sealed alternative through the F04 routine, and starts a new round with recomputed alternatives when the choice is invalid or the room was taken in the meantime (spec Section 5.3 decision table).

**10. Interim Leftovers Removal** - Remove the remaining interim conflict code from the tool module, and retire the temporary F05 gate in the foundation cross-feature checks so they run unconditionally (spec Section 3.3).
