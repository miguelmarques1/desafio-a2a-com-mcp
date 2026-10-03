"""F01 contracts consumed by F02-F06.

Each test is skipped while the consumer feature has not registered the tool or
resource it needs, and becomes active automatically once F02-F05 land.
"""

import json
from pathlib import Path

import pytest

from conftest import build_envelope, build_headers

SALAS = ["sala-aquario", "sala-porao", "sala-garagem", "sala-fusca", "sala-mirante"]


def tool_names(client, mcp_post) -> set[str]:
    r = mcp_post(client, "tools/list")
    return {t["name"] for t in r.json()["result"]["tools"]}


def call(client, mcp_post, name, arguments, **options):
    return mcp_post(client, "tools/call", {"name": name, "arguments": arguments}, **options)


def need_tool(client, mcp_post, name):
    if name not in tool_names(client, mcp_post):
        pytest.skip("consumer feature not registered yet")


def test_listar_salas_returns_rooms_loaded_by_foundation(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    need_tool(client, mcp_post, "listar_salas")
    r = call(client, mcp_post, "listar_salas", {})
    assert r.json()["result"]["structuredContent"]["salas"] == [s.as_dict() for s in dominio.catalogo]


def test_politica_resource_returns_policy_text_loaded_by_foundation(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    listed = mcp_post(client, "resources/list").json()
    uris = [r["uri"] for r in listed.get("result", {}).get("resources", [])]
    if "politica://uso" not in uris:
        pytest.skip("consumer feature not registered yet")
    r = mcp_post(client, "resources/read", {"uri": "politica://uso"})
    assert r.json()["result"]["contents"][0]["text"] == dominio.politica.texto


def test_consultar_disponibilidade_reports_seeded_reservations(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    need_tool(client, mcp_post, "consultar_disponibilidade")
    for sala, ini, fim, esperado in [
        ("sala-garagem", "14:00", "15:00", "res-0001"),
        ("sala-fusca", "16:00", "17:00", "res-0002"),
    ]:
        args = {
            "sala": sala,
            "inicio": f"2026-11-03T{ini}:00-03:00",
            "fim": f"2026-11-03T{fim}:00-03:00",
        }
        sc = call(client, mcp_post, "consultar_disponibilidade", args).json()["result"]["structuredContent"]
        assert sc["livre"] is False and [c["id"] for c in sc["conflitos"]] == [esperado]


def test_first_reservation_continues_ledger_with_parsed_policy_version(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    need_tool(client, mcp_post, "reservar_sala")
    args = {
        "sala": "sala-aquario",
        "inicio": "2026-11-03T09:00:00-03:00",
        "fim": "2026-11-03T10:00:00-03:00",
        "responsavel": "Doc",
    }
    sc = call(client, mcp_post, "reservar_sala", args).json()["result"]["structuredContent"]
    assert sc["reserva"] == "res-0003"
    assert sc["politica"] == dominio.politica.versao
    assert len(dominio.reservas) == 3


def conflict_args():
    return {
        "sala": "sala-garagem",
        "inicio": "2026-11-03T14:00:00-03:00",
        "fim": "2026-11-03T15:00:00-03:00",
        "responsavel": "Marty",
    }


def test_alternatives_never_smaller_than_requested_room(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    need_tool(client, mcp_post, "reservar_sala")
    result = call(client, mcp_post, "reservar_sala", conflict_args()).json()["result"]
    assert result["resultType"] == "input_required"
    (request,) = result["inputRequests"].values()
    enum = request["params"]["requestedSchema"]["properties"]["sala"]["enum"]
    minimo = dominio.catalogo.get("sala-garagem").capacidade
    assert enum and all(dominio.catalogo.get(i).capacidade >= minimo for i in enum)


def test_32021_exactly_when_request_capabilities_lack_form_elicitation(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    need_tool(client, mcp_post, "reservar_sala")
    form = {"elicitation": {"form": {}}}
    outcomes = []
    for caps in (form, {}, {"elicitation": {}}, form):
        r = call(client, mcp_post, "reservar_sala", conflict_args(), caps=caps)
        body = r.json()
        outcomes.append((r.status_code, body.get("error", {}).get("code"), body.get("result", {}).get("resultType")))
    assert outcomes == [
        (200, None, "input_required"),
        (400, -32021, None),
        (400, -32021, None),
        (200, None, "input_required"),
    ]


def test_agent_style_tools_list_is_logged_and_lists_registered_tools(fresh_app, repo_root: Path):
    client, log_lines, _ = fresh_app()
    wire = json.loads((repo_root / "exemplos" / "wire" / "01-tools-list.json").read_text(encoding="utf-8"))
    req = wire["request"]
    r = client.post("/mcp", json=req["body"], headers=req["headers"])
    assert r.status_code == 200
    assert log_lines() == [
        "mcp method=tools/list id=1 name=- traceparent=00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    ]
    names = {t["name"] for t in r.json()["result"]["tools"]}
    if not {"listar_salas", "consultar_disponibilidade", "reservar_sala"} <= names:
        pytest.skip("consumer feature not registered yet")
