"""Task state machine: allowed transitions and terminal states."""

from __future__ import annotations

from agente.protocol import TaskState

TERMINAL_STATES = frozenset({TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED})

ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.SUBMITTED: frozenset({TaskState.WORKING, TaskState.FAILED}),
    TaskState.WORKING: frozenset(
        {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED, TaskState.INPUT_REQUIRED}
    ),
    TaskState.INPUT_REQUIRED: frozenset(
        {TaskState.WORKING, TaskState.INPUT_REQUIRED, TaskState.FAILED}
    ),
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELED: frozenset(),
}


class InvalidTransitionError(Exception):
    def __init__(self, current: TaskState, target: TaskState):
        self.current, self.target = current, target
        super().__init__(f"transition {current.value} -> {target.value} not allowed")


def is_terminal(state: TaskState) -> bool:
    return state in TERMINAL_STATES


def check_transition(current: TaskState, target: TaskState, *, continuation_claim: bool) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(current, target)
    if (
        current is TaskState.INPUT_REQUIRED
        and target is TaskState.WORKING
        and not continuation_claim
    ):
        raise InvalidTransitionError(current, target)
