"""Fixed-format parser for `reservar sala=<id> inicio=<iso8601> fim=<iso8601> responsavel=<nome>`.

Shape only: room ids, timestamps and policy are the MCP server's decision, never checked here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERN = re.compile(r"reservar +sala=(\S+) +inicio=(\S+) +fim=(\S+) +responsavel=(.*)")


@dataclass(frozen=True)
class ReservationRequest:
    sala: str
    inicio: str
    fim: str
    responsavel: str

    def arguments(self) -> dict[str, str]:
        return {
            "sala": self.sala,
            "inicio": self.inicio,
            "fim": self.fim,
            "responsavel": self.responsavel,
        }


def parse_reservation_request(text: str) -> ReservationRequest | None:
    text = text.strip()
    if "\r" in text or "\n" in text:
        return None
    match = _PATTERN.fullmatch(text)
    if match is None:
        return None
    sala, inicio, fim, responsavel = match.groups()
    responsavel = responsavel.strip()
    if not responsavel:
        return None
    return ReservationRequest(sala, inicio, fim, responsavel)
