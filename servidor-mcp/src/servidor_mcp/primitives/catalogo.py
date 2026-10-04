"""F02: tool ``listar_salas`` and static resource ``politica://uso``."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel

from servidor_mcp import mensagens
from servidor_mcp.dominio import Dominio

POLITICA_URI = "politica://uso"
POLITICA_MIME_TYPE = "text/markdown"


class SalaOut(BaseModel):
    id: str
    nome: str
    capacidade: int
    recursos: list[str]


class ListaDeSalas(BaseModel):
    salas: list[SalaOut]


def register(server: MCPServer, dominio: Dominio) -> None:
    @server.tool(
        name="listar_salas",
        description=mensagens.DESCRICAO_LISTAR_SALAS,
        structured_output=True,
    )
    def listar_salas() -> ListaDeSalas:
        return ListaDeSalas(salas=[SalaOut(**sala.as_dict()) for sala in dominio.catalogo])

    @server.resource(
        POLITICA_URI,
        name=mensagens.POLITICA_NOME,
        title=mensagens.POLITICA_TITULO,
        description=mensagens.POLITICA_DESCRICAO,
        mime_type=POLITICA_MIME_TYPE,
    )
    def politica_de_uso() -> str:
        return dominio.politica.texto
