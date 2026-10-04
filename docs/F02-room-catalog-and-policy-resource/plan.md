# Implementation Plan: Room Catalog and Policy Resource

**Prerequisites:**
- F01 MCP Server Foundation implemented and green: repo-root virtualenv with `pip install -e "./servidor-mcp[dev]"` (`mcp==2.3.0`, `uvicorn==0.54.0`, `pytest==9.1.1`, `httpx==0.28.1`); no new dependency is added by F02
- Environment variables: none new; `MCP_PORT`, `MCP_HOST` and `MCP_DADOS_DIR` behave as in F01, and `REQUEST_STATE_SECRET` is not needed by F02
- Configuration files: none changed (`servidor-mcp/pyproject.toml` stays as is)
- Read-only references: `dados/salas.json` and `dados/politica-de-uso.md` (never modified), `exemplos/wire/01-tools-list.json` and `exemplos/wire/05-resources-read-politica.json` as the target wire shapes, `validador/validar.py` checks 1–8
- Coordination: F03 is specified in parallel and edits the same shared files (primitives registry, messages module); follow the spec's coordination notes (Section 3.3)

### Stage 1: Catalog Tool

**1. Wire-Visible Strings** - Add a clearly labelled F02 block to the central messages module with the `listar_salas` description and the policy resource's name, title and description exactly as listed in the spec. Leave every existing constant untouched so blocks added by other features merge without conflict.

**2. Catalog Output Models** - Create the F02 primitives module with the resource URI and MIME type constants and the two output models for the room list, declared so that the schema the SDK generates reproduces the `listar_salas` entry of the wire example. Follow the field order and naming given in the spec's data model.

**3. Catalog Tool Registration** - Implement the module's registrar so it registers `listar_salas` as a structured tool that builds the room list from the injected domain's catalog in file order, with the exact tool identity and description the spec requires. The registrar keeps no module-level state and never reads from disk.

### Stage 2: Policy Resource and Registry Wiring

**4. Policy Resource Registration** - Extend the same registrar to register the static `politica://uso` resource with its Markdown MIME type and metadata, serving the policy text held by the injected domain exactly as loaded. Unknown URIs are left to the SDK's not-found handling, as described in the spec's error handling table.

**5. Registry Entry** - Make the F02 registrar the first entry of the primitives registry so `listar_salas` leads `tools/list`. If another feature has already added its entry, insert F02's ahead of it rather than appending.
