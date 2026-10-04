"""Registration hook where the skill (F08) and the bridge (F09) plug in.

Contract:
- `new_task` is the `reservar-sala` skill handler (F08), built on the shared `McpClient`.
- F09 passes its pause hook as `make_reservar_sala_handler(client, on_input_required=...)` and
  replaces `continuation` with the pause/resume bridge, reusing the same client.
- Shared resources (e.g. F06's MCP client) are built inside `build_handlers`,
  never at import time, and released through `Handlers.aclose`, which the app
  awaits on shutdown.
- F08/F09 must capture the `McpClient` built below in their handler closures: one client
  (one id counter, one connection pool) serves the whole process.
- A handler is `async (RequestContext, TaskHandle) -> None` and must leave the
  Task terminal or INPUT_REQUIRED.
"""

from __future__ import annotations

from agente.config import Settings
from agente.handlers import Handlers, stub_continuation_handler
from agente.mcp_host import McpClient
from agente.skills.reservar_sala import make_reservar_sala_handler


def build_handlers(settings: Settings) -> Handlers:
    client = McpClient(settings.mcp_url)
    return Handlers(
        new_task=make_reservar_sala_handler(client),
        continuation=stub_continuation_handler,
        aclose=client.aclose,
    )
