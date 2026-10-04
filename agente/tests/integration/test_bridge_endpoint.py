import json

from agente.handlers import Handlers
from agente.skills.bridge import make_continuation_handler, pause_for_choice
from agente.skills.reservar_sala import make_reservar_sala_handler

TEXT = (
    "reservar sala=sala-garagem inicio=2026-11-03T14:00:00-03:00 "
    "fim=2026-11-03T15:00:00-03:00 responsavel=Marty"
)
LINE = "alternativas: sala-fusca, sala-mirante"


def result_of(wire, name):
    return wire(name)["response"]["body"]["result"]


def answers(*results):
    queue = list(results)

    def answer(request):
        body = json.loads(request.content)
        return (200, "application/json", {"jsonrpc": "2.0", "id": body["id"], "result": queue.pop(0)})

    return answer


def conflict_flow(wire, *rest):
    return answers(
        result_of(wire, "01-tools-list.json"),
        result_of(wire, "05-resources-read-politica.json"),
        result_of(wire, "03-tools-call-conflito-input-required.json"),
        *rest,
    )


def app_with_bridge(make_client, mock, fixed_ids):
    handlers = Handlers(
        new_task=make_reservar_sala_handler(mock.client, on_input_required=pause_for_choice),
        continuation=make_continuation_handler(mock.client),
    )
    return make_client(handlers, ids=fixed_ids())


def pause(app, send):
    return send(app.client, TEXT).json()["result"]["task"]


def status_text(task):
    return task["status"]["message"]["parts"][0]["text"]


def test_conflict_pauses_with_alternatives_line(make_client, mock_mcp, wire, send, fixed_ids):
    app = app_with_bridge(make_client, mock_mcp(conflict_flow(wire)), fixed_ids)
    task = pause(app, send)
    assert task["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert status_text(task) == LINE
    assert [m["role"] for m in task["history"]] == ["ROLE_USER", "ROLE_AGENT"]
    assert task["artifacts"] == []


def test_get_task_on_paused_task_matches_pause(make_client, mock_mcp, wire, send, a2a_post, fixed_ids):
    app = app_with_bridge(make_client, mock_mcp(conflict_flow(wire)), fixed_ids)
    task = pause(app, send)
    got = a2a_post(app.client, "GetTask", {"id": task["id"]}, id=2).json()["result"]
    got = got.get("task", got)
    assert (got["id"], got["contextId"], got["status"]["state"]) == (
        task["id"], task["contextId"], "TASK_STATE_INPUT_REQUIRED",
    )
    assert status_text(got) == LINE


def test_continuation_completes_and_terminal_refuses(make_client, mock_mcp, wire, send, fixed_ids):
    retry = result_of(wire, "04-tools-call-retry.json")
    app = app_with_bridge(make_client, mock_mcp(conflict_flow(wire, retry)), fixed_ids)
    task = pause(app, send)
    done = send(app.client, "escolha=sala-fusca", task_id=task["id"], id=2).json()["result"]["task"]
    assert (done["id"], done["contextId"]) == (task["id"], task["contextId"])
    assert done["status"]["state"] == "TASK_STATE_COMPLETED"
    assert [m["role"] for m in done["history"]] == ["ROLE_USER", "ROLE_AGENT", "ROLE_USER", "ROLE_AGENT"]
    assert json.loads(done["artifacts"][0]["parts"][0]["text"])["sala"] == "sala-fusca"
    again = send(app.client, "escolha=sala-mirante", task_id=task["id"], id=3).json()
    assert again["error"]["code"] == -32004
    assert again["error"]["message"] == f"Task {task['id']} esta em estado terminal: TASK_STATE_COMPLETED"


def test_reprompt_then_no_response_contains_request_state(make_client, mock_mcp, wire, send, a2a_post, fixed_ids):
    state = result_of(wire, "03-tools-call-conflito-input-required.json")["requestState"]
    retry = result_of(wire, "04-tools-call-retry.json")
    mock = mock_mcp(conflict_flow(wire, retry))
    app = app_with_bridge(make_client, mock, fixed_ids)
    bodies = [app.client.get("/.well-known/agent-card.json").text]
    first = send(app.client, TEXT)
    task = first.json()["result"]["task"]
    bodies.append(first.text)
    bodies.append(a2a_post(app.client, "GetTask", {"id": task["id"]}, id=2).text)
    reprompt = send(app.client, "escolha=sala-aquario", task_id=task["id"], id=3)
    bodies.append(reprompt.text)
    assert status_text(reprompt.json()["result"]["task"]) == LINE
    assert len(mock.requests) == 3
    bodies.append(send(app.client, "escolha=sala-fusca", task_id=task["id"], id=4).text)
    bodies.append(send(app.client, "escolha=sala-fusca", task_id=task["id"], id=5).text)
    for body in bodies:
        assert not any(state[i : i + 40] in body for i in range(0, len(state) - 39, 20))
    log = app.log.getvalue()
    assert state[:40] not in log
    states = [line for line in app.lines() if "state=" in line]
    assert "state=TASK_STATE_INPUT_REQUIRED" in states[0]
    assert "state=TASK_STATE_COMPLETED" in states[-2]


def test_identical_conflicts_give_identical_lines(make_client, mock_mcp, wire, send, fixed_ids):
    flow = conflict_flow(wire)
    second = conflict_flow(wire)
    queue = [flow, second]
    calls = []

    def answer(request):
        calls.append(1)
        return queue[0 if len(calls) <= 3 else 1](request)

    app = app_with_bridge(make_client, mock_mcp(answer), fixed_ids)
    a = pause(app, send)
    b = send(app.client, TEXT, id=2).json()["result"]["task"]
    assert status_text(a) == status_text(b) == LINE
