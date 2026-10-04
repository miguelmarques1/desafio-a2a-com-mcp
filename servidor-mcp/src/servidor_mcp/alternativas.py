"""F05: pure alternatives rule (no MCP types, no I/O, no clock)."""

from __future__ import annotations

from servidor_mcp.dominio import CatalogoDeSalas, LivroDeReservas
from servidor_mcp.regras import PedidoValidado, conflitos_no_intervalo

LIMITE_ALTERNATIVAS = 3


def calcular_alternativas(
    catalogo: CatalogoDeSalas, reservas: LivroDeReservas, pedido: PedidoValidado
) -> tuple[str, ...]:
    """Other rooms at least as large as the requested one and free in the whole interval."""
    candidatas = [
        sala
        for sala in catalogo.todas()
        if sala.id != pedido.sala.id
        and sala.capacidade >= pedido.sala.capacidade
        and not conflitos_no_intervalo(reservas, sala.id, pedido.intervalo)
    ]
    candidatas.sort(key=lambda sala: (sala.capacidade, sala.id))
    return tuple(sala.id for sala in candidatas[:LIMITE_ALTERNATIVAS])
