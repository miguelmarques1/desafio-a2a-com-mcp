"""Cross-feature criteria of PRD Section 9 that name F05 (server side)."""

import secrets

import pytest

from servidor_mcp.alternativas import calcular_alternativas
from servidor_mcp.regras import validar_pedido

TOOL = "reservar_sala"
CHAVE = "reservar_sala:escolha_de_sala"
FORM = {"elicitation": {"form": {}}}


def h(hora, dia="2026-11-03"):
    return f"{dia}T{hora}:00-03:00"


def reservar(client, mcp_post, sala, inicio, fim, responsavel="Doc", **options):
    options.setdefault("id", secrets.token_hex(6))
    args = {"sala": sala, "inicio": inicio, "fim": fim, "responsavel": responsavel}
    return mcp_post(client, "tools/call", {"name": TOOL, "arguments": args}, **options)


def retomar(client, mcp_post, args, chave, resposta, estado, **options):
    options.setdefault("id", secrets.token_hex(6))
    params = {
        "name": TOOL,
        "arguments": args,
        "inputResponses": {chave: resposta},
        "requestState": estado,
    }
    return mcp_post(client, "tools/call", params, **options)


def enum_de(result):
    (pedido,) = result["inputRequests"].values()
    return pedido["params"]["requestedSchema"]["properties"]["sala"]["enum"]


GARAGEM = {"sala": "sala-garagem", "inicio": h("14:00"), "fim": h("15:00"), "responsavel": "Marty"}


def test_alternatives_respect_foundation_capacities(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    amostras = [
        ("sala-garagem", "14:00", "15:00"),
        ("sala-fusca", "16:00", "17:00"),
        ("sala-aquario", "09:00", "10:00"),
        ("sala-porao", "09:00", "10:00"),
    ]
    reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))
    reservar(client, mcp_post, "sala-porao", h("09:00"), h("10:00"))
    for sala, ini, fim in amostras:
        result = reservar(client, mcp_post, sala, h(ini), h(fim)).json()["result"]
        assert result["resultType"] == "input_required"
        minimo = dominio.catalogo.get(sala).capacidade
        assert all(dominio.catalogo.get(i).capacidade >= minimo for i in enum_de(result))


def test_32021_exactly_when_form_elicitation_missing(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    saidas = []
    for caps in (FORM, {}, {"elicitation": {}}, {"elicitation": {"url": {}}}, FORM):
        r = reservar(client, mcp_post, "sala-garagem", h("14:00"), h("15:00"), "Marty", caps=caps)
        corpo = r.json()
        saidas.append((r.status_code, corpo.get("error", {}).get("code"), corpo.get("result", {}).get("resultType")))
    assert saidas == [
        (200, None, "input_required"),
        (400, -32021, None),
        (400, -32021, None),
        (400, -32021, None),
        (200, None, "input_required"),
    ]


def test_alternatives_only_when_f03_reports_conflict(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    amostras = [
        ("sala-garagem", "14:00", "15:00"),
        ("sala-garagem", "15:00", "16:00"),
        ("sala-fusca", "16:30", "17:30"),
        ("sala-fusca", "17:00", "18:00"),
        ("sala-mirante", "09:00", "10:00"),
    ]
    for sala, ini, fim in amostras:
        consulta = mcp_post(
            client,
            "tools/call",
            {"name": "consultar_disponibilidade", "arguments": {"sala": sala, "inicio": h(ini), "fim": h(fim)}},
        ).json()["result"]["structuredContent"]
        result = reservar(client, mcp_post, sala, h(ini), h(fim), "Doc").json()["result"]
        if consulta["livre"]:
            assert result["resultType"] == "complete" and result["structuredContent"]["reservado"] is True
        else:
            assert consulta["conflitos"]
            assert result["resultType"] == "input_required"


def test_retry_reservation_created_by_f04_routine(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    inicial = reservar(client, mcp_post, **{k: GARAGEM[k] for k in ("sala", "inicio", "fim")}, responsavel="Marty")
    result = inicial.json()["result"]
    estado = result["requestState"]
    r = retomar(client, mcp_post, GARAGEM, CHAVE, {"action": "accept", "content": {"sala": "sala-fusca"}}, estado)
    sc = r.json()["result"]["structuredContent"]
    assert sc["reserva"] == "res-0003" and sc["politica"] == "2026-11-01"
    consulta = mcp_post(
        client,
        "tools/call",
        {"name": "consultar_disponibilidade", "arguments": {"sala": "sala-fusca", "inicio": h("14:00"), "fim": h("15:00")}},
    ).json()["result"]["structuredContent"]
    assert consulta["livre"] is False
    assert [c["id"] for c in consulta["conflitos"]] == ["res-0003"]


def test_enum_order_and_key_echo_contract(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    result = reservar(client, mcp_post, **{k: GARAGEM[k] for k in ("sala", "inicio", "fim")}, responsavel="Marty").json()["result"]
    pedido = validar_pedido(dominio.catalogo, "sala-garagem", h("14:00"), h("15:00"))
    assert enum_de(result) == list(calcular_alternativas(dominio.catalogo, dominio.reservas, pedido))
    (chave,) = result["inputRequests"]
    estado = result["requestState"]

    aceita = {"action": "accept", "content": {"sala": "sala-fusca"}}
    outra = retomar(client, mcp_post, GARAGEM, "qualquer:outra", aceita, estado)
    assert outra.status_code == 400 and outra.json()["error"]["code"] == -32602
    certa = retomar(client, mcp_post, GARAGEM, chave, aceita, estado)
    assert certa.json()["result"]["resultType"] == "complete"


def test_retry_with_new_id_and_byte_identical_state(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    result = reservar(
        client, mcp_post, **{k: GARAGEM[k] for k in ("sala", "inicio", "fim")}, responsavel="Marty", id="first"
    ).json()["result"]
    estado = result["requestState"]
    aceita = {"action": "accept", "content": {"sala": "sala-fusca"}}
    alterado = estado[:-1] + ("A" if estado[-1] != "A" else "B")
    assert retomar(client, mcp_post, GARAGEM, CHAVE, aceita, alterado, id="second").status_code == 400
    ok = retomar(client, mcp_post, GARAGEM, CHAVE, aceita, estado, id="third")
    assert ok.status_code == 200 and ok.json()["result"]["resultType"] == "complete"


def test_decline_result_is_reservado_false_for_bridge(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    result = reservar(client, mcp_post, **{k: GARAGEM[k] for k in ("sala", "inicio", "fim")}, responsavel="Marty").json()["result"]
    r = retomar(client, mcp_post, GARAGEM, CHAVE, {"action": "decline"}, result["requestState"])
    final = r.json()["result"]
    assert final["isError"] is False
    assert final["structuredContent"]["reservado"] is False
    assert final["structuredContent"]["motivo"] == "recusado"


def test_continuation_artifact_fields_come_from_sealed_request(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    args = {"sala": "sala-garagem", "inicio": "2026-11-03T14:00:00-03:00", "fim": "2026-11-03T15:30:00-03:00", "responsavel": " Marty  "}
    result = reservar(client, mcp_post, **args).json()["result"]
    aceita = {"action": "accept", "content": {"sala": "sala-mirante"}}
    sc = retomar(client, mcp_post, args, CHAVE, aceita, result["requestState"]).json()["result"]["structuredContent"]
    assert sc["sala"] == "sala-mirante"
    assert (sc["inicio"], sc["fim"], sc["responsavel"]) == (args["inicio"], args["fim"], args["responsavel"])


@pytest.mark.parametrize("sala", ["sala-garagem", "sala-fusca"])
def test_offer_never_contains_requested_room(fresh_app, mcp_post, sala):
    client, _, _ = fresh_app()
    horario = ("14:00", "15:00") if sala == "sala-garagem" else ("16:00", "17:00")
    result = reservar(client, mcp_post, sala, h(horario[0]), h(horario[1])).json()["result"]
    assert sala not in enum_de(result)
