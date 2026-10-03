"""Registration hook where the skill (F08) and the bridge (F09) plug in.

Contract:
- F08 replaces `new_task` with the `reservar-sala` skill handler.
- F09 replaces `continuation` with the pause/resume bridge.
- Shared resources (e.g. F06's MCP client) are built inside `build_handlers`,
  never at import time, and released through `Handlers.aclose`, which the app
  awaits on shutdown.
- A handler is `async (RequestContext, TaskHandle) -> None` and must leave the
  Task terminal or INPUT_REQUIRED.
"""

from __future__ import annotations

from agente.config import Settings
from agente.handlers import Handlers, stub_continuation_handler, stub_new_task_handler


def build_handlers(settings: Settings) -> Handlers:
    return Handlers(new_task=stub_new_task_handler, continuation=stub_continuation_handler)
