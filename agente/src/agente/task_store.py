"""In-memory Task store, per-Task handles, claims and private attachments.

Every store operation runs under one threading.Lock that is never held across
an await. Handlers only ever see a TaskHandle bound to a single Task.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from agente import mensagens
from agente.ids import IdFactory, RandomIdFactory
from agente.lifecycle import InvalidTransitionError, check_transition, is_terminal
from agente.protocol import (
    Artifact,
    Message,
    Part,
    Role,
    TaskState,
    task_to_wire,
)

CLAIM_NEW = "new"
CLAIM_CONTINUATION = "continuation"

__all__ = [
    "CLAIM_CONTINUATION",
    "CLAIM_NEW",
    "InvalidTransitionError",
    "NotAwaitingInputError",
    "TaskHandle",
    "TaskImmutableError",
    "TaskNotFoundError",
    "TaskStore",
    "TerminalTaskError",
]


class TaskNotFoundError(Exception):
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"task {task_id} not found")


class TerminalTaskError(Exception):
    def __init__(self, task_id: str, state: TaskState):
        self.task_id, self.state = task_id, state
        super().__init__(f"task {task_id} is terminal: {state.value}")


class NotAwaitingInputError(Exception):
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(f"task {task_id} is not awaiting input")


class TaskImmutableError(Exception):
    def __init__(self, task_id: str, state: TaskState):
        self.task_id, self.state = task_id, state
        super().__init__(f"task {task_id} is terminal ({state.value}) and cannot change")


@dataclass
class _TaskRecord:
    id: str
    context_id: str
    state: TaskState = TaskState.SUBMITTED
    status_message: Message | None = None
    history: list[Message] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)


class TaskStore:
    def __init__(self, ids: IdFactory | None = None):
        self._ids: IdFactory = ids or RandomIdFactory()
        self._lock = threading.Lock()
        self._tasks: dict[str, _TaskRecord] = {}
        self._claims: dict[str, str] = {}
        self._attachments: dict[str, object] = {}

    # --- internal helpers (callers hold the lock) ---

    def _get(self, task_id: str) -> _TaskRecord:
        record = self._tasks.get(task_id)
        if record is None:
            raise TaskNotFoundError(task_id)
        return record

    def _mutable(self, task_id: str) -> _TaskRecord:
        record = self._get(task_id)
        if is_terminal(record.state):
            raise TaskImmutableError(task_id, record.state)
        return record

    @staticmethod
    def _wire(record: _TaskRecord) -> dict[str, Any]:
        return task_to_wire(
            record.id,
            record.context_id,
            record.state,
            record.status_message,
            record.history,
            record.artifacts,
        )

    def _agent_message(self, record: _TaskRecord, text: str) -> Message:
        return Message(
            message_id=self._ids.message_id(),
            role=Role.AGENT,
            parts=(Part(text),),
            task_id=record.id,
            context_id=record.context_id,
        )

    def _apply_transition(self, record: _TaskRecord, state: TaskState, text: str | None) -> None:
        check_transition(
            record.state,
            state,
            continuation_claim=self._claims.get(record.id) == CLAIM_CONTINUATION,
        )
        if text is not None:
            message = self._agent_message(record, text)
            record.history.append(message)
            record.status_message = message
        else:
            record.status_message = None
        record.state = state
        if is_terminal(state):
            self._attachments.pop(record.id, None)

    # --- dispatcher-facing operations ---

    def create_task(self, user_message: Message) -> str:
        """Create a SUBMITTED Task holding the `new` claim; returns its id."""
        with self._lock:
            task_id = self._ids.task_id()
            while task_id in self._tasks:
                task_id = self._ids.task_id()
            self._tasks[task_id] = _TaskRecord(
                id=task_id,
                context_id=self._ids.context_id(),
                history=[user_message],
            )
            self._claims[task_id] = CLAIM_NEW
            return task_id

    def begin_continuation(self, task_id: str, user_message: Message) -> None:
        """Atomically check, append the user message and take the continuation claim."""
        with self._lock:
            record = self._get(task_id)
            if is_terminal(record.state):
                raise TerminalTaskError(task_id, record.state)
            if task_id in self._claims or record.state is not TaskState.INPUT_REQUIRED:
                raise NotAwaitingInputError(task_id)
            record.history.append(user_message)
            self._claims[task_id] = CLAIM_CONTINUATION

    def end_claim(self, task_id: str) -> None:
        with self._lock:
            self._claims.pop(task_id, None)

    def snapshot(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            return self._wire(self._get(task_id))

    def state_of(self, task_id: str) -> TaskState:
        with self._lock:
            return self._get(task_id).state

    def context_id_of(self, task_id: str) -> str:
        with self._lock:
            return self._get(task_id).context_id

    def settle(self, task_id: str) -> None:
        """Fail a Task a handler left in SUBMITTED or WORKING."""
        with self._lock:
            record = self._get(task_id)
            if record.state in (TaskState.SUBMITTED, TaskState.WORKING):
                self._apply_transition(record, TaskState.FAILED, mensagens.FALHA_INTERNA)

    def handle(self, task_id: str) -> TaskHandle:
        return TaskHandle(self, task_id)

    # --- handle-facing operations ---

    def _transition(self, task_id: str, state: TaskState, text: str | None) -> None:
        with self._lock:
            self._apply_transition(self._mutable(task_id), state, text)

    def _append_message(self, task_id: str, text: str) -> None:
        with self._lock:
            record = self._mutable(task_id)
            record.history.append(self._agent_message(record, text))

    def _add_artifact(self, task_id: str, name: str, text: str) -> str:
        with self._lock:
            record = self._mutable(task_id)
            artifact_id = self._ids.artifact_id()
            record.artifacts.append(Artifact(artifact_id, name, (Part(text),)))
            return artifact_id

    def _set_attachment(self, task_id: str, value: object) -> None:
        with self._lock:
            self._mutable(task_id)
            self._attachments[task_id] = value

    def _get_attachment(self, task_id: str) -> object | None:
        with self._lock:
            return self._attachments.get(task_id)

    def _clear_attachment(self, task_id: str) -> None:
        with self._lock:
            self._attachments.pop(task_id, None)


class TaskHandle:
    """The only write path handlers have; bound to one Task."""

    __slots__ = ("_store", "_task_id", "_context_id")

    def __init__(self, store: TaskStore, task_id: str):
        self._store = store
        self._task_id = task_id
        self._context_id = store.context_id_of(task_id)  # raises TaskNotFoundError

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def context_id(self) -> str:
        return self._context_id

    def state(self) -> TaskState:
        return self._store.state_of(self._task_id)

    def snapshot(self) -> dict[str, Any]:
        return self._store.snapshot(self._task_id)

    def transition(self, state: TaskState, text: str | None = None) -> None:
        self._store._transition(self._task_id, state, text)

    def append_message(self, text: str) -> None:
        self._store._append_message(self._task_id, text)

    def add_artifact(self, name: str, text: str) -> str:
        return self._store._add_artifact(self._task_id, name, text)

    def set_attachment(self, value: object) -> None:
        self._store._set_attachment(self._task_id, value)

    def get_attachment(self) -> object | None:
        return self._store._get_attachment(self._task_id)

    def clear_attachment(self) -> None:
        self._store._clear_attachment(self._task_id)

    def __repr__(self) -> str:
        return f"TaskHandle(task_id={self._task_id!r})"
