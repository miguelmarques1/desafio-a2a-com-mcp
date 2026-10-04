import hashlib
import io
import json
import secrets
import urllib.request

import pytest
from starlette.testclient import TestClient

from conftest import TRACEPARENT
from servidor_mcp.app import build_app
from servidor_mcp.config import Settings
from servidor_mcp.loader import load_dominio
from servidor_mcp.primitives import REGISTRARS
from servidor_mcp.server import build_server

TOOL = "reservar_sala"


def h(hora, dia="2026-11-03"):
    return f"{dia}T{hora}:00-03:00"


def post_call(client, mcp_post, arguments, **options):
    options.setdefault("id", secrets.token_hex(6))
    return mcp_post(client, "tools/call", {"name": TOOL, "arguments": arguments}, **options)


def reservar(client, mcp_post, sala, inicio, fim, responsavel="Doc", **options):
    r = post_call(client, mcp_post, {"sala": sala, "inicio": inicio, "fim": fim, "responsavel": responsavel}, **options)
    assert r.status_code == 200
    return r.json()["result"]


def consultar(client, mcp_post, sala, inicio, fim):
    args = {"sala": sala, "inicio": inicio, "fim": fim}
    r = mcp_post(client, "tools/call", {"name": "consultar_disponibilidade", "arguments": args})
    return r.json()["result"]


def wire(repo_root, name):
    return json.loads((repo_root / "exemplos" / "wire" / name).read_text(encoding="utf-8"))


def tools(client, mcp_post):
    return mcp_post(client, "tools/list").json()["result"]["tools"]


def test_tool_descriptor_matches_wire_capture(fresh_app, mcp_post, repo_root):
    client, _, _ = fresh_app()
    listed = wire(repo_root, "01-tools-list.json")["response"]["body"]["result"]["tools"]
    expected = next(t for t in listed if t["name"] == TOOL)
    assert next(t for t in tools(client, mcp_post) if t["name"] == TOOL) == expected


def test_tools_list_order_matches_wire_capture(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    assert [t["name"] for t in tools(client, mcp_post)] == ["listar_salas", "consultar_disponibilidade", "reservar_sala"]


def test_free_booking_matches_wire_example(fresh_app, repo_root):
    client, _, _ = fresh_app()
    captured = wire(repo_root, "02-tools-call-livre.json")
    r = client.post("/mcp", json=captured["request"]["body"], headers=captured["request"]["headers"])
    assert r.status_code == 200
    assert r.json()["result"] == captured["response"]["body"]["result"]


def test_first_booking_returns_res_0003_with_policy_version(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))
    assert r["resultType"] == "complete" and r["isError"] is False
    sc = r["structuredContent"]
    assert sc["reserva"] == "res-0003" and sc["reservado"] is True
    assert sc["politica"] == "2026-11-01" and sc["motivo"] is None


def test_inicio_fim_responsavel_returned_verbatim(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    ini, fim, resp = "2026-11-03T12:00:00Z", "2026-11-03T13:00:00.250+00:00", "  Dr. Emmett Brown "
    sc = reservar(client, mcp_post, "sala-aquario", ini, fim, resp)["structuredContent"]
    assert (sc["inicio"], sc["fim"], sc["responsavel"]) == (ini, fim, resp)
    stored = dominio.reservas.todas()[-1]
    assert (stored.inicio, stored.fim, stored.responsavel) == (ini, fim, resp)


def test_text_block_parses_to_structured_content(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))
    assert len(r["content"]) == 1 and r["content"][0]["type"] == "text"
    assert json.loads(r["content"][0]["text"]) == r["structuredContent"]


def test_booking_visible_to_consultar_disponibilidade(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    sc = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"), "Doc")["structuredContent"]
    q = consultar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))["structuredContent"]
    assert q["livre"] is False
    assert q["conflitos"] == [{"id": sc["reserva"], "inicio": h("09:00"), "fim": h("10:00"), "responsavel": "Doc"}]


def test_second_booking_of_same_slot_is_not_created(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))
    r = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"), "Marty")
    assert r["resultType"] == "input_required"
    (pedido,) = r["inputRequests"].values()
    assert pedido["params"]["requestedSchema"]["properties"]["sala"]["enum"] == [
        "sala-porao",
        "sala-fusca",
        "sala-garagem",
    ]
    assert len(dominio.reservas) == 3


def test_ids_increase_across_bookings(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    ids = [
        reservar(client, mcp_post, "sala-aquario", h(f"{hora:02d}:00"), h(f"{hora + 1:02d}:00"))["structuredContent"]["reserva"]
        for hora in (9, 10, 11)
    ]
    assert ids == ["res-0003", "res-0004", "res-0005"]


@pytest.mark.parametrize(
    "sala,inicio,fim,mensagem",
    [
        ("sala-delorean", h("09:00"), h("10:00"), "Sala inexistente: sala-delorean"),
        ("sala-aquario", "2026-11-03T09:00:00", h("10:00"), "Horario invalido: 2026-11-03T09:00:00"),
        ("sala-aquario", h("10:00"), h("09:00"), "Intervalo invalido: fim deve ser posterior a inicio"),
        ("sala-aquario", h("07:00"), h("08:00"), "Fora da janela de uso: a politica permite reservas entre 08:00 e 20:00"),
        ("sala-aquario", h("09:00"), h("12:00"), "Duracao acima do limite: a politica permite no maximo 2 horas"),
    ],
)
def test_validation_failures_return_exact_messages_and_create_nothing(fresh_app, mcp_post, sala, inicio, fim, mensagem):
    client, _, dominio = fresh_app()
    r = reservar(client, mcp_post, sala, inicio, fim)
    assert r["isError"] is True
    assert r["content"] == [{"type": "text", "text": mensagem}]
    assert "structuredContent" not in r
    assert len(dominio.reservas) == 2


def test_missing_argument_rejected_by_sdk(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    r = post_call(client, mcp_post, {"sala": "sala-aquario", "inicio": h("09:00"), "fim": h("10:00")})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"].startswith("Error executing tool reservar_sala")
    assert len(dominio.reservas) == 2


def test_non_string_argument_rejected_by_sdk(fresh_app, mcp_post):
    client, _, dominio = fresh_app()
    r = post_call(client, mcp_post, {"sala": "sala-aquario", "inicio": h("09:00"), "fim": h("10:00"), "responsavel": 5})
    assert r.json()["result"]["isError"] is True
    assert len(dominio.reservas) == 2


def test_internal_failure_returns_exact_message_and_leaves_ledger(fresh_app, mcp_post, monkeypatch, caplog):
    client, _, dominio = fresh_app()

    def boom(reserva):
        raise RuntimeError("disk on fire")

    with monkeypatch.context() as m:
        m.setattr(dominio.reservas, "adicionar", boom)
        r = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))
    assert r["isError"] is True
    assert r["content"] == [{"type": "text", "text": "Falha interna ao registrar a reserva"}]
    assert len(dominio.reservas) == 2
    assert any(rec.exc_info for rec in caplog.records if rec.levelname == "ERROR")
    again = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))
    assert again["structuredContent"]["reserva"] == "res-0003"


def test_free_booking_without_elicitation_capability_succeeds(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"), caps={})
    assert r["resultType"] == "complete" and r["structuredContent"]["reservado"] is True


def test_request_is_logged_with_tool_name(fresh_app, mcp_post):
    client, log_lines, _ = fresh_app()
    reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"), id=77, traceparent=TRACEPARENT)
    assert f"mcp method=tools/call id=77 name=reservar_sala traceparent={TRACEPARENT}" in log_lines()


def test_nothing_written_to_dados(dados_tmp, mcp_post):
    def digests():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dados_tmp.iterdir())}

    before = digests()
    dominio = load_dominio(dados_tmp)
    app = build_app(
        build_server(dominio, registrars=REGISTRARS), Settings("127.0.0.1", 7301, None, None), log_stream=io.StringIO()
    )
    with TestClient(app, base_url="http://127.0.0.1:7301") as client:
        r = reservar(client, mcp_post, "sala-aquario", h("09:00"), h("10:00"))
    assert r["structuredContent"]["reserva"] == "res-0003"
    assert digests() == before


def _rpc(port, name, arguments, id_):
    body = {
        "jsonrpc": "2.0",
        "id": id_,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments,
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
            },
        },
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/call",
            "Mcp-Name": name,
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())["result"]


def test_restart_forgets_reservations_and_restarts_ids(start_server):
    args = {"sala": "sala-aquario", "inicio": h("09:00"), "fim": h("10:00")}
    first = start_server()
    assert _rpc(first.port, TOOL, {**args, "responsavel": "Doc"}, 1)["structuredContent"]["reserva"] == "res-0003"
    first.stop()

    second = start_server()
    assert _rpc(second.port, "consultar_disponibilidade", args, 1)["structuredContent"]["livre"] is True
    assert _rpc(second.port, TOOL, {**args, "responsavel": "Doc"}, 2)["structuredContent"]["reserva"] == "res-0003"
