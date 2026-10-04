"""F03: tool ``consultar_disponibilidade``."""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult
from pydantic import BaseModel

from servidor_mcp import mensagens
from servidor_mcp.dominio import Dominio
from servidor_mcp.regras import FalhaDeValidacao, conflitos_no_intervalo, validar_pedido
from servidor_mcp.resultados import erro_de_execucao


class ConflitoOut(BaseModel):
    id: str
    inicio: str
    fim: str
    responsavel: str


class Disponibilidade(BaseModel):
    sala: str
    livre: bool
    conflitos: list[ConflitoOut]


def register(server: MCPServer, dominio: Dominio) -> None:
    @server.tool(
        name="consultar_disponibilidade",
        description=mensagens.DESCRICAO_CONSULTAR_DISPONIBILIDADE,
        structured_output=True,
    )
    def consultar_disponibilidade(
        sala: str, inicio: str, fim: str
    ) -> Annotated[CallToolResult, Disponibilidade]:
        pedido = validar_pedido(dominio.catalogo, sala, inicio, fim)
        if isinstance(pedido, FalhaDeValidacao):
            return erro_de_execucao(pedido.mensagem)
        conflitos = conflitos_no_intervalo(dominio.reservas, pedido.sala.id, pedido.intervalo)
        return Disponibilidade(
            sala=pedido.sala.id,
            livre=not conflitos,
            conflitos=[
                ConflitoOut(id=c.id, inicio=c.inicio, fim=c.fim, responsavel=c.responsavel)
                for c in conflitos
            ],
        )
