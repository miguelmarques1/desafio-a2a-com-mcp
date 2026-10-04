import json

from agente.handlers import Handlers
from agente.skills.bridge import pause_for_choice
from agente.skills.reservar_sala import make_reservar_sala_handler

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
TP = f"00-{TRACE}-00f067aa0ba902b7-01"
TEXT = (
    "reservar sala=sala-porao inicio=2026-11-03T09:00:00-03:00 "
    "fim=2026-11-03T10:00:00-03:00 responsavel=Doc"
)


def result_of(wire, name):
    return wire(name)["response"]["body"]["result"]


def answers(*results):
    queue = list(results)

    def answer(request):
        body = json.loads(request.content)
        return (200, "application/json", {"jsonrpc": "2.0", "id": body["id"], "result": queue.pop(0)})

    return answer


def flow(wire, last="02-tools-call-livre.json"):
    return answers(
        result_of(wire, "01-tools-list.json"),
        result_of(wire, "05-resources-read-politica.json"),
        result_of(wire, last),
    )


async def unused_continuation(ctx, task):
    raise AssertionError("these tests never continue a Task")


def app_with_skill(make_client, mock, fixed_ids):
    skill = make_reservar_sala_handler(mock.client, on_input_required=pause_for_choice)
    return make_client(Handlers(skill, unused_continuation), ids=fixed_ids())


def test_send_message_free_room_returns_completed_task(make_client, mock_mcp, wire, send, fixed_ids):
    mock = mock_mcp(flow(wire))
    app = app_with_skill(make_client, mock, fixed_ids)
    response = send(app.client, TEXT, id="9c1e04aa77b2")
    assert response.status_code == 200
    task = response.json()["result"]["task"]
    structured = result_of(wire, "02-tools-call-livre.json")["structuredContent"]
    assert task["id"] == "task-000000000001" and task["contextId"] == "ctx-000000000001"
    assert task["status"]["state"] == "TASK_STATE_COMPLETED"
    confirmation = f"Reserva {structured['reserva']} confirmada na {structured['sala']}."
    assert task["status"]["message"]["parts"] == [{"text": confirmation}]
    assert [m["role"] for m in task["history"]] == ["ROLE_USER", "ROLE_AGENT"]
    assert task["history"][1] == task["status"]["message"]
    artifact = task["artifacts"][0]
    assert artifact["name"] == "reserva" and artifact["artifactId"] == "art-000000000001"
    assert artifact["parts"][0]["text"] == json.dumps(
        {**{k: structured[k] for k in ("reserva", "sala", "inicio", "fim", "responsavel")}, "politica": "2026-11-01"},
        ensure_ascii=False,
    )


def test_send_message_malformed_returns_failed_task(make_client, mock_mcp, send, fixed_ids):
    mock = mock_mcp(answers())
    app = app_with_skill(make_client, mock, fixed_ids)
    task = send(app.client, "reservar sala=sala-porao").json()["result"]["task"]
    assert task["status"]["state"] == "TASK_STATE_FAILED"
    assert task["status"]["message"]["parts"][0]["text"] == (
        "Pedido invalido: use reservar sala=<id> inicio=<iso8601> fim=<iso8601> responsavel=<nome>"
    )
    assert task["artifacts"] == []
    assert mock.requests == []


def test_get_task_after_skill_returns_same_task(make_client, mock_mcp, wire, send, a2a_post, fixed_ids):
    mock = mock_mcp(flow(wire))
    app = app_with_skill(make_client, mock, fixed_ids)
    sent = send(app.client, TEXT).json()["result"]["task"]
    got = a2a_post(app.client, "GetTask", {"id": sent["id"]}, id=2).json()["result"]["task"]
    assert got == sent


def test_request_log_line_has_resulting_state(make_client, mock_mcp, wire, send, fixed_ids):
    mock = mock_mcp(flow(wire))
    app = app_with_skill(make_client, mock, fixed_ids)
    task = send(app.client, TEXT, id="9c1e04aa77b2").json()["result"]["task"]
    assert app.lines() == [f"a2a method=SendMessage id=9c1e04aa77b2 task={task['id']} state=TASK_STATE_COMPLETED"]


def test_traceparent_header_reaches_mcp_meta(make_client, mock_mcp, wire, send, fixed_ids):
    mock = mock_mcp(flow(wire))
    app = app_with_skill(make_client, mock, fixed_ids)
    send(app.client, TEXT, traceparent=TP)
    assert len(mock.bodies) == 3
    assert {b["params"]["_meta"]["traceparent"].split("-")[1] for b in mock.bodies} == {TRACE}


def test_no_request_state_in_any_response_after_pause(make_client, mock_mcp, wire, send, a2a_post, fixed_ids):
    state = result_of(wire, "03-tools-call-conflito-input-required.json")["requestState"]
    mock = mock_mcp(flow(wire, "03-tools-call-conflito-input-required.json"))
    app = app_with_skill(make_client, mock, fixed_ids)
    card = app.client.get("/.well-known/agent-card.json")
    sent = send(app.client, TEXT)
    task = sent.json()["result"]["task"]
    assert task["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    got = a2a_post(app.client, "GetTask", {"id": task["id"]}, id=2)
    for body in (card.text, sent.text, got.text):
        assert not any(state[i : i + 40] in body for i in range(0, len(state) - 39, 20))
