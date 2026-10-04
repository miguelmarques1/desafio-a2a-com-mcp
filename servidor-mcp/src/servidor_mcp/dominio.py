"""In-memory domain types."""

from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class Sala:
    id: str
    nome: str
    capacidade: int
    recursos: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "capacidade": self.capacidade,
            "recursos": list(self.recursos),
        }


@dataclass(frozen=True)
class Reserva:
    id: str
    sala: str
    inicio: str
    fim: str
    responsavel: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "sala": self.sala,
            "inicio": self.inicio,
            "fim": self.fim,
            "responsavel": self.responsavel,
        }


@dataclass(frozen=True)
class Politica:
    texto: str
    versao: str


class CatalogoDeSalas:
    def __init__(self, salas: Iterable[Sala]):
        self._salas = tuple(salas)
        self._index = {s.id: s for s in self._salas}

    def __iter__(self) -> Iterator[Sala]:
        return iter(self._salas)

    def __len__(self) -> int:
        return len(self._salas)

    def __contains__(self, sala_id: object) -> bool:
        return sala_id in self._index

    def get(self, sala_id: str) -> Sala | None:
        return self._index.get(sala_id)

    def todas(self) -> tuple[Sala, ...]:
        return self._salas


class LivroDeReservas:
    def __init__(self, reservas: Iterable[Reserva] = ()):
        self._lock = threading.RLock()
        self._reservas: list[Reserva] = list(reservas)

    @contextmanager
    def bloqueio(self) -> Iterator[None]:
        """Exclusive section: other threads wait; ledger methods may be called inside it."""
        with self._lock:
            yield

    def todas(self) -> tuple[Reserva, ...]:
        with self._lock:
            return tuple(self._reservas)

    def da_sala(self, sala_id: str) -> tuple[Reserva, ...]:
        with self._lock:
            return tuple(r for r in self._reservas if r.sala == sala_id)

    def adicionar(self, reserva: Reserva) -> None:
        with self._lock:
            if any(r.id == reserva.id for r in self._reservas):
                raise ValueError(f"Reserva duplicada: {reserva.id}")
            self._reservas.append(reserva)

    def __len__(self) -> int:
        with self._lock:
            return len(self._reservas)


@dataclass(frozen=True)
class Dominio:
    catalogo: CatalogoDeSalas
    reservas: LivroDeReservas
    politica: Politica
