"""Outcome-to-Task mapping shared by the skill and the bridge."""

from __future__ import annotations

import json
from typing import Any

from agente import mensagens
from agente.mcp_host import CompleteError, CompleteSuccess, InputRequired, ProtocolFailure, ToolOutcome
from agente.protocol import TaskState
from agente.task_store import TaskHandle

ARTIFACT_NAME = "reserva"
ARTIFACT_KEYS = ("reserva", "sala", "inicio", "fim", "responsavel", "politica")
_PAYLOAD_KEYS = ARTIFACT_KEYS[:-1]
_NON_EMPTY_KEYS = ("reserva", "sala")


def build_reserva_document(structured: dict[str, Any], policy_version: str) -> dict[str, str] | None:
    """Ordered artifact document, or None when the payload is not a completed reservation."""
    if structured.get("reservado") is not True:
        return None
    values = {key: structured.get(key) for key in _PAYLOAD_KEYS}
    if not all(isinstance(value, str) for value in values.values()):
        return None
    if not all(values[key] for key in _NON_EMPTY_KEYS):
        return None
    return {**values, "politica": policy_version}


def render_reserva_artifact(document: dict[str, str]) -> str:
    return json.dumps(document, ensure_ascii=False)


def complete_with_reservation(task: TaskHandle, document: dict[str, str]) -> None:
    task.add_artifact(ARTIFACT_NAME, render_reserva_artifact(document))
    task.transition(
        TaskState.COMPLETED,
        mensagens.RESERVA_CONFIRMADA.format(reserva=document["reserva"], sala=document["sala"]),
    )


def fail_task(task: TaskHandle, text: str) -> None:
    task.transition(TaskState.FAILED, text)


def apply_final_outcome(task: TaskHandle, outcome: ToolOutcome, policy_version: str) -> None:
    match outcome:
        case CompleteSuccess(structured):
            document = build_reserva_document(structured, policy_version)
            if document is None:
                fail_task(task, mensagens.MCP_RESPOSTA_INESPERADA)
            else:
                complete_with_reservation(task, document)
        case CompleteError(text):
            fail_task(task, text)
        case ProtocolFailure(message):
            fail_task(task, message)
        case InputRequired():
            raise TypeError("input-required outcomes are handled by the pause hook, not the final mapping")
        case _:
            raise TypeError(f"unsupported outcome: {type(outcome).__name__}")
