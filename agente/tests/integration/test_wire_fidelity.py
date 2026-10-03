import json

import pytest

from agente.protocol import TaskState as S

TASK, CTX = "task-3f658e57d468", "ctx-b125fd5a6174"


@pytest.fixture
def paused(make_client, scripted, fixed_ids, wire):
    """A client whose Task already went through wire 08."""
    expected_10 = wire("10-a2a-send-message-continuacao.json")["response"]["body"]["result"]["task"]
    status_text = expected_10["status"]["message"]["parts"][0]["text"]
    artifact_text = expected_10["artifacts"][0]["parts"][0]["text"]
    handlers = scripted(
        new=[
            ("transition", S.WORKING),
            ("transition", S.INPUT_REQUIRED, "alternativas: sala-mirante"),
        ],
        cont=[
            ("transition", S.WORKING),
            ("artifact", "reserva", artifact_text),
            ("transition", S.COMPLETED, status_text),
        ],
    ).handlers()
    ids = fixed_ids(
        task=[TASK],
        context=[CTX],
        message=["msg-5f36afcd2f76", "msg-3888926ca166"],
        artifact=["art-7259ff515ec2"],
    )
    box = make_client(handlers, ids=ids, public_url="http://127.0.0.1:7300")
    request = wire("08-a2a-send-message.json")["request"]
    response = box.client.post("/a2a", json=request["body"], headers=request["headers"])
    box.first = response
    return box


def test_card_equals_wire_07(make_client, wire):
    box = make_client(public_url="http://127.0.0.1:7300")
    expected = wire("07-a2a-agent-card.json")["response"]["body"]
    assert json.dumps(box.client.get("/.well-known/agent-card.json").json()) == json.dumps(expected)


def test_send_message_input_required_equals_wire_08(paused, wire):
    expected = wire("08-a2a-send-message.json")["response"]["body"]
    assert json.dumps(paused.first.json()) == json.dumps(expected)


def test_get_task_equals_wire_09(paused, wire):
    request = wire("09-a2a-get-task-input-required.json")["request"]
    response = paused.client.post("/a2a", json=request["body"], headers=request["headers"])
    expected = wire("09-a2a-get-task-input-required.json")["response"]["body"]
    assert json.dumps(response.json()) == json.dumps(expected)


def test_continuation_completed_equals_wire_10(paused, wire):
    request = wire("10-a2a-send-message-continuacao.json")["request"]
    response = paused.client.post("/a2a", json=request["body"], headers=request["headers"])
    expected = wire("10-a2a-send-message-continuacao.json")["response"]["body"]
    assert json.dumps(response.json()) == json.dumps(expected)
