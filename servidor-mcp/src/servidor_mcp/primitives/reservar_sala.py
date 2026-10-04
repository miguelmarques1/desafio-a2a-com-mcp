"""F04/F05: tool ``reservar_sala``, the reservation creation routine and the MRTR conflict flow."""

from __future__ import annotations

import logging
from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, InputRequiredResult
from pydantic import BaseModel

from servidor_mcp import mensagens
from servidor_mcp.alternativas import calcular_alternativas
from servidor_mcp.dominio import Dominio, Reserva
from servidor_mcp.estado_pedido import novo_estado
from servidor_mcp.mrtr import (
    estado_da_rodada,
    exigir_elicitacao_form,
    pedir_escolha,
    resposta_para,
)
from servidor_mcp.regras import FalhaDeValidacao, PedidoValidado, validar_pedido
from servidor_mcp.reservas import SalaOcupada, registrar_se_livre
from servidor_mcp.resultados import erro_de_execucao

logger = logging.getLogger(__name__)


class ReservaOut(BaseModel):
    reserva: str | None = None
    reservado: bool = True
    sala: str | None = None
    inicio: str | None = None
    fim: str | None = None
    responsavel: str | None = None
    politica: str | None = None
    motivo: str | None = None


def reserva_confirmada(reserva: Reserva, versao: str) -> ReservaOut:
    return ReservaOut(
        reserva=reserva.id,
        reservado=True,
        sala=reserva.sala,
        inicio=reserva.inicio,
        fim=reserva.fim,
        responsavel=reserva.responsavel,
        politica=versao,
        motivo=None,
    )


def criar_reserva(
    dominio: Dominio, pedido: PedidoValidado, responsavel: str
) -> ReservaOut | SalaOcupada | CallToolResult:
    """Create the reservation for an already validated request; never raises."""
    try:
        criada = registrar_se_livre(dominio.reservas, pedido, responsavel)
    except Exception:
        logger.exception("Falha ao registrar reserva")
        return erro_de_execucao(mensagens.FALHA_INTERNA_RESERVA)
    if isinstance(criada, SalaOcupada):
        return criada
    return reserva_confirmada(criada, dominio.politica.versao)


def reserva_nao_realizada(motivo: str) -> ReservaOut:
    return ReservaOut(reservado=False, motivo=motivo)


def _oferecer_alternativas(
    dominio: Dominio, ctx: Context, pedido: PedidoValidado, responsavel: str
) -> CallToolResult | InputRequiredResult:
    alternativas = calcular_alternativas(dominio.catalogo, dominio.reservas, pedido)
    if not alternativas:
        return erro_de_execucao(mensagens.SEM_ALTERNATIVAS)
    exigir_elicitacao_form(ctx)
    return pedir_escolha(novo_estado(pedido, responsavel, alternativas))


def _retomar(
    dominio: Dominio, ctx: Context
) -> ReservaOut | CallToolResult | InputRequiredResult:
    """Retry round: every value comes from the sealed payload, never from the tool arguments."""
    estado = estado_da_rodada(ctx)
    resposta = resposta_para(ctx, estado.chave)
    if resposta.action == "decline":
        return reserva_nao_realizada("recusado")
    if resposta.action == "cancel":
        return reserva_nao_realizada("cancelado")

    escolhida = (resposta.content or {}).get("sala")
    if isinstance(escolhida, str) and escolhida in estado.alternativas:
        pedido = validar_pedido(dominio.catalogo, escolhida, estado.inicio, estado.fim)
        if isinstance(pedido, FalhaDeValidacao):
            return erro_de_execucao(pedido.mensagem)
        resultado = criar_reserva(dominio, pedido, estado.responsavel)
        if not isinstance(resultado, SalaOcupada):
            return resultado

    original = validar_pedido(dominio.catalogo, estado.sala, estado.inicio, estado.fim)
    if isinstance(original, FalhaDeValidacao):
        return erro_de_execucao(original.mensagem)
    return _oferecer_alternativas(dominio, ctx, original, estado.responsavel)


def register(server: MCPServer, dominio: Dominio) -> None:
    @server.tool(
        name="reservar_sala",
        description=mensagens.DESCRICAO_RESERVAR_SALA,
        structured_output=True,
    )
    def reservar_sala(
        sala: str, inicio: str, fim: str, responsavel: str, ctx: Context
    ) -> Annotated[CallToolResult, ReservaOut] | InputRequiredResult:
        if ctx.request_state is not None:
            return _retomar(dominio, ctx)
        pedido = validar_pedido(dominio.catalogo, sala, inicio, fim)
        if isinstance(pedido, FalhaDeValidacao):
            return erro_de_execucao(pedido.mensagem)
        resultado = criar_reserva(dominio, pedido, responsavel)
        if isinstance(resultado, SalaOcupada):
            return _oferecer_alternativas(dominio, ctx, pedido, responsavel)
        return resultado
