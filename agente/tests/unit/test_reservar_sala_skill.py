import asyncio
import json

import httpx

from agente.handlers import IncomingMessage, RequestContext
from agente.protocol import Message, Part, Role, TaskState
from agente.skills.outcome_mapping import ARTIFACT_KEYS
from agente.skills.request_parser import parse_reservation_request
from agente.skills.reservar_sala import (
    InputRequiredHandoff,
    make_reservar_sala_handler,
)
from agente.task_store import TaskStore

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
TP = f"00-{TRACE}-00f067aa0ba902b7-01"
TEXT = (
    "reservar sala=sala-aquario inicio=2026-11-03T09:00:00-03:00 "
    "fim=2026-11-03T10:00:00-03:00 responsavel=Doc"
)


def result_of(wire, name):
    return wire(name)["response"]["body"]["result"]


def answers(*results):
    queue = list(results)

    def answer(request):
        body = json.loads(request.content)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return (200, "application/json", {"jsonrpc": "2.0", "id": body["id"], "result": item})

    return answer


def free_flow(wire):
    return answers(
        result_of(wire, "01-tools-list.json"),
        result_of(wire, "05-resources-read-politica.json"),
        result_of(wire, "02-tools-call-livre.json"),
    )


def conflict_flow(wire):
    return answers(
        result_of(wire, "01-tools-list.json"),
        result_of(wire, "05-resources-read-politica.json"),
        result_of(wire, "03-tools-call-conflito-input-required.json"),
    )


def error_result(text):
    return {"resultType": "complete", "isError": True, "content": [{"type": "text", "text": text}]}


def new_task(fixed_ids, text=TEXT, traceparent=TP):
    store = TaskStore(fixed_ids())
    message = IncomingMessage("msg-user", (text,))
    task_id = store.create_task(Message("msg-user", Role.USER, (Part(text),)))
    ctx = RequestContext(1, task_id, store.context_id_of(task_id), False, message, traceparent)
    return ctx, store.handle(task_id)


async def unexpected_pause(ctx, task, handoff):
    raise AssertionError("this flow must not pause")


def skill(mock):
    return make_reservar_sala_handler(mock.client, on_input_required=unexpected_pause)


def run(handler, ctx, task):
    asyncio.run(handler(ctx, task))
    return task.snapshot()


def status_text(snap):
    return snap["status"]["message"]["parts"][0]["text"]


def test_malformed_request_fails_without_mcp_requests(mock_mcp, fixed_ids):
    mock = mock_mcp(answers())
    ctx, task = new_task(fixed_ids, "reservar sala=sala-porao")
    snap = run(skill(mock), ctx, task)
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(snap) == (
        "Pedido invalido: use reservar sala=<id> inicio=<iso8601> fim=<iso8601> responsavel=<nome>"
    )
    assert [m["parts"][0]["text"] for m in snap["history"]][-1] == status_text(snap)
    assert snap["artifacts"] == []
    assert mock.requests == []


def test_free_room_completes_with_artifact(mock_mcp, wire, fixed_ids):
    mock = mock_mcp(free_flow(wire))
    ctx, task = new_task(fixed_ids)
    snap = run(skill(mock), ctx, task)
    assert [b["method"] for b in mock.bodies] == ["tools/list", "resources/read", "tools/call"]
    assert snap["status"]["state"] == "TASK_STATE_COMPLETED"
    assert [m["role"] for m in snap["history"]] == ["ROLE_USER", "ROLE_AGENT"]
    document = json.loads(snap["artifacts"][0]["parts"][0]["text"])
    structured = result_of(wire, "02-tools-call-livre.json")["structuredContent"]
    assert tuple(document) == ARTIFACT_KEYS
    assert document["politica"] == "2026-11-01"
    assert document["reserva"] == structured["reserva"]
    assert status_text(snap) == f"Reserva {structured['reserva']} confirmada na {structured['sala']}."


def test_tool_call_arguments_are_the_parsed_tokens(mock_mcp, wire, fixed_ids):
    mock = mock_mcp(free_flow(wire))
    ctx, task = new_task(fixed_ids)
    run(skill(mock), ctx, task)
    params = mock.bodies[2]["params"]
    assert params["name"] == "reservar_sala"
    expected = parse_reservation_request(TEXT).arguments()
    assert params["arguments"] == expected
    assert list(params["arguments"]) == list(expected)


def test_all_requests_share_task_trace_id(mock_mcp, wire, fixed_ids):
    mock = mock_mcp(free_flow(wire))
    ctx, task = new_task(fixed_ids)
    run(skill(mock), ctx, task)
    traces = {b["params"]["_meta"]["traceparent"].split("-")[1] for b in mock.bodies}
    assert traces == {TRACE}


def test_complete_error_fails_with_verbatim_text(mock_mcp, wire, fixed_ids):
    text = "Sala inexistente: sala-delorean"
    mock = mock_mcp(
        answers(
            result_of(wire, "01-tools-list.json"),
            result_of(wire, "05-resources-read-politica.json"),
            error_result(text),
        )
    )
    ctx, task = new_task(fixed_ids)
    snap = run(skill(mock), ctx, task)
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(snap) == text
    assert snap["history"][-1]["parts"][0]["text"] == text
    assert snap["artifacts"] == []


def test_mcp_unavailable_fails_task(mock_mcp, fixed_ids):
    mock = mock_mcp(answers(httpx.ConnectError("down")))
    ctx, task = new_task(fixed_ids)
    snap = run(skill(mock), ctx, task)
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(snap) == "Servidor MCP indisponivel"
    assert len(mock.requests) == 1


def test_missing_tool_fails_after_discovery(mock_mcp, fixed_ids):
    mock = mock_mcp(answers({"resultType": "complete", "tools": [{"name": "listar_salas"}]}))
    ctx, task = new_task(fixed_ids)
    snap = run(skill(mock), ctx, task)
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(snap) == "Ferramenta reservar_sala nao encontrada no servidor MCP"
    assert len(mock.requests) == 1


def test_policy_without_version_fails(mock_mcp, wire, fixed_ids):
    policy = {"contents": [{"uri": "politica://uso", "mimeType": "text/markdown", "text": "# Politica"}]}
    mock = mock_mcp(answers(result_of(wire, "01-tools-list.json"), policy))
    ctx, task = new_task(fixed_ids)
    snap = run(skill(mock), ctx, task)
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(snap) == "Politica de uso sem versao declarada"
    assert [b["method"] for b in mock.bodies] == ["tools/list", "resources/read"]


def test_input_required_goes_to_pause_hook_with_handoff(mock_mcp, wire, fixed_ids):
    mock = mock_mcp(conflict_flow(wire))
    ctx, task = new_task(fixed_ids)
    calls = []

    async def hook(hook_ctx, hook_task, handoff):
        calls.append((hook_ctx, hook_task.state(), handoff))
        hook_task.transition(TaskState.INPUT_REQUIRED, "alternativas: x")

    snap = run(make_reservar_sala_handler(mock.client, on_input_required=hook), ctx, task)
    assert len(calls) == 1
    hook_ctx, state, handoff = calls[0]
    assert hook_ctx is ctx and state is TaskState.WORKING
    assert snap["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert handoff.request == parse_reservation_request(TEXT)
    assert handoff.policy_version == "2026-11-01"
    assert handoff.trace.trace_id == TRACE
    expected = result_of(wire, "03-tools-call-conflito-input-required.json")
    assert handoff.outcome.input_key == "__main__:escolha_de_sala"
    assert handoff.outcome.alternatives == ("sala-fusca", "sala-mirante")
    assert handoff.outcome.request_state == expected["requestState"]
    assert snap["artifacts"] == []


def test_malformed_request_passes_through_working_before_failing(mock_mcp, fixed_ids):
    mock = mock_mcp(answers())
    ctx, task = new_task(fixed_ids, "reservar sala=sala-porao")
    store = task._store
    seen = []
    original = store._transition

    def recording(task_id, state, text):
        seen.append(state)
        original(task_id, state, text)

    store._transition = recording
    run(skill(mock), ctx, task)
    assert seen == [TaskState.WORKING, TaskState.FAILED]


def test_incompatible_discovered_schema_fails_before_tools_call(mock_mcp, wire, fixed_ids):
    tools = json.loads(json.dumps(result_of(wire, "01-tools-list.json")))
    for tool in tools["tools"]:
        if tool["name"] == "reservar_sala":
            tool["inputSchema"]["required"].append("motivo")
    mock = mock_mcp(answers(tools, result_of(wire, "05-resources-read-politica.json")))
    ctx, task = new_task(fixed_ids)
    snap = run(skill(mock), ctx, task)
    assert [b["method"] for b in mock.bodies] == ["tools/list", "resources/read"]
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(snap) == (
        "Ferramenta reservar_sala anunciada com inputSchema incompativel com o pedido"
    )


def test_handoff_repr_hides_request_state(wire):
    from agente.mcp_host import InputRequired, TraceContext

    sentinel = "S" * 64
    handoff = InputRequiredHandoff(
        parse_reservation_request(TEXT),
        "2026-11-01",
        TraceContext.for_task(TP),
        InputRequired("k", ("sala-a",), sentinel),
    )
    assert sentinel not in repr(handoff)


def test_same_text_gives_same_state_and_message(mock_mcp, wire, fixed_ids):
    results = []
    for _ in range(2):
        mock = mock_mcp(free_flow(wire))
        ctx, task = new_task(fixed_ids)
        snap = run(skill(mock), ctx, task)
        results.append((snap["status"]["state"], status_text(snap)))
    assert results[0] == results[1]
