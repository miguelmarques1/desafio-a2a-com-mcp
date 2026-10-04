import json

import pytest

from agente.mcp_host import CompleteError, CompleteSuccess, InputRequired, ProtocolFailure
from agente.protocol import Message, Part, Role, TaskState
from agente.skills.outcome_mapping import (
    ARTIFACT_KEYS,
    apply_final_outcome,
    build_reserva_document,
    complete_with_reservation,
    render_reserva_artifact,
)
from agente.task_store import TaskStore

VERSION = "2026-11-01"


def structured_of(wire, name="02-tools-call-livre.json"):
    return wire(name)["response"]["body"]["result"]["structuredContent"]


def working_task(fixed_ids):
    store = TaskStore(fixed_ids())
    task_id = store.create_task(Message("msg-user", Role.USER, (Part("reservar ..."),)))
    handle = store.handle(task_id)
    handle.transition(TaskState.WORKING)
    return handle


def test_document_from_wire_02_structured_content(wire):
    structured = structured_of(wire)
    document = build_reserva_document(structured, VERSION)
    assert tuple(document) == ARTIFACT_KEYS
    for key in ARTIFACT_KEYS[:-1]:
        assert document[key] == structured[key]
    assert document["politica"] == VERSION


def test_politica_comes_from_agent_version(wire):
    structured = {**structured_of(wire), "politica": "outra"}
    assert build_reserva_document(structured, VERSION)["politica"] == VERSION


@pytest.mark.parametrize(
    "patch",
    [
        {"reservado": False},
        {"reservado": None},
        {"reservado": "true"},
        {"reserva": None},
        {"reserva": ""},
        {"sala": ""},
        {"inicio": 3},
        {"responsavel": None},
    ],
)
def test_invalid_payloads_return_none(wire, patch):
    assert build_reserva_document({**structured_of(wire), **patch}, VERSION) is None


@pytest.mark.parametrize("missing", ["reservado", "responsavel"])
def test_missing_keys_return_none(wire, missing):
    structured = structured_of(wire)
    del structured[missing]
    assert build_reserva_document(structured, VERSION) is None


def test_artifact_text_matches_wire_10_format(wire):
    artifact = wire("10-a2a-send-message-continuacao.json")["response"]["body"]["result"]["task"]["artifacts"][0]
    expected = artifact["parts"][0]["text"]
    assert render_reserva_artifact(json.loads(expected)) == expected


def test_non_ascii_name_is_not_escaped(wire):
    document = build_reserva_document({**structured_of(wire), "responsavel": "João"}, VERSION)
    text = render_reserva_artifact(document)
    assert "João" in text
    assert json.loads(text) == document


def test_complete_with_reservation_adds_artifact_then_completes(wire, fixed_ids):
    task = working_task(fixed_ids)
    complete_with_reservation(task, build_reserva_document(structured_of(wire), VERSION))
    snap = task.snapshot()
    assert snap["status"]["state"] == "TASK_STATE_COMPLETED"
    assert [a["name"] for a in snap["artifacts"]] == ["reserva"]
    assert snap["artifacts"][0]["artifactId"].startswith("art-")
    assert snap["status"]["message"]["parts"][0]["text"] == "Reserva res-0003 confirmada na sala-aquario."
    assert snap["history"][-1] == snap["status"]["message"]


def test_apply_final_outcome_success_completes(wire, fixed_ids):
    task = working_task(fixed_ids)
    apply_final_outcome(task, CompleteSuccess(structured_of(wire)), VERSION)
    assert task.state() is TaskState.COMPLETED


def test_apply_final_outcome_complete_error_is_verbatim(fixed_ids):
    task = working_task(fixed_ids)
    text = "Error executing tool reservar_sala: 1 validation error"
    apply_final_outcome(task, CompleteError(text), VERSION)
    snap = task.snapshot()
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert snap["status"]["message"]["parts"][0]["text"] == text
    assert snap["history"][-1]["parts"][0]["text"] == text
    assert snap["artifacts"] == []


def test_apply_final_outcome_protocol_failure(fixed_ids):
    task = working_task(fixed_ids)
    apply_final_outcome(task, ProtocolFailure("Servidor MCP indisponivel"), VERSION)
    snap = task.snapshot()
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert snap["status"]["message"]["parts"][0]["text"] == "Servidor MCP indisponivel"
    assert snap["artifacts"] == []


def test_apply_final_outcome_invalid_success_is_unexpected(wire, fixed_ids):
    task = working_task(fixed_ids)
    apply_final_outcome(task, CompleteSuccess({**structured_of(wire), "reservado": False}), VERSION)
    snap = task.snapshot()
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert snap["status"]["message"]["parts"][0]["text"] == "Resposta inesperada do servidor MCP"
    assert snap["artifacts"] == []


def test_apply_final_outcome_rejects_input_required(fixed_ids):
    task = working_task(fixed_ids)
    with pytest.raises(TypeError):
        apply_final_outcome(task, InputRequired("k", ("sala-a",), "state"), VERSION)
    assert task.state() is TaskState.WORKING
    assert task.snapshot()["artifacts"] == []
