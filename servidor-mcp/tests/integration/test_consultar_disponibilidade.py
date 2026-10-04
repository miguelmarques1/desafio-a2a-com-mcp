import json
import secrets
import urllib.request

import pytest

from conftest import FORM_CAPS, TRACEPARENT, build_envelope, build_headers
from servidor_mcp.dominio import Reserva

TOOL = "consultar_disponibilidade"
MSG_JANELA = "Fora da janela de uso: a politica permite reservas entre 08:00 e 20:00"
MSG_DURACAO = "Duracao acima do limite: a politica permite no maximo 2 horas"
MSG_INTERVALO = "Intervalo invalido: fim deve ser posterior a inicio"


def h(hora, dia="2026-11-03", offset="-03:00"):
    return f"{dia}T{hora}:00{offset}"


def tools(client, mcp_post):
    return mcp_post(client, "tools/list").json()["result"]["tools"]


def post_call(client, mcp_post, sala, inicio, fim, **options):
    options.setdefault("id", secrets.token_hex(6))
    return mcp_post(client, "tools/call", {"name": TOOL, "arguments": {"sala": sala, "inicio": inicio, "fim": fim}}, **options)


def consultar(client, mcp_post, sala, inicio, fim, **options):
    r = post_call(client, mcp_post, sala, inicio, fim, **options)
    assert r.status_code == 200
    return r.json()["result"]


def wire_entry(repo_root):
    wire = json.loads((repo_root / "exemplos" / "wire" / "01-tools-list.json").read_text(encoding="utf-8"))
    return next(t for t in wire["response"]["body"]["result"]["tools"] if t["name"] == TOOL)


def test_tool_listed_with_object_input_schema_requiring_sala_inicio_fim(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    entry = next(t for t in tools(client, mcp_post) if t["name"] == TOOL)
    assert entry["inputSchema"]["type"] == "object"
    assert entry["inputSchema"]["required"] == ["sala", "inicio", "fim"]


def test_tool_descriptor_matches_wire_capture(fresh_app, mcp_post, repo_root):
    client, _, _ = fresh_app()
    entry = next(t for t in tools(client, mcp_post) if t["name"] == TOOL)
    assert entry == wire_entry(repo_root)


def test_registry_order_places_tool_between_listar_salas_and_reservar_sala(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    names = [t["name"] for t in tools(client, mcp_post)]
    i = names.index(TOOL)
    assert "listar_salas" not in names or names.index("listar_salas") < i
    assert "reservar_sala" not in names or i < names.index("reservar_sala")


def test_outside_window_returns_exact_message(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = consultar(client, mcp_post, "sala-aquario", h("07:00"), h("08:00"))
    assert r["isError"] is True and r["content"][0]["text"] == MSG_JANELA


def test_duration_over_limit_returns_exact_message(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = consultar(client, mcp_post, "sala-aquario", h("09:00"), h("12:00"))
    assert r["isError"] is True and r["content"][0]["text"] == MSG_DURACAO


def test_inverted_interval_returns_exact_message(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = consultar(client, mcp_post, "sala-aquario", h("10:00"), h("09:00"))
    assert r["isError"] is True and r["content"][0]["text"] == MSG_INTERVALO


def test_unknown_room_returns_exact_message(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = consultar(client, mcp_post, "sala-delorean", h("09:00"), h("10:00"))
    assert r["isError"] is True and r["content"][0]["text"] == "Sala inexistente: sala-delorean"


def test_two_hours_ending_at_20_is_free(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = consultar(client, mcp_post, "sala-aquario", h("18:00"), h("20:00"))
    assert r["isError"] is False
    assert r["structuredContent"]["livre"] is True and r["structuredContent"]["conflitos"] == []


def test_back_to_back_with_seeded_reservation_is_free(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = consultar(client, mcp_post, "sala-garagem", h("15:00"), h("16:00"))
    assert r["structuredContent"] == {"sala": "sala-garagem", "livre": True, "conflitos": []}


def test_seeded_conflict_reported(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = consultar(client, mcp_post, "sala-garagem", h("14:00"), h("15:00"))
    assert r["structuredContent"] == {
        "sala": "sala-garagem",
        "livre": False,
        "conflitos": [
            {"id": "res-0001", "inicio": h("14:00"), "fim": h("15:00"), "responsavel": "Marty"}
        ],
    }


def test_timestamp_without_offset_returns_exact_message(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = consultar(client, mcp_post, "sala-garagem", "2026-11-03T14:00:00", h("15:00"))
    assert r["isError"] is True
    assert r["content"][0]["text"] == "Horario invalido: 2026-11-03T14:00:00"


@pytest.mark.parametrize("args", [("sala-garagem", "14:00", "15:00"), ("sala-garagem", "15:00", "16:00")])
def test_success_has_structured_content_and_one_equal_text_block(fresh_app, mcp_post, args):
    client, _, _ = fresh_app()
    sala, ini, fim = args
    r = consultar(client, mcp_post, sala, h(ini), h(fim))
    assert r["resultType"] == "complete" and r["isError"] is False
    assert len(r["content"]) == 1 and r["content"][0]["type"] == "text"
    assert json.loads(r["content"][0]["text"]) == r["structuredContent"]


@pytest.mark.parametrize(
    "sala, inicio, fim, texto",
    [
        ("sala-delorean", h("09:00"), h("10:00"), "Sala inexistente: sala-delorean"),
        ("sala-aquario", "2026-11-03T14:00:00", h("15:00"), "Horario invalido: 2026-11-03T14:00:00"),
        ("sala-aquario", h("10:00"), h("09:00"), MSG_INTERVALO),
        ("sala-aquario", h("07:00"), h("08:00"), MSG_JANELA),
        ("sala-aquario", h("09:00"), h("12:00"), MSG_DURACAO),
    ],
)
def test_error_results_are_complete_with_single_exact_text_block(fresh_app, mcp_post, sala, inicio, fim, texto):
    client, _, _ = fresh_app()
    r = consultar(client, mcp_post, sala, inicio, fim)
    assert r["resultType"] == "complete" and r["isError"] is True
    assert r["content"] == [{"type": "text", "text": texto}]
    assert "structuredContent" not in r


def test_missing_argument_is_rejected_by_sdk_validation(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    r = mcp_post(client, "tools/call", {"name": TOOL, "arguments": {"sala": "sala-aquario"}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"].startswith("Error executing tool consultar_disponibilidade")
    assert len(dominio.reservas) == 2


def test_non_string_argument_is_rejected_by_sdk_validation(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = mcp_post(
        client, "tools/call", {"name": TOOL, "arguments": {"sala": 5, "inicio": h("09:00"), "fim": h("10:00")}}
    )
    assert r.status_code == 200 and r.json()["result"]["isError"] is True


def test_result_does_not_depend_on_client_capabilities(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    com = post_call(client, mcp_post, "sala-garagem", h("14:00"), h("15:00"), id=1, caps=FORM_CAPS)
    sem = post_call(client, mcp_post, "sala-garagem", h("14:00"), h("15:00"), id=1, caps={})
    assert com.status_code == sem.status_code == 200
    assert com.json() == sem.json()


def test_reservation_appended_to_ledger_becomes_visible(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    nova = Reserva("res-0003", "sala-aquario", h("09:00"), h("10:00"), "Doc")
    dominio.reservas.adicionar(nova)
    r = consultar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))["structuredContent"]
    assert r["livre"] is False
    assert r["conflitos"] == [{"id": "res-0003", "inicio": nova.inicio, "fim": nova.fim, "responsavel": "Doc"}]


def test_conflicts_sorted_at_tool_level(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    for id_, ini, fim in [
        ("res-0007", h("14:00"), h("14:30")),
        ("res-0006", "2026-11-03T16:30:00Z", "2026-11-03T17:00:00Z"),
        ("res-0004", "2026-11-03T17:00:00Z", "2026-11-03T17:30:00Z"),
    ]:
        dominio.reservas.adicionar(Reserva(id_, "sala-aquario", ini, fim, "X"))
    sc = consultar(client, mcp_post, "sala-aquario", h("13:00"), h("15:00"))["structuredContent"]
    assert [c["id"] for c in sc["conflitos"]] == ["res-0006", "res-0004", "res-0007"]


def test_query_does_not_modify_ledger(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    for ini, fim in [("14:00", "15:00"), ("15:00", "16:00"), ("07:00", "08:00")]:
        consultar(client, mcp_post, "sala-garagem", h(ini), h(fim))
    assert len(dominio.reservas) == 2


def test_identical_requests_produce_identical_results(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    a = consultar(client, mcp_post, "sala-garagem", h("14:00"), h("15:00"), id="aaaaaaaaaaaa")
    b = consultar(client, mcp_post, "sala-garagem", h("14:00"), h("15:00"), id="bbbbbbbbbbbb")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_request_is_logged_with_tool_name(fresh_app, mcp_post):
    client, log_lines, _ = fresh_app()
    post_call(client, mcp_post, "sala-garagem", h("14:00"), h("15:00"), id="5c0e9a1b7d3f", traceparent=TRACEPARENT)
    assert log_lines() == [f"mcp method=tools/call id=5c0e9a1b7d3f name={TOOL} traceparent={TRACEPARENT}"]


def test_real_process_serves_consultar_disponibilidade(start_server):
    server = start_server()

    def post(body):
        req = urllib.request.Request(
            f"http://127.0.0.1:{server.port}/mcp",
            data=json.dumps(body).encode(),
            headers=build_headers(body),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())

    listed = post(build_envelope("tools/list", id=1))
    assert TOOL in [t["name"] for t in listed["result"]["tools"]]
    called = post(
        build_envelope(
            "tools/call",
            {"name": TOOL, "arguments": {"sala": "sala-garagem", "inicio": h("14:00"), "fim": h("15:00")}},
            id="5c0e9a1b7d3f",
        )
    )
    sc = called["result"]["structuredContent"]
    assert sc["livre"] is False and [c["id"] for c in sc["conflitos"]] == ["res-0001"]
    server.wait_for_log_count(2)
    assert any(f"name={TOOL}" in line for line in server.lines)
