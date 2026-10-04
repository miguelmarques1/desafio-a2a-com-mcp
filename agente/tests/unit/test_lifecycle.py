import itertools

import pytest

from agente.lifecycle import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    InvalidTransitionError,
    check_transition,
    is_terminal,
)
from agente.protocol import TaskState as S

ALLOWED = {
    (S.SUBMITTED, S.WORKING),
    (S.SUBMITTED, S.FAILED),
    (S.WORKING, S.COMPLETED),
    (S.WORKING, S.FAILED),
    (S.WORKING, S.CANCELED),
    (S.WORKING, S.INPUT_REQUIRED),
    (S.INPUT_REQUIRED, S.WORKING),
    (S.INPUT_REQUIRED, S.INPUT_REQUIRED),
    (S.INPUT_REQUIRED, S.FAILED),
}


@pytest.mark.parametrize(("current", "target"), list(itertools.product(S, S)))
def test_allowed_transitions_table(current, target):
    if (current, target) in ALLOWED:
        check_transition(current, target, continuation_claim=True)
    else:
        with pytest.raises(InvalidTransitionError):
            check_transition(current, target, continuation_claim=True)


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES, key=lambda s: s.value))
def test_terminal_states_have_no_outgoing_transitions(state):
    assert ALLOWED_TRANSITIONS[state] == frozenset()
    for target in S:
        with pytest.raises(InvalidTransitionError):
            check_transition(state, target, continuation_claim=True)


def test_input_required_to_working_requires_continuation_claim():
    with pytest.raises(InvalidTransitionError):
        check_transition(S.INPUT_REQUIRED, S.WORKING, continuation_claim=False)
    check_transition(S.INPUT_REQUIRED, S.WORKING, continuation_claim=True)


def test_is_terminal_flags():
    assert {s for s in S if is_terminal(s)} == {S.COMPLETED, S.FAILED, S.CANCELED}
