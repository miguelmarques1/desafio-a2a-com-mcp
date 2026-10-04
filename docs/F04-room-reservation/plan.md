# Implementation Plan: Room Reservation

**Prerequisites:**
- F01 MCP Server Foundation and F03 Availability and Policy Validation implemented (domain ledger, shared validation routine, conflict detection, execution-error builder, `primitives.REGISTRARS`)
- Repo-root virtualenv activated with the server installed in editable mode with its development extra (`pip install -e "./servidor-mcp[dev]"`)
- Pinned packages unchanged: `mcp==2.3.0`, `pydantic==2.13.5`, `uvicorn==0.54.0`; no new dependency
- No new environment variables
- Read-only references, never modified: `dados/`, `exemplos/wire/01-tools-list.json` (expected descriptor), `exemplos/wire/02-tools-call-livre.json` (expected success body), `exemplos/wire/11-tools-call-retry-recusa.json` (`ReservaOut` decline shape)
- Coordination: F05 extends the same tool module later and replaces the interim conflict branch (spec Section 3.3)

### Stage 1: Reservation Domain Core

**1. Ledger Exclusive Section** - Make the F01 reservation ledger's lock re-entrant and expose an exclusive-section context manager. Existing ledger operations keep their behavior and can run inside the section (spec Sections 3.2 A3 and 4).

**2. Reservation Messages** - Append an F04 block to the central messages module with the tool description, the internal-failure message and the interim conflict message from the spec, without editing existing constants.

**3. Id Generation and Atomic Registration** - Create the reservation domain module with the next-id rule and the occupied-room value. Add the routine that, in one exclusive section of the ledger, checks for conflicts, computes the next id and appends the verbatim record, as described in spec Sections 4 and 5.3.

### Stage 2: Reservation Tool

**4. Output Model and Creation Routine** - Create the reservation tool module with the `ReservaOut` output model and the creation routine that F05 will reuse. The routine turns a registered reservation into a confirmed receipt carrying the policy version, passes an occupied room through, and converts unexpected failures into the internal-failure result while leaving the ledger untouched (spec Sections 5.3 and 6).

**5. Tool Registration and Interim Conflict Branch** - Register `reservar_sala` in the same module so that its descriptor and responses match the wire captures. Validation runs first and fails with the shared messages. Conflicts go to an isolated interim branch that F05 will replace (spec Sections 3.2 A6 and 5).

**6. Registry Wiring** - Append the new registrar to the primitives registry as the third entry, after the availability tool, so `tools/list` lists the three tools in the documented order.

**7. Cross-Feature Gate Adjustment** - Tighten the gate of the two F05-dependent foundation cross-feature checks so they wait for the MRTR flow instead of activating when `reservar_sala` is registered (spec Section 3.2 A15).
