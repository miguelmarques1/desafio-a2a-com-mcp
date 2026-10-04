"""F04 contracts consumed by F05/F08 and provided by F01/F03 (server side)."""

import json
import secrets

import pytest
from pydantic_core import to_json

from servidor_mcp.primitives.reservar_sala import ReservaOut
from servidor_mcp.regras import FalhaDeValidacao, validar_pedido

RESERVAR = "reservar_sala"
CONSULTAR = "consultar_disponibilidade"


def h(hora, dia="2026-11-03"):
    return f"{dia}T{hora}:00-03:00"


def reservar(client, mcp_post, sala, inicio, fim, responsavel="Doc", **options):
    args = {"sala": sala, "inicio": inicio, "fim": fim, "responsavel": responsavel}
    options.setdefault("id", secrets.token_hex(6))
    r = mcp_post(client, "tools/call", {"name": RESERVAR, "arguments": args}, **options)
    assert r.status_code == 200
    return r.json()["result"]


def consultar(client, mcp_post, sala, inicio, fim):
    args = {"sala": sala, "inicio": inicio, "fim": fim}
    return mcp_post(client, "tools/call", {"name": CONSULTAR, "arguments": args}).json()["result"]


def test_first_reservation_continues_foundation_ledger_and_policy_version(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    sc = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))["structuredContent"]
    assert sc["reserva"] == "res-0003"
    assert sc["politica"] == dominio.politica.versao
    assert [r.id for r in dominio.reservas.todas()] == ["res-0001", "res-0002", "res-0003"]


CASOS = [
    ("sala-delorean", h("09:00"), h("10:00")),
    ("sala-aquario", "2026-11-03T09:00:00", h("10:00")),
    ("sala-aquario", h("09:00"), "ontem"),
    ("sala-aquario", h("10:00"), h("09:00")),
    ("sala-aquario", h("07:00"), h("08:00")),
    ("sala-aquario", h("19:00"), h("21:00")),
    ("sala-aquario", h("09:00"), h("12:00")),
]


@pytest.mark.parametrize("sala,inicio,fim", CASOS)
def test_reservar_sala_errors_equal_f03_validation_messages(fresh_app, mcp_post, sala, inicio, fim):
    client, _, dominio = fresh_app()
    esperado = validar_pedido(dominio.catalogo, sala, inicio, fim)
    assert isinstance(esperado, FalhaDeValidacao)
    a = reservar(client, mcp_post, sala, inicio, fim)
    b = consultar(client, mcp_post, sala, inicio, fim)
    assert a["isError"] is True and b["isError"] is True
    assert a["content"][0]["text"] == b["content"][0]["text"] == esperado.mensagem


def test_retry_reservation_created_by_f04_routine(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    first = reservar(client, mcp_post, "sala-garagem", h("14:00"), h("15:00"), "Marty")
    if first.get("resultType") != "input_required":
        pytest.skip("F05 MRTR flow not implemented yet")
    key = next(iter(first["inputRequests"]))
    args = {"sala": "sala-garagem", "inicio": h("14:00"), "fim": h("15:00"), "responsavel": "Marty"}
    params = {
        "name": RESERVAR,
        "arguments": args,
        "inputResponses": {key: {"action": "accept", "content": {"sala": "sala-fusca"}}},
        "requestState": first["requestState"],
    }
    done = mcp_post(client, "tools/call", params).json()["result"]["structuredContent"]
    assert done["reserva"] == "res-0003" and done["politica"] == "2026-11-01"
    q = consultar(client, mcp_post, "sala-fusca", h("14:00"), h("15:00"))["structuredContent"]
    assert q["livre"] is False and q["conflitos"][0]["id"] == "res-0003"


def test_structured_content_fields_are_the_artifact_source(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    ini, fim = "2026-11-03T12:00:00Z", "2026-11-03T13:00:00Z"
    r = reservar(client, mcp_post, "sala-aquario", ini, fim, "Doc")
    sc = r["structuredContent"]
    for chave, valor in {"sala": "sala-aquario", "inicio": ini, "fim": fim, "responsavel": "Doc"}.items():
        assert isinstance(sc[chave], str) and sc[chave] == valor
    assert isinstance(sc["reserva"], str)
    assert json.loads(r["content"][0]["text"]) == sc


def test_iserror_text_is_plain_message_for_agent_relay(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = reservar(client, mcp_post, "sala-delorean", h("09:00"), h("10:00"))
    assert r["isError"] is True
    assert r["content"] == [{"type": "text", "text": "Sala inexistente: sala-delorean"}]


def test_decline_result_shape_from_reservaout(repo_root):
    path = repo_root / "exemplos" / "wire" / "11-tools-call-retry-recusa.json"
    result = json.loads(path.read_text(encoding="utf-8"))["response"]["body"]["result"]
    out = ReservaOut(reservado=False, motivo="recusado")
    assert to_json(out, indent=2).decode() == result["content"][0]["text"]
    assert out.model_dump(mode="json") == result["structuredContent"]
