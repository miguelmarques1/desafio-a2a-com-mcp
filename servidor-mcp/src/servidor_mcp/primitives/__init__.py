"""Registration hook for MCP primitives (tools and resources).

Contract: each of F02-F05 adds a module in this package exposing
``register(server, dominio)`` and appends it to ``REGISTRARS``. The tuple order
defines the ``tools/list`` order (F02 listar_salas, F03 consultar_disponibilidade,
F04/F05 reservar_sala). Registrars receive the ``MCPServer`` and the ``Dominio``
and must not keep module-level state.
"""

from __future__ import annotations

from collections.abc import Callable

from mcp.server.mcpserver import MCPServer

from servidor_mcp.dominio import Dominio

Registrar = Callable[[MCPServer, Dominio], None]

REGISTRARS: tuple[Registrar, ...] = ()
