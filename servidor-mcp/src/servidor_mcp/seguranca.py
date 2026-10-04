"""Request-state secret validation and the SDK sealing policy."""

from __future__ import annotations

import re

from mcp.server.mcpserver import RequestStateSecurity

from servidor_mcp import mensagens

TTL_ESTADO_SEGUNDOS = 600

_SEGREDO_HEX = re.compile(r"[0-9a-fA-F]{64,}")


class SegredoInvalidoError(Exception):
    def __init__(self) -> None:
        super().__init__(mensagens.SEGREDO_INVALIDO)


def validar_segredo(valor: str | None) -> str:
    """Return the secret unchanged when it has at least 64 hex characters."""
    if valor is None or _SEGREDO_HEX.fullmatch(valor) is None:
        raise SegredoInvalidoError
    return valor


def politica_de_estado(segredo: str) -> RequestStateSecurity:
    return RequestStateSecurity(keys=[segredo], ttl=TTL_ESTADO_SEGUNDOS)
