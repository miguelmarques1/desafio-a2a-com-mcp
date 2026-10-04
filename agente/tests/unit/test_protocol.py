import json

from agente.protocol import (
    Artifact,
    Message,
    Part,
    Role,
    TaskState,
    artifact_to_wire,
    message_to_wire,
    status_to_wire,
    task_to_wire,
)


def _agent_message():
    return Message("msg-1", Role.AGENT, (Part("oi"),), "task-1", "ctx-1")


def test_agent_message_key_order():
    assert list(message_to_wire(_agent_message())) == [
        "messageId",
        "role",
        "parts",
        "taskId",
        "contextId",
    ]


def test_user_message_keeps_only_received_optional_fields(wire):
    history = wire("10-a2a-send-message-continuacao.json")["response"]["body"]["result"]["task"][
        "history"
    ]
    first_user = Message(
        history[0]["messageId"], Role.USER, (Part(history[0]["parts"][0]["text"]),)
    )
    continuation = Message(
        history[2]["messageId"],
        Role.USER,
        (Part(history[2]["parts"][0]["text"]),),
        task_id=history[2]["taskId"],
    )
    assert json.dumps(message_to_wire(first_user)) == json.dumps(history[0])
    assert json.dumps(message_to_wire(continuation)) == json.dumps(history[2])


def test_task_key_order_and_artifacts_always_present():
    wire = task_to_wire("task-1", "ctx-1", TaskState.WORKING, None, [], [])
    assert list(wire) == ["id", "contextId", "status", "history", "artifacts"]
    assert wire["artifacts"] == []


def test_status_without_message_omits_message_key():
    assert status_to_wire(TaskState.WORKING, None) == {"state": "TASK_STATE_WORKING"}


def test_artifact_shape():
    art = Artifact("art-1", "reserva", (Part("x"),))
    assert artifact_to_wire(art) == {
        "artifactId": "art-1",
        "name": "reserva",
        "parts": [{"text": "x"}],
    }


def test_enum_wire_values():
    assert [s.value for s in TaskState] == [
        "TASK_STATE_SUBMITTED",
        "TASK_STATE_WORKING",
        "TASK_STATE_COMPLETED",
        "TASK_STATE_FAILED",
        "TASK_STATE_CANCELED",
        "TASK_STATE_INPUT_REQUIRED",
    ]
    assert (Role.USER.value, Role.AGENT.value) == ("ROLE_USER", "ROLE_AGENT")
