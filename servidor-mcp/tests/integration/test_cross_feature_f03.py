"""F03 contracts consumed by F04 and F05 and provided by F01.

Tests that need ``reservar_sala`` are skipped while it is not registered and
become active automatically once F04/F05 land.
"""

import json

import pytest

CONSULTAR = "consultar_disponibilidade"
RESERVAR = "reservar_sala"


def h(hora, dia="2026-11-03"):
    return f"{dia}T{hora}:00-03:00"


def tool_names(client, mcp_post) -> set[str]:
    return {t["name"] for t in mcp_post(client, "tools/list").json()["result"]["tools"]}


def need_reservar(client, mcp_post):
    if RESERVAR not in tool_names(client, mcp_post):
        pytest.skip("consumer feature not registered yet")


def consultar(client, mcp_post, sala, inicio, fim):
    r = mcp_post(client, "tools/call", {"name": CONSULTAR, "arguments": {"sala": sala, "inicio": inicio, "fim": fim}})
    return r.json()["result"]


def reservar(client, mcp_post, sala, inicio, fim, responsavel="Doc", **params):
    args = {"sala": sala, "inicio": inicio, "fim": fim, "responsavel": responsavel}
    return mcp_post(client, "tools/call", {"name": RESERVAR, "arguments": args, **params})


def test_consultar_disponibilidade_reports_seeded_reservations_from_foundation_ledger(fresh_app, mcp_post, repo_root):
    client, _, _ = fresh_app()
    seeded = {
        r["id"]: r for r in json.loads((repo_root / "dados" / "reservas.json").read_text(encoding="utf-8"))
    }
    for sala, ini, fim, rid in [
        ("sala-garagem", "14:00", "15:00", "res-0001"),
        ("sala-fusca", "16:00", "17:00", "res-0002"),
    ]:
        sc = consultar(client, mcp_post, sala, h(ini), h(fim))["structuredContent"]
        assert sc["livre"] is False
        (conflito,) = sc["conflitos"]
        esperado = seeded[rid]
        assert conflito == {k: esperado[k] for k in ("id", "inicio", "fim", "responsavel")}


@pytest.mark.parametrize(
    "sala, inicio, fim",
    [
        ("sala-delorean", h("09:00"), h("10:00")),
        ("sala-aquario", "2026-11-03T14:00:00", h("15:00")),
        ("sala-aquario", h("10:00"), h("09:00")),
        ("sala-aquario", h("07:00"), h("08:00")),
        ("sala-aquario", h("09:00"), h("12:00")),
    ],
)
def test_reservar_sala_returns_same_messages_as_consultar_disponibilidade(fresh_app, mcp_post, sala, inicio, fim):
    client, _, dominio = fresh_app()
    need_reservar(client, mcp_post)
    esperado = consultar(client, mcp_post, sala, inicio, fim)
    r = reservar(client, mcp_post, sala, inicio, fim).json()["result"]
    assert esperado["isError"] is True and r["isError"] is True
    assert r["content"][0]["text"] == esperado["content"][0]["text"]
    assert len(dominio.reservas) == 2


@pytest.mark.parametrize(
    "sala, inicio, fim",
    [
        ("sala-garagem", h("15:00"), h("16:00")),
        ("sala-garagem", h("14:00"), h("15:00")),
        ("sala-aquario", h("09:00"), h("10:00")),
    ],
)
def test_alternatives_offered_only_when_conflict_detected(fresh_app, mcp_post, sala, inicio, fim):
    client, _, _ = fresh_app()
    need_reservar(client, mcp_post)
    disponibilidade = consultar(client, mcp_post, sala, inicio, fim)["structuredContent"]
    resposta = reservar(client, mcp_post, sala, inicio, fim)
    result = resposta.json().get("result", {})
    if disponibilidade["livre"]:
        assert result["resultType"] == "complete" and result["structuredContent"]["reservado"] is True
    elif result.get("resultType") == "input_required":
        assert len(disponibilidade["conflitos"]) >= 1


def test_reservation_completed_through_retry_is_visible_to_consultar_disponibilidade(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    need_reservar(client, mcp_post)
    first = reservar(client, mcp_post, "sala-garagem", h("14:00"), h("15:00"), "Marty").json()["result"]
    if first.get("resultType") != "input_required":
        pytest.skip("first call did not return input_required")
    (chave,) = first["inputRequests"]
    retry = reservar(
        client,
        mcp_post,
        "sala-garagem",
        h("14:00"),
        h("15:00"),
        "Marty",
        inputResponses={chave: {"action": "accept", "content": {"sala": "sala-fusca"}}},
        requestState=first["requestState"],
        id=2,
    ).json()["result"]
    assert retry["resultType"] == "complete" and retry["structuredContent"]["reserva"] == "res-0003"
    sc = consultar(client, mcp_post, "sala-fusca", h("14:00"), h("15:00"))["structuredContent"]
    assert sc["livre"] is False and "res-0003" in [c["id"] for c in sc["conflitos"]]


def test_booking_by_reservar_sala_is_visible_to_consultar_disponibilidade(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    need_reservar(client, mcp_post)
    booked = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"), "Doc").json()["result"]
    assert booked["resultType"] == "complete"
    sc = consultar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))["structuredContent"]
    assert sc["livre"] is False
    assert sc["conflitos"] == [
        {"id": booked["structuredContent"]["reserva"], "inicio": h("09:00"), "fim": h("10:00"), "responsavel": "Doc"}
    ]
