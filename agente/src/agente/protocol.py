"""A2A v1.0 value types and wire serialization (key order of exemplos/wire/08-10)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    SUBMITTED = "TASK_STATE_SUBMITTED"
    WORKING = "TASK_STATE_WORKING"
    COMPLETED = "TASK_STATE_COMPLETED"
    FAILED = "TASK_STATE_FAILED"
    CANCELED = "TASK_STATE_CANCELED"
    INPUT_REQUIRED = "TASK_STATE_INPUT_REQUIRED"

    def __str__(self) -> str:
        return self.value


class Role(str, Enum):
    USER = "ROLE_USER"
    AGENT = "ROLE_AGENT"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Part:
    text: str


@dataclass(frozen=True)
class Message:
    message_id: str
    role: Role
    parts: tuple[Part, ...]
    task_id: str | None = None
    context_id: str | None = None


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    name: str
    parts: tuple[Part, ...]


def part_to_wire(part: Part) -> dict[str, Any]:
    return {"text": part.text}


def message_to_wire(message: Message) -> dict[str, Any]:
    wire: dict[str, Any] = {
        "messageId": message.message_id,
        "role": message.role.value,
        "parts": [part_to_wire(p) for p in message.parts],
    }
    if message.task_id is not None:
        wire["taskId"] = message.task_id
    if message.context_id is not None:
        wire["contextId"] = message.context_id
    return wire


def artifact_to_wire(artifact: Artifact) -> dict[str, Any]:
    return {
        "artifactId": artifact.artifact_id,
        "name": artifact.name,
        "parts": [part_to_wire(p) for p in artifact.parts],
    }


def status_to_wire(state: TaskState, message: Message | None) -> dict[str, Any]:
    wire: dict[str, Any] = {"state": state.value}
    if message is not None:
        wire["message"] = message_to_wire(message)
    return wire


def task_to_wire(
    task_id: str,
    context_id: str,
    state: TaskState,
    status_message: Message | None,
    history: list[Message] | tuple[Message, ...],
    artifacts: list[Artifact] | tuple[Artifact, ...],
) -> dict[str, Any]:
    return {
        "id": task_id,
        "contextId": context_id,
        "status": status_to_wire(state, status_message),
        "history": [message_to_wire(m) for m in history],
        "artifacts": [artifact_to_wire(a) for a in artifacts],
    }
