import json
import re
import secrets

import pytest

from agente.protocol import TaskState as S
from agente.task_store import TaskStore

TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
PAUSE = [("transition", S.WORKING), ("transition", S.INPUT_REQUIRED, "alternativas: sala-mirante")]


def test_agent_card_returns_200_json(make_client):
    r = make_client().client.get("/.well-known/agent-card.json")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert json.loads(r.text)


def test_agent_card_declares_jsonrpc_interface_v1(make_client):
    card = make_client().client.get("/.well-known/agent-card.json").json()
    interface = card["supportedInterfaces"][0]
    assert interface["url"].endswith("/a2a")
    assert interface["protocolBinding"] == "JSONRPC"
    assert interface["protocolVersion"] == "1.0"
    assert "preferredTransport" not in card and "additionalInterfaces" not in card


def test_agent_card_declares_reservar_sala_skill(make_client):
    card = make_client().client.get("/.well-known/agent-card.json").json()
    assert any(skill["id"] == "reservar-sala" for skill in card["skills"])


def test_send_message_without_task_id_creates_new_task(make_client, send):
    c = make_client().client
    a, b = (send(c, id=i).json()["result"]["task"] for i in (1, 2))
    for task in (a, b):
        assert re.fullmatch(r"task-[0-9a-f]{12}", task["id"])
        assert re.fullmatch(r"ctx-[0-9a-f]{12}", task["contextId"])
    assert a["id"] != b["id"] and a["contextId"] != b["contextId"]


def test_stub_skill_fails_task_with_fixed_message(make_client, send):
    task = send(make_client().client).json()["result"]["task"]
    text = "Skill reservar-sala ainda nao implementada"
    assert task["status"]["state"] == "TASK_STATE_FAILED"
    assert task["status"]["message"]["parts"] == [{"text": text}]
    assert task["history"][-1] == task["status"]["message"]
    agent = task["history"][-1]
    assert agent["role"] == "ROLE_AGENT" and agent["messageId"].startswith("msg-")
    assert agent["taskId"] == task["id"] and agent["contextId"] == task["contextId"]


def test_send_message_returns_after_task_settles(make_client, send, scripted):
    steps = [
        ("transition", S.WORKING),
        ("artifact", "reserva", "{}"),
        ("transition", S.COMPLETED, "feito"),
    ]
    box = make_client(scripted(new=steps).handlers())
    task = send(box.client).json()["result"]["task"]
    assert task["status"]["state"] == "TASK_STATE_COMPLETED"
    assert task["artifacts"][0]["name"] == "reserva"


def test_get_task_returns_same_task(make_client, send, a2a_post):
    c = make_client().client
    sent = send(c).json()["result"]["task"]
    got = a2a_post(c, "GetTask", {"id": sent["id"]}, id=2).json()["result"]["task"]
    assert got == sent


@pytest.mark.parametrize("terminal", [S.COMPLETED, S.FAILED, S.CANCELED])
def test_send_message_to_terminal_task_returns_32004_and_keeps_task(
    make_client, send, a2a_post, scripted, terminal
):
    steps = [("transition", S.WORKING), ("transition", terminal, "fim")]
    box = make_client(scripted(new=steps).handlers())
    task = send(box.client).json()["result"]["task"]
    before = a2a_post(box.client, "GetTask", {"id": task["id"]}).text
    error = send(box.client, "escolha=sala-mirante", task_id=task["id"], id=5).json()["error"]
    assert error["code"] == -32004
    assert error["message"] == f"Task {task['id']} esta em estado terminal: {terminal.value}"
    assert a2a_post(box.client, "GetTask", {"id": task["id"]}).text == before


def test_get_task_unknown_id_returns_32001(make_client, a2a_post):
    body = a2a_post(make_client().client, "GetTask", {"id": "task-000000000000"}, id=7).json()
    assert body["error"]["code"] == -32001
    assert body["error"]["message"] == "Task nao encontrada: task-000000000000"
    assert body["error"]["data"][0]["reason"] == "TASK_NOT_FOUND"
    assert body["id"] == 7


def test_send_message_unknown_task_id_returns_32001(make_client, send):
    body = send(make_client().client, "escolha=x", task_id="task-000000000000").json()
    assert body["error"]["code"] == -32001


@pytest.mark.parametrize(
    "method",
    ["CancelTask", "ListTasks", "SendStreamingMessage", "SubscribeToTask", "message/send", "tasks/get"],
)
def test_unknown_method_returns_32601(make_client, a2a_post, method):
    body = a2a_post(make_client().client, method, {}, id=3).json()
    assert body["error"]["code"] == -32601
    assert body["error"]["message"] == f"Metodo nao encontrado: {method}"


def test_invalid_json_returns_32700(make_client, a2a_post):
    body = a2a_post(make_client().client, raw='{"jsonrpc": "2.0", "id"').json()
    assert body["error"]["code"] == -32700 and body["id"] is None


def test_invalid_request_returns_32600(make_client, a2a_post):
    c = make_client().client
    missing = a2a_post(c, raw=json.dumps({"id": 1, "method": "GetTask"})).json()
    assert missing["error"]["code"] == -32600
    assert a2a_post(c, raw="[]").json()["error"]["code"] == -32600


def test_missing_message_or_id_returns_32602(make_client, a2a_post):
    c = make_client().client
    a = a2a_post(c, "SendMessage", {}).json()["error"]
    b = a2a_post(c, "GetTask", {}).json()["error"]
    assert (a["code"], a["message"]) == (-32602, "Parametros invalidos: params.message ausente")
    assert (b["code"], b["message"]) == (-32602, "Parametros invalidos: params.id ausente")


def test_non_text_part_returns_32005(make_client, a2a_post):
    params = {"message": {"messageId": "m", "role": "ROLE_USER", "parts": [{"raw": "AAAA"}]}}
    body = a2a_post(make_client().client, "SendMessage", params).json()
    assert body["error"]["code"] == -32005


def test_all_jsonrpc_responses_are_http_200_json(make_client, send, a2a_post):
    c = make_client().client
    responses = [
        send(c),
        a2a_post(c, "GetTask", {"id": "task-000000000000"}),
        a2a_post(c, "CancelTask", {}),
        a2a_post(c, raw="{"),
        a2a_post(c, raw="[]"),
        a2a_post(c, "SendMessage", {}),
        a2a_post(c, "GetTask", {"id": "x"}, version="0.3"),
    ]
    for r in responses:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("version", [None, "1.0", "1.0.3"])
def test_a2a_version_absent_or_1_0_is_served(make_client, send, version):
    assert "result" in send(make_client().client, version=version).json()


@pytest.mark.parametrize("version", ["0.3", "2.0"])
def test_a2a_version_other_returns_32009(make_client, send, version):
    store = TaskStore()
    body = send(make_client(store=store).client, version=version).json()
    assert body["error"]["code"] == -32009
    assert body["error"]["message"] == f"Versao do protocolo A2A nao suportada: {version}"
    assert store._tasks == {}


def test_handler_exception_fails_task_with_internal_message(make_client, send, scripted):
    steps = [("transition", S.WORKING), ("raise", RuntimeError("segredo-xyz"))]
    box = make_client(scripted(new=steps).handlers())
    task = send(box.client).json()["result"]["task"]
    assert task["status"]["state"] == "TASK_STATE_FAILED"
    assert task["status"]["message"]["parts"] == [{"text": "Falha interna do agente"}]
    assert "RuntimeError" in box.log.getvalue()
    assert "segredo-xyz" not in box.log.getvalue()


def test_handler_leaving_task_working_is_failed(make_client, send, scripted):
    box = make_client(scripted(new=[("transition", S.WORKING)]).handlers())
    task = send(box.client).json()["result"]["task"]
    assert task["status"]["state"] == "TASK_STATE_FAILED"
    assert task["status"]["message"]["parts"] == [{"text": "Falha interna do agente"}]


def test_each_request_logs_one_line_with_resulting_state(make_client, send, a2a_post):
    box = make_client()
    task = send(box.client, id="9c1e04aa77b2").json()["result"]["task"]
    a2a_post(box.client, "GetTask", {"id": "task-000000000000"}, id=2)
    a2a_post(box.client, "CancelTask", {}, id=7)
    a2a_post(box.client, raw="{")
    assert box.lines() == [
        f"a2a method=SendMessage id=9c1e04aa77b2 task={task['id']} state=TASK_STATE_FAILED",
        "a2a method=GetTask id=2 task=task-000000000000 state=-",
        "a2a method=CancelTask id=7 task=- state=-",
        "a2a method=- id=- task=- state=-",
    ]


def test_card_requests_are_not_logged(make_client):
    box = make_client()
    box.client.get("/.well-known/agent-card.json")
    assert box.lines() == []


def test_traceparent_header_reaches_handler_context(make_client, send, recording):
    rec = recording()
    box = make_client(rec.handlers())
    send(box.client, traceparent=TRACEPARENT)
    send(box.client, id=2)
    assert [ctx.traceparent for ctx, _ in rec.new_calls] == [TRACEPARENT, None]


def test_attachment_never_leaks_into_responses_or_log(make_client, send, a2a_post, scripted):
    sentinel = secrets.token_hex(32)
    steps = [
        ("transition", S.WORKING),
        ("attach", sentinel),
        ("transition", S.INPUT_REQUIRED, "alternativas: sala-mirante"),
    ]
    box = make_client(scripted(new=steps).handlers())
    c = box.client
    first = send(c)
    task_id = first.json()["result"]["task"]["id"]
    texts = [
        first.text,
        a2a_post(c, "GetTask", {"id": task_id}).text,
        send(c, "escolha=x", task_id=task_id, id=3).text,  # stub continuation fails the Task
        send(c, "escolha=x", task_id=task_id, id=4).text,  # now terminal: -32004
        c.get("/.well-known/agent-card.json").text,
        box.log.getvalue(),
    ]
    windows = {sentinel[i : i + 40] for i in range(len(sentinel) - 39)}
    for text in texts:
        assert not any(w in text for w in windows)


def test_routes_and_verbs(make_client):
    c = make_client().client
    assert c.get("/a2a").status_code == 405
    assert c.post("/.well-known/agent-card.json").status_code == 405
    assert c.get("/outra").status_code == 404
