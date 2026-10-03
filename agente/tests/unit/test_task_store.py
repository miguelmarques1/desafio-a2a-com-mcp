import copy
import json
import re
import threading

import pytest

from agente import mensagens
from agente.lifecycle import InvalidTransitionError
from agente.protocol import Message, Part, Role, TaskState as S
from agente.task_store import (
    NotAwaitingInputError,
    TaskImmutableError,
    TaskNotFoundError,
    TaskStore,
    TerminalTaskError,
)

TERMINALS = [S.COMPLETED, S.FAILED, S.CANCELED]


def user_msg(text="oi", mid="msg-user", task_id=None):
    return Message(mid, Role.USER, (Part(text),), task_id)


def make(ids=None):
    store = TaskStore(ids)
    task_id = store.create_task(user_msg())
    return store, task_id, store.handle(task_id)


def paused(ids=None):
    store, task_id, handle = make(ids)
    handle.transition(S.WORKING)
    handle.transition(S.INPUT_REQUIRED, "alternativas: x")
    store.end_claim(task_id)
    return store, task_id, handle


def finish(handle, store, task_id, state):
    if state is S.FAILED:
        handle.transition(S.FAILED, "x")
        return
    handle.transition(S.WORKING)
    handle.transition(state, "x")


def test_create_task_starts_submitted_with_user_message():
    store = TaskStore()
    task_id = store.create_task(user_msg())
    snap = store.snapshot(task_id)
    assert snap["status"] == {"state": "TASK_STATE_SUBMITTED"}
    assert [m["messageId"] for m in snap["history"]] == ["msg-user"]
    assert snap["artifacts"] == []
    assert task_id.startswith("task-") and snap["contextId"].startswith("ctx-")
    with pytest.raises(NotAwaitingInputError):
        store.begin_continuation(task_id, user_msg())  # `new` claim still held


def test_each_task_gets_new_id_and_context_id():
    store = TaskStore()
    a, b = store.create_task(user_msg()), store.create_task(user_msg())
    assert a != b
    assert store.snapshot(a)["contextId"] != store.snapshot(b)["contextId"]


def test_colliding_generated_task_id_is_regenerated(fixed_ids):
    store = TaskStore(fixed_ids(task=["task-a", "task-a", "task-b"]))
    first = store.create_task(user_msg(mid="m1"))
    second = store.create_task(user_msg(mid="m2"))
    assert (first, second) == ("task-a", "task-b")
    assert store.snapshot("task-a")["history"][0]["messageId"] == "m1"


def test_transition_with_text_sets_status_and_appends_same_message():
    _, _, handle = make()
    handle.transition(S.WORKING)
    handle.transition(S.INPUT_REQUIRED, "alternativas: x")
    snap = handle.snapshot()
    assert snap["status"]["message"] == snap["history"][-1]
    assert snap["status"]["message"]["role"] == "ROLE_AGENT"


def test_transition_without_text_clears_status_message():
    store, task_id, handle = paused()
    store.begin_continuation(task_id, user_msg(mid="msg-2", task_id=task_id))
    handle.transition(S.WORKING)
    assert handle.snapshot()["status"] == {"state": "TASK_STATE_WORKING"}


def test_reprompt_keeps_input_required_and_appends_new_message():
    store, task_id, handle = paused()
    store.begin_continuation(task_id, user_msg(mid="msg-2", task_id=task_id))
    before = handle.snapshot()
    handle.transition(S.INPUT_REQUIRED, "alternativas: x")
    after = handle.snapshot()
    assert after["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert len(after["history"]) == len(before["history"]) + 1
    assert after["status"]["message"]["messageId"] != before["status"]["message"]["messageId"]


def test_add_artifact_returns_id_and_appears_in_snapshot():
    _, _, handle = make()
    art_id = handle.add_artifact("reserva", "{}")
    assert re.fullmatch(r"art-[0-9a-f]{12}", art_id)
    assert handle.snapshot()["artifacts"] == [
        {"artifactId": art_id, "name": "reserva", "parts": [{"text": "{}"}]}
    ]


def test_append_message_does_not_change_status():
    _, _, handle = make()
    before = handle.snapshot()
    handle.append_message("nota")
    after = handle.snapshot()
    assert after["status"] == before["status"]
    assert len(after["history"]) == len(before["history"]) + 1


@pytest.mark.parametrize("terminal", TERMINALS)
@pytest.mark.parametrize("op", ["transition", "append", "artifact", "attachment"])
def test_terminal_task_is_immutable(terminal, op):
    store, task_id, handle = make()
    finish(handle, store, task_id, terminal)
    before = json.dumps(handle.snapshot())
    with pytest.raises(TaskImmutableError):
        {
            "transition": lambda: handle.transition(S.WORKING),
            "append": lambda: handle.append_message("x"),
            "artifact": lambda: handle.add_artifact("a", "b"),
            "attachment": lambda: handle.set_attachment(object()),
        }[op]()
    assert json.dumps(handle.snapshot()) == before


def test_unknown_task_raises_not_found():
    store = TaskStore()
    for call in (
        lambda: store.snapshot("task-x"),
        lambda: store.handle("task-x"),
        lambda: store.begin_continuation("task-x", user_msg()),
    ):
        with pytest.raises(TaskNotFoundError):
            call()


def test_begin_continuation_appends_user_message_and_claims():
    store, task_id, handle = paused()
    store.begin_continuation(task_id, user_msg("escolha=a", "msg-2", task_id))
    assert handle.snapshot()["history"][-1]["messageId"] == "msg-2"
    with pytest.raises(NotAwaitingInputError):
        store.begin_continuation(task_id, user_msg())  # claim held


@pytest.mark.parametrize("terminal", TERMINALS)
def test_begin_continuation_on_terminal_task_leaves_it_untouched(terminal):
    store, task_id, handle = make()
    finish(handle, store, task_id, terminal)
    store.end_claim(task_id)
    before = json.dumps(store.snapshot(task_id))
    with pytest.raises(TerminalTaskError) as info:
        store.begin_continuation(task_id, user_msg())
    assert info.value.state is terminal
    assert json.dumps(store.snapshot(task_id)) == before


@pytest.mark.parametrize("busy", ["submitted", "working", "claimed"])
def test_begin_continuation_on_busy_task_is_refused(busy):
    if busy == "claimed":
        store, task_id, handle = paused()
        store.begin_continuation(task_id, user_msg(mid="msg-2"))
    else:
        store, task_id, handle = make()
        if busy == "working":
            handle.transition(S.WORKING)
        store.end_claim(task_id)
    before = json.dumps(store.snapshot(task_id))
    with pytest.raises(NotAwaitingInputError):
        store.begin_continuation(task_id, user_msg(mid="msg-3"))
    assert json.dumps(store.snapshot(task_id)) == before


def test_end_claim_releases_task():
    store, task_id, handle = paused()
    store.begin_continuation(task_id, user_msg(mid="msg-2"))
    handle.transition(S.INPUT_REQUIRED, "de novo")
    store.end_claim(task_id)
    store.begin_continuation(task_id, user_msg(mid="msg-3"))


def test_settle_fails_unsettled_task_with_internal_message():
    store, task_id, handle = make()
    handle.transition(S.WORKING)
    store.settle(task_id)
    snap = store.snapshot(task_id)
    assert snap["status"]["state"] == "TASK_STATE_FAILED"
    assert snap["status"]["message"]["parts"] == [{"text": mensagens.FALHA_INTERNA}]


def test_settle_leaves_terminal_and_paused_tasks_alone():
    store, task_id, handle = make()
    finish(handle, store, task_id, S.COMPLETED)
    before = json.dumps(store.snapshot(task_id))
    store.settle(task_id)
    assert json.dumps(store.snapshot(task_id)) == before
    store2, task2, _ = paused()
    store2.settle(task2)
    assert store2.state_of(task2) is S.INPUT_REQUIRED


def test_resume_without_continuation_claim_is_rejected():
    store, task_id, handle = paused()
    with pytest.raises(InvalidTransitionError):
        handle.transition(S.WORKING)


def test_attachment_never_appears_in_snapshot():
    _, _, handle = make()
    sentinel = "S" * 64
    handle.set_attachment({"secret": sentinel})
    assert sentinel not in json.dumps(handle.snapshot())


@pytest.mark.parametrize("terminal", TERMINALS)
def test_attachment_dropped_on_terminal_transition(terminal):
    store, task_id, handle = make()
    handle.transition(S.WORKING)
    handle.set_attachment("paused-state")
    handle.transition(terminal, "fim")
    assert handle.get_attachment() is None


def test_attachments_are_isolated_per_task():
    store = TaskStore()
    h1 = store.handle(store.create_task(user_msg()))
    h2 = store.handle(store.create_task(user_msg()))
    h1.set_attachment("um")
    h2.set_attachment("dois")
    assert (h1.get_attachment(), h2.get_attachment()) == ("um", "dois")
    h1.clear_attachment()
    assert h1.get_attachment() is None and h2.get_attachment() == "dois"


def test_snapshot_is_detached():
    _, _, handle = make()
    snap = handle.snapshot()
    expected = copy.deepcopy(snap)
    snap["history"].clear()
    snap["status"]["state"] = "x"
    assert handle.snapshot() == expected


def test_concurrent_creates_from_threads_are_all_kept():
    store = TaskStore()
    ids: list[str] = []

    def work():
        ids.append(store.create_task(user_msg()))

    threads = [threading.Thread(target=work) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(ids)) == 50
    assert all(store.snapshot(i)["id"] == i for i in ids)


def test_handle_repr_has_no_attachment():
    _, _, handle = make()
    handle.set_attachment("segredo-xyz")
    assert "segredo-xyz" not in repr(handle)
