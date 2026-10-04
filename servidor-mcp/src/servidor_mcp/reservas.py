"""Reservation domain core (id generation and atomic check-then-append)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from servidor_mcp.dominio import LivroDeReservas, Reserva
from servidor_mcp.regras import PedidoValidado, conflitos_no_intervalo

_ID = re.compile(r"res-([0-9]+)", re.ASCII)


@dataclass(frozen=True)
class SalaOcupada:
    conflitos: tuple[Reserva, ...]


def proximo_id(reservas: Iterable[Reserva]) -> str:
    """Highest numeric ``res-N`` suffix plus one, at least 4 digits; other ids are ignored."""
    maior = 0
    for reserva in reservas:
        achado = _ID.fullmatch(reserva.id)
        if achado:
            maior = max(maior, int(achado.group(1)))
    return f"res-{maior + 1:04d}"


def registrar_se_livre(
    livro: LivroDeReservas, pedido: PedidoValidado, responsavel: str
) -> Reserva | SalaOcupada:
    """Check conflicts, compute the id and append in one exclusive section of the ledger."""
    with livro.bloqueio():
        conflitos = conflitos_no_intervalo(livro, pedido.sala.id, pedido.intervalo)
        if conflitos:
            return SalaOcupada(conflitos)
        reserva = Reserva(
            id=proximo_id(livro.todas()),
            sala=pedido.sala.id,
            inicio=pedido.inicio,
            fim=pedido.fim,
            responsavel=responsavel,
        )
        livro.adicionar(reserva)
        return reserva
