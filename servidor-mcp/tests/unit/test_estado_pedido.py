import json
import time

import pytest

from servidor_mcp.dominio import CatalogoDeSalas, Sala
from servidor_mcp.estado_pedido import (
    CHAVE_ESCOLHA,
    EstadoDoPedido,
    codificar,
    decodificar,
    expirado,
    novo_estado,
)
from servidor_mcp.regras import validar_pedido

INI, FIM = "2026-11-03T14:00:00-03:00", "2026-11-03T15:00:00-03:00"


def estado(**mudancas):
    base = dict(
        sala="sala-garagem",
        inicio=INI,
        fim=FIM,
        responsavel="Marty",
        alternativas=("sala-fusca", "sala-mirante"),
        expira=1793721600,
    )
    return EstadoDoPedido(**{**base, **mudancas})


def test_round_trip():
    assert decodificar(codificar(estado())) == estado()


def test_encoding_is_compact_ascii_and_ordered():
    texto = codificar(estado(responsavel="Zé"))
    assert " " not in texto and "\\u00e9" in texto
    assert list(json.loads(texto)) == [
        "v", "ferramenta", "sala", "inicio", "fim", "responsavel", "alternativas", "chave", "expira",
    ]


def test_encoding_matches_spec_example():
    assert codificar(estado()) == (
        '{"v":1,"ferramenta":"reservar_sala","sala":"sala-garagem","inicio":"2026-11-03T14:00:00-03:00",'
        '"fim":"2026-11-03T15:00:00-03:00","responsavel":"Marty","alternativas":["sala-fusca","sala-mirante"],'
        '"chave":"reservar_sala:escolha_de_sala","expira":1793721600}'
    )


def test_novo_estado_stamps_expiry_600s(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1000.7)
    catalogo = CatalogoDeSalas([Sala("sala-garagem", "G", 12, ())])
    pedido = validar_pedido(catalogo, "sala-garagem", INI, FIM)
    e = novo_estado(pedido, " Marty ", ("sala-fusca",))
    assert e.expira == 1600
    assert e.chave == CHAVE_ESCOLHA and e.ferramenta == "reservar_sala"
    assert (e.sala, e.inicio, e.fim, e.responsavel) == ("sala-garagem", INI, FIM, " Marty ")


def test_expirado_boundary(monkeypatch):
    e = estado(expira=1600)
    monkeypatch.setattr(time, "time", lambda: 1599.9)
    assert expirado(e) is False
    monkeypatch.setattr(time, "time", lambda: 1600)
    assert expirado(e) is True


@pytest.mark.parametrize("texto", ["x", "[]", "{}", "null", "5", ""])
def test_decodificar_rejects_garbage(texto):
    assert decodificar(texto) is None


def test_decodificar_rejects_non_string_input():
    assert decodificar(None) is None


def _doc(**mudancas):
    d = json.loads(codificar(estado()))
    d.update(mudancas)
    return json.dumps(d)


def _sem_chave():
    d = json.loads(codificar(estado()))
    del d["chave"]
    return json.dumps(d)


@pytest.mark.parametrize(
    "texto",
    [
        _doc(v=2),
        _doc(v=True),
        _doc(expira="1"),
        _doc(expira=True),
        _doc(alternativas=[]),
        _doc(alternativas=["a", "b", "c", "d"]),
        _doc(alternativas=[1]),
        _doc(alternativas="sala-fusca"),
        _doc(sala=5),
        _sem_chave(),
    ],
)
def test_decodificar_rejects_wrong_version_or_types(texto):
    assert decodificar(texto) is None
