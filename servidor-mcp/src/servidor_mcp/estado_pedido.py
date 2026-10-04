"""Payload sealed inside ``requestState`` (pure: encode, decode, expiry)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from servidor_mcp.regras import PedidoValidado
from servidor_mcp.seguranca import TTL_ESTADO_SEGUNDOS

VERSAO_ESTADO = 1
FERRAMENTA = "reservar_sala"
CHAVE_ESCOLHA = "reservar_sala:escolha_de_sala"
_MAX_ALTERNATIVAS = 3


@dataclass(frozen=True)
class EstadoDoPedido:
    sala: str
    inicio: str
    fim: str
    responsavel: str
    alternativas: tuple[str, ...]
    expira: int
    v: int = VERSAO_ESTADO
    ferramenta: str = FERRAMENTA
    chave: str = CHAVE_ESCOLHA


def novo_estado(
    pedido: PedidoValidado, responsavel: str, alternativas: tuple[str, ...]
) -> EstadoDoPedido:
    return EstadoDoPedido(
        sala=pedido.sala.id,
        inicio=pedido.inicio,
        fim=pedido.fim,
        responsavel=responsavel,
        alternativas=alternativas,
        expira=int(time.time()) + TTL_ESTADO_SEGUNDOS,
    )


def codificar(estado: EstadoDoPedido) -> str:
    documento = {
        "v": estado.v,
        "ferramenta": estado.ferramenta,
        "sala": estado.sala,
        "inicio": estado.inicio,
        "fim": estado.fim,
        "responsavel": estado.responsavel,
        "alternativas": list(estado.alternativas),
        "chave": estado.chave,
        "expira": estado.expira,
    }
    return json.dumps(documento, separators=(",", ":"), ensure_ascii=True)


def _inteiro(valor: object) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def decodificar(texto: str) -> EstadoDoPedido | None:
    """Strict inverse of ``codificar``; any deviation yields None (never raises)."""
    try:
        documento = json.loads(texto)
    except (TypeError, ValueError):
        return None
    if not isinstance(documento, dict):
        return None
    versao = documento.get("v")
    if not _inteiro(versao) or versao != VERSAO_ESTADO:
        return None
    campos = ("ferramenta", "sala", "inicio", "fim", "responsavel", "chave")
    if not all(isinstance(documento.get(campo), str) for campo in campos):
        return None
    alternativas = documento.get("alternativas")
    if (
        not isinstance(alternativas, list)
        or not 1 <= len(alternativas) <= _MAX_ALTERNATIVAS
        or not all(isinstance(item, str) for item in alternativas)
    ):
        return None
    expira = documento.get("expira")
    if not _inteiro(expira):
        return None
    return EstadoDoPedido(
        v=versao,
        ferramenta=documento["ferramenta"],
        sala=documento["sala"],
        inicio=documento["inicio"],
        fim=documento["fim"],
        responsavel=documento["responsavel"],
        alternativas=tuple(alternativas),
        chave=documento["chave"],
        expira=expira,
    )


def expirado(estado: EstadoDoPedido) -> bool:
    return time.time() >= estado.expira
