"""Registration hook for MCP primitives (tools and resources).

Contract: each primitive module in this package exposes ``register(server, dominio)``
and is listed in ``REGISTRARS``. The tuple order defines the ``tools/list`` order
(listar_salas, consultar_disponibilidade, reservar_sala). Registrars receive the ``MCPServer`` and the ``Dominio``
and must not keep module-level state.
"""

from __future__ import annotations

from collections.abc import Callable

from mcp.server.mcpserver import MCPServer

from servidor_mcp.dominio import Dominio
from servidor_mcp.primitives import catalogo, consultar_disponibilidade, reservar_sala

Registrar = Callable[[MCPServer, Dominio], None]

REGISTRARS: tuple[Registrar, ...] = (
    catalogo.register,
    consultar_disponibilidade.register,
    reservar_sala.register,
)
