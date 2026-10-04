"""Pure policy rules shared by every booking path (no MCP types, no I/O, no clock)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from servidor_mcp import mensagens
from servidor_mcp.dominio import CatalogoDeSalas, LivroDeReservas, Reserva, Sala

POLITICA_OFFSET = timezone(timedelta(hours=-3))
JANELA_INICIO = time(8, 0, 0)
JANELA_FIM = time(20, 0, 0)
DURACAO_MAXIMA = timedelta(minutes=120)

_HORARIO = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?"
    r"(?:(Z)|([+-])(\d{2}):(\d{2}))",
    re.ASCII,
)


def interpretar_horario(valor: str) -> datetime | None:
    """Parse an ISO 8601 timestamp with explicit offset into an aware datetime in -03:00."""
    m = _HORARIO.fullmatch(valor)
    if m is None:
        return None
    ano, mes, dia, hora, minuto, segundo, fracao, z, sinal, oh, om = m.groups()
    try:
        if z:
            tz = timezone.utc
        else:
            oh_i, om_i = int(oh), int(om)
            if oh_i > 23 or om_i > 59:
                return None
            delta = timedelta(hours=oh_i, minutes=om_i)
            tz = timezone(-delta if sinal == "-" else delta)
        local = datetime(
            int(ano),
            int(mes),
            int(dia),
            int(hora),
            int(minuto),
            int(segundo or 0),
            int((fracao or "").ljust(6, "0")),
            tzinfo=tz,
        )
        return local.astimezone(POLITICA_OFFSET)
    except (ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class Intervalo:
    inicio: datetime
    fim: datetime

    def sobrepoe(self, outro: Intervalo) -> bool:
        return self.inicio < outro.fim and outro.inicio < self.fim


@dataclass(frozen=True)
class PedidoValidado:
    sala: Sala
    inicio: str
    fim: str
    intervalo: Intervalo


@dataclass(frozen=True)
class FalhaDeValidacao:
    regra: str
    mensagem: str


def validar_pedido(
    catalogo: CatalogoDeSalas, sala: str, inicio: str, fim: str
) -> PedidoValidado | FalhaDeValidacao:
    """Apply the PRD rules in order; the first failure wins."""
    sala_obj = catalogo.get(sala)
    if sala_obj is None:
        return FalhaDeValidacao("sala_inexistente", mensagens.SALA_INEXISTENTE.format(sala=sala))

    inicio_dt = interpretar_horario(inicio)
    if inicio_dt is None:
        return FalhaDeValidacao("horario_invalido", mensagens.HORARIO_INVALIDO.format(valor=inicio))
    fim_dt = interpretar_horario(fim)
    if fim_dt is None:
        return FalhaDeValidacao("horario_invalido", mensagens.HORARIO_INVALIDO.format(valor=fim))

    if fim_dt <= inicio_dt:
        return FalhaDeValidacao("intervalo_invalido", mensagens.INTERVALO_INVALIDO)

    if (
        inicio_dt.date() != fim_dt.date()
        or inicio_dt.time() < JANELA_INICIO
        or fim_dt.time() > JANELA_FIM
    ):
        return FalhaDeValidacao("fora_da_janela", mensagens.FORA_DA_JANELA)

    if fim_dt - inicio_dt > DURACAO_MAXIMA:
        return FalhaDeValidacao("duracao_acima_do_limite", mensagens.DURACAO_ACIMA_DO_LIMITE)

    return PedidoValidado(sala_obj, inicio, fim, Intervalo(inicio_dt, fim_dt))


def conflitos_no_intervalo(
    reservas: LivroDeReservas, sala_id: str, intervalo: Intervalo
) -> tuple[Reserva, ...]:
    """Ledger reservations of the room overlapping the interval, ordered by (start instant, id)."""
    achados: list[tuple[datetime, str, Reserva]] = []
    for reserva in reservas.da_sala(sala_id):
        inicio = interpretar_horario(reserva.inicio)
        fim = interpretar_horario(reserva.fim)
        if inicio is None or fim is None:
            continue
        if intervalo.sobrepoe(Intervalo(inicio, fim)):
            achados.append((inicio, reserva.id, reserva))
    achados.sort(key=lambda t: (t[0], t[1]))
    return tuple(r for _, _, r in achados)
