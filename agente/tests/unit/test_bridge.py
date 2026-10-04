import asyncio
import json

import httpx

from agente.handlers import IncomingMessage, RequestContext
from agente.mcp_host import InputRequired, TraceContext
from agente.protocol import Message, Part, Role, TaskState
from agente.skills.bridge import (
    PausedRecord,
    make_continuation_handler,
    pause_for_choice,
    render_alternatives,
)
from agente.skills.request_parser import ReservationRequest
from agente.skills.reservar_sala import InputRequiredHandoff
from agente.task_store import TaskStore

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
TRACE2 = "11111111111111111111111111111111"
STATE = "S" * 64
REQ = ReservationRequest(
    "sala-garagem", "2026-11-03T14:00:00-03:00", "2026-11-03T15:00:00-03:00", "Marty"
)
KEY = "reservar_sala:escolha_de_sala"
RESERVED = {
    "resultType": "complete",
    "structuredContent": {
        "reservado": True,
        "reserva": "res-0004",
        "sala": "sala-fusca",
        "inicio": REQ.inicio,
        "fim": REQ.fim,
        "responsavel": "Marty",
        "politica": "outra",
    },
    "content": [],
}


def input_required(key, alts, state):
    return {
        "resultType": "input_required",
        "inputRequests": {
            key: {
                "method": "elicitation/create",
                "params": {
                    "mode": "form",
                    "message": "x",
                    "requestedSchema": {
                        "type": "object",
                        "properties": {"sala": {"type": "string", "enum": list(alts)}},
                    },
                },
            }
        },
        "requestState": state,
    }


def err(text):
    return {"resultType": "complete", "isError": True, "content": [{"type": "text", "text": text}]}


def answers(*items):
    queue = list(items)

    def answer(request):
        body = json.loads(request.content)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            error = {"code": item[0], "message": item[1]}
            return (200, "application/json", {"jsonrpc": "2.0", "id": body["id"], "error": error})
        return (200, "application/json", {"jsonrpc": "2.0", "id": body["id"], "result": item})

    return answer


def paused(fixed_ids, state=STATE, alts=("sala-fusca", "sala-mirante"), store=None):
    store = store or TaskStore(fixed_ids())
    task_id = store.create_task(Message("m", Role.USER, (Part("reservar"),)))
    task = store.handle(task_id)
    task.transition(TaskState.WORKING)
    handoff = InputRequiredHandoff(
        REQ,
        "2026-11-01",
        TraceContext.for_task(f"00-{TRACE}-00f067aa0ba902b7-01"),
        InputRequired(KEY, tuple(alts), state),
    )
    asyncio.run(pause_for_choice(None, task, handoff))
    store.end_claim(task_id)
    return store, task


def resume(store, task, mock, text, traceparent=None):
    task_id = task.task_id
    ctx = RequestContext(
        1, task_id, store.context_id_of(task_id), True, IncomingMessage("m", (text,)), traceparent
    )
    store.begin_continuation(task_id, Message("u", Role.USER, (Part(text),)))
    asyncio.run(make_continuation_handler(mock.client)(ctx, task))
    store.end_claim(task_id)
    return task.snapshot()


def text_of(snap):
    return snap["status"]["message"]["parts"][0]["text"]


def test_render_alternatives_enum_and_const():
    assert render_alternatives(("sala-fusca", "sala-mirante")) == "alternativas: sala-fusca, sala-mirante"
    assert render_alternatives(("sala-mirante",)) == "alternativas: sala-mirante"


def test_paused_record_from_handoff_and_repr(fixed_ids):
    _, task = paused(fixed_ids)
    record = task.get_attachment()
    assert isinstance(record, PausedRecord)
    assert record.tool_name == "reservar_sala"
    assert (record.request, record.input_key, record.policy_version) == (REQ, KEY, "2026-11-01")
    assert record.alternatives == ("sala-fusca", "sala-mirante")
    assert STATE not in repr(record) and STATE not in str(record)


def test_pause_stores_record_and_pauses(fixed_ids):
    _, task = paused(fixed_ids)
    snap = task.snapshot()
    assert snap["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert text_of(snap) == "alternativas: sala-fusca, sala-mirante"
    assert snap["history"][-1]["messageId"] == snap["status"]["message"]["messageId"]


def test_invalid_reply_reprompts_without_mcp(mock_mcp, fixed_ids):
    store, task = paused(fixed_ids)
    before = task.snapshot()["status"]["message"]["messageId"]
    record = task.get_attachment()
    mock = mock_mcp(answers())
    snap = resume(store, task, mock, "escolha=sala-aquario")
    assert mock.requests == []
    assert snap["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert text_of(snap) == "alternativas: sala-fusca, sala-mirante"
    assert snap["status"]["message"]["messageId"] != before
    assert task.get_attachment() is record


def test_accept_retry_request_shape_and_completion(mock_mcp, fixed_ids):
    store, task = paused(fixed_ids)
    mock = mock_mcp(answers(RESERVED))
    snap = resume(store, task, mock, "escolha=sala-fusca")
    (body,) = mock.bodies
    params = body["params"]
    assert params["name"] == "reservar_sala"
    assert list(params["arguments"]) == ["sala", "inicio", "fim", "responsavel"]
    assert params["arguments"]["sala"] == "sala-garagem"
    assert params["inputResponses"] == {KEY: {"action": "accept", "content": {"sala": "sala-fusca"}}}
    assert params["requestState"] == STATE
    assert snap["status"]["state"] == "TASK_STATE_COMPLETED"
    doc = json.loads(snap["artifacts"][0]["parts"][0]["text"])
    assert (doc["sala"], doc["politica"], doc["inicio"], doc["responsavel"]) == (
        "sala-fusca",
        "2026-11-01",
        REQ.inicio,
        "Marty",
    )
    assert task.get_attachment() is None
    assert [m["role"] for m in snap["history"]] == ["ROLE_USER", "ROLE_AGENT", "ROLE_USER", "ROLE_AGENT"]


def test_new_round_replaces_state_and_key_then_second_retry(mock_mcp, fixed_ids):
    store, task = paused(fixed_ids)
    mock = mock_mcp(answers(input_required("k2", ["sala-mirante"], "S2"), RESERVED))
    snap = resume(store, task, mock, "escolha=sala-fusca", f"00-{TRACE2}-00f067aa0ba902b7-01")
    assert snap["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert text_of(snap) == "alternativas: sala-mirante"
    record = task.get_attachment()
    assert (record.input_key, record.alternatives, record.request_state) == ("k2", ("sala-mirante",), "S2")
    assert (record.request, record.policy_version) == (REQ, "2026-11-01")
    assert record.trace.trace_id == TRACE
    resume(store, task, mock, "escolha=sala-mirante")
    params = mock.bodies[1]["params"]
    assert params["requestState"] == "S2" and list(params["inputResponses"]) == ["k2"]
    assert params["_meta"]["traceparent"].split("-")[1] == TRACE
    assert mock.bodies[0]["params"]["_meta"]["traceparent"].split("-")[1] == TRACE2


def test_retry_trace_falls_back_to_task_trace(mock_mcp, fixed_ids):
    store, task = paused(fixed_ids)
    mock = mock_mcp(answers(RESERVED))
    resume(store, task, mock, "escolha=sala-fusca", "garbage")
    assert mock.bodies[0]["params"]["_meta"]["traceparent"].split("-")[1] == TRACE


def test_retry_failures(mock_mcp, fixed_ids):
    cases = [
        (err("Sem alternativas disponiveis no intervalo"), "Sem alternativas disponiveis no intervalo"),
        ((-32602, "Invalid or expired requestState"), "Erro do servidor MCP: -32602 Invalid or expired requestState"),
        (httpx.ConnectError("boom"), "Servidor MCP indisponivel"),
    ]
    for item, expected in cases:
        store, task = paused(fixed_ids)
        snap = resume(store, task, mock_mcp(answers(item)), "escolha=sala-fusca")
        assert snap["status"]["state"] == "TASK_STATE_FAILED"
        assert text_of(snap) == expected
        assert snap["artifacts"] == [] and task.get_attachment() is None


def test_decline_cancels(mock_mcp, fixed_ids):
    store, task = paused(fixed_ids)
    declined = {
        "resultType": "complete",
        "structuredContent": {"reservado": False, "motivo": "recusado"},
        "content": [],
    }
    mock = mock_mcp(answers(declined))
    snap = resume(store, task, mock, "escolha=recusar")
    assert mock.bodies[0]["params"]["inputResponses"] == {KEY: {"action": "decline"}}
    assert snap["status"]["state"] == "TASK_STATE_CANCELED"
    assert text_of(snap) == "Reserva recusada: nenhuma alternativa escolhida."
    assert snap["artifacts"] == [] and task.get_attachment() is None


def test_decline_unexpected_answers_fail(mock_mcp, fixed_ids):
    for item in (RESERVED, err("x"), input_required(KEY, ["sala-fusca"], "S")):
        store, task = paused(fixed_ids)
        snap = resume(store, task, mock_mcp(answers(item)), "escolha=recusar")
        assert snap["status"]["state"] == "TASK_STATE_FAILED"
        assert text_of(snap) == "Resposta inesperada do servidor MCP"


def test_decline_protocol_failure_keeps_text(mock_mcp, fixed_ids):
    store, task = paused(fixed_ids)
    mock = mock_mcp(answers((-32602, "Invalid or expired requestState")))
    assert text_of(resume(store, task, mock, "escolha=recusar")) == (
        "Erro do servidor MCP: -32602 Invalid or expired requestState"
    )
    store, task = paused(fixed_ids)
    mock = mock_mcp(answers(httpx.ConnectError("x")))
    assert text_of(resume(store, task, mock, "escolha=recusar")) == "Servidor MCP indisponivel"


def test_missing_record_fails_internal(mock_mcp, fixed_ids):
    store = TaskStore(fixed_ids())
    task_id = store.create_task(Message("m", Role.USER, (Part("x"),)))
    task = store.handle(task_id)
    task.transition(TaskState.WORKING)
    task.transition(TaskState.INPUT_REQUIRED, "alternativas: a")
    store.end_claim(task_id)
    mock = mock_mcp(answers())
    snap = resume(store, task, mock, "escolha=a")
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert text_of(snap) == "Falha interna do agente"
    assert mock.requests == []


def test_two_tasks_keep_independent_records(mock_mcp, fixed_ids):
    store = TaskStore(fixed_ids())
    _, a = paused(fixed_ids, "S_A", store=store)
    _, b = paused(fixed_ids, "S_B", store=store)
    mock = mock_mcp(answers(RESERVED, RESERVED))
    resume(store, b, mock, "escolha=sala-mirante")
    resume(store, a, mock, "escolha=sala-mirante")
    assert [x["params"]["requestState"] for x in mock.bodies] == ["S_B", "S_A"]


def test_no_output_written(mock_mcp, fixed_ids, capsys):
    store, task = paused(fixed_ids)
    resume(store, task, mock_mcp(answers(RESERVED)), "escolha=sala-fusca")
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
