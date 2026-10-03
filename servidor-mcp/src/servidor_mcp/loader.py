"""Read-only loading and validation of the three dados/ files."""

from __future__ import annotations

import json
from pathlib import Path

from servidor_mcp import mensagens
from servidor_mcp.dominio import CatalogoDeSalas, Dominio, LivroDeReservas, Politica, Reserva, Sala


class DataLoadError(Exception):
    def __init__(self, arquivo: str, motivo: str):
        self.arquivo = arquivo
        self.motivo = motivo
        super().__init__(mensagens.FALHA_CARREGAR_DADOS.format(arquivo=arquivo, motivo=motivo))


class PolicyVersionMissingError(Exception):
    def __init__(self) -> None:
        super().__init__(mensagens.POLITICA_SEM_VERSAO)


def _read_bytes(dados_dir: Path, nome: str) -> bytes:
    try:
        return (dados_dir / nome).read_bytes()
    except OSError as exc:
        raise DataLoadError(nome, exc.strerror or str(exc)) from exc


def _decode(nome: str, raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise DataLoadError(nome, "nao esta em UTF-8") from None


def _load_list(dados_dir: Path, nome: str) -> list:
    texto = _decode(nome, _read_bytes(dados_dir, nome))
    try:
        data = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise DataLoadError(nome, f"JSON invalido: {exc}") from None
    if not isinstance(data, list):
        raise _invalid(nome, "esperado uma lista")
    return data


def _invalid(nome: str, detalhe: str) -> DataLoadError:
    return DataLoadError(nome, f"formato invalido: {detalhe}")


def _load_salas(dados_dir: Path) -> CatalogoDeSalas:
    nome = "salas.json"
    salas: list[Sala] = []
    seen: set[str] = set()
    for i, item in enumerate(_load_list(dados_dir, nome)):
        if not isinstance(item, dict):
            raise _invalid(nome, f"item {i} nao e um objeto")
        sid = item.get("id")
        if not isinstance(sid, str) or not sid:
            raise _invalid(nome, f"item {i}: id deve ser texto nao vazio")
        if sid in seen:
            raise _invalid(nome, f"id duplicado: {sid}")
        seen.add(sid)
        if not isinstance(item.get("nome"), str):
            raise _invalid(nome, f"{sid}: nome deve ser texto")
        cap = item.get("capacidade")
        if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
            raise _invalid(nome, f"{sid}: capacidade deve ser inteiro >= 1")
        rec = item.get("recursos")
        if not isinstance(rec, list) or not all(isinstance(r, str) for r in rec):
            raise _invalid(nome, f"{sid}: recursos deve ser lista de textos")
        salas.append(Sala(sid, item["nome"], cap, tuple(rec)))
    return CatalogoDeSalas(salas)


def _load_reservas(dados_dir: Path) -> LivroDeReservas:
    nome = "reservas.json"
    reservas: list[Reserva] = []
    seen: set[str] = set()
    for i, item in enumerate(_load_list(dados_dir, nome)):
        if not isinstance(item, dict):
            raise _invalid(nome, f"item {i} nao e um objeto")
        for campo in ("id", "sala", "inicio", "fim", "responsavel"):
            valor = item.get(campo)
            if not isinstance(valor, str) or (campo == "id" and not valor):
                raise _invalid(nome, f"item {i}: {campo} deve ser texto")
        if item["id"] in seen:
            raise _invalid(nome, f"id duplicado: {item['id']}")
        seen.add(item["id"])
        reservas.append(
            Reserva(item["id"], item["sala"], item["inicio"], item["fim"], item["responsavel"])
        )
    return LivroDeReservas(reservas)


def _load_politica(dados_dir: Path) -> Politica:
    nome = "politica-de-uso.md"
    texto = _decode(nome, _read_bytes(dados_dir, nome))
    primeira = texto.split("\n", 1)[0]
    if primeira.endswith("\r"):
        primeira = primeira[:-1]
    if not primeira.startswith("versao:"):
        raise PolicyVersionMissingError()
    versao = primeira[len("versao:"):].strip()
    if not versao:
        raise PolicyVersionMissingError()
    return Politica(texto=texto, versao=versao)


def load_dominio(dados_dir: str | Path) -> Dominio:
    dados_dir = Path(dados_dir)
    catalogo = _load_salas(dados_dir)
    reservas = _load_reservas(dados_dir)
    politica = _load_politica(dados_dir)
    return Dominio(catalogo=catalogo, reservas=reservas, politica=politica)
