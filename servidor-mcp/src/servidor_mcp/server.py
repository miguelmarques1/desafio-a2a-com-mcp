"""MCPServer factory."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mcp.server.mcpserver import MCPServer

from servidor_mcp.dominio import Dominio
from servidor_mcp.primitives import REGISTRARS, Registrar

SERVER_NAME = "central-de-salas"
SERVER_VERSION = "1.0.0"


def build_server(
    dominio: Dominio,
    *,
    request_state_security: Any = None,
    registrars: Sequence[Registrar] = REGISTRARS,
) -> MCPServer:
    kwargs: dict[str, Any] = {}
    if request_state_security is not None:
        kwargs["request_state_security"] = request_state_security
    server = MCPServer(name=SERVER_NAME, version=SERVER_VERSION, log_level="WARNING", **kwargs)
    for registrar in registrars:
        registrar(server, dominio)
    return server
