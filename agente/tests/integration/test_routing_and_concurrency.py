import asyncio
import io

import httpx

from agente.app import build_app
from agente.config import Settings
from agente.handlers import Handlers
from agente.protocol import TaskState as S
from agente.task_store import TaskStore

PAUSE = [("transition", S.WORKING), ("transition", S.INPUT_REQUIRED, "alternativas: x")]


def message(text, task_id=None, mid="msg-user"):
    msg = {"messageId": mid, "role": "ROLE_USER", "parts": [{"text": text}]}
    if task_id:
        msg["taskId"] = task_id
    return {"jsonrpc": "2.0", "id": mid, "method": "SendMessage", "params": {"message": msg}}


def get_task(task_id):
    return {"jsonrpc": "2.0", "id": "g", "method": "GetTask", "params": {"id": task_id}}


def run_app(handlers, scenario, ids=None):
    store = TaskStore(ids)
    log = io.StringIO()
    app = build_app(
        Settings("127.0.0.1", 7300, "http://localhost:7300"),
        handlers=handlers,
        store=store,
        log_stream=log,
    )

    async def main():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://agente") as client:

            async def post(body):
                return (await client.post("/a2a", json=body)).json()

            return await scenario(post, store)

    return asyncio.run(main())


def test_message_without_task_id_goes_to_new_task_handler(recording):
    rec = recording()

    async def scenario(post, store):
        return await post(message("reservar"))

    run_app(rec.handlers(), scenario)
    assert len(rec.new_calls) == 1 and rec.cont_calls == []
    assert rec.new_calls[0][0].is_continuation is False


def test_message_with_task_id_goes_to_continuation_handler(scripted, recording, fixed_ids):
    rec = recording()
    handlers = Handlers(
        new_task=scripted(new=PAUSE).handlers().new_task, continuation=rec.handlers().continuation
    )

    async def scenario(post, store):
        first = await post(message("reservar"))
        task = first["result"]["task"]
        await post(message("escolha=a", task["id"], "msg-2"))
        return task

    task = run_app(handlers, scenario)
    assert len(rec.cont_calls) == 1
    ctx, seen = rec.cont_calls[0]
    assert ctx.is_continuation and ctx.task_id == task["id"] and ctx.context_id == task["contextId"]
    assert ctx.message.text == "escolha=a"
    assert seen["history"][-1]["role"] == "ROLE_USER"
    assert seen["history"][-1]["parts"] == [{"text": "escolha=a"}]


def test_continuation_while_continuation_runs_returns_32004(scripted):
    # events must be created inside the running loop, so everything is built in one coroutine
    store = TaskStore()
    log = io.StringIO()

    async def main():
        started, release = asyncio.Event(), asyncio.Event()
        cont = [
            ("transition", S.WORKING),
            ("set", started),
            ("wait", release),
            ("transition", S.COMPLETED, "ok"),
        ]
        handlers = scripted(new=PAUSE, cont=cont).handlers()
        app = build_app(
            Settings("127.0.0.1", 7300, "http://localhost:7300"),
            handlers=handlers,
            store=store,
            log_stream=log,
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://agente") as client:

            async def post(body):
                return (await client.post("/a2a", json=body)).json()

            task_id = (await post(message("reservar")))["result"]["task"]["id"]
            first = asyncio.create_task(post(message("escolha=a", task_id, "msg-c1")))
            await started.wait()
            second = await post(message("escolha=b", task_id, "msg-c2"))
            release.set()
            return task_id, second, await first

    task_id, second, first = asyncio.run(main())
    assert second["error"]["code"] == -32004
    assert second["error"]["message"] == f"Task {task_id} nao aguarda entrada"
    assert first["result"]["task"]["status"]["state"] == "TASK_STATE_COMPLETED"
    ids = [m["messageId"] for m in first["result"]["task"]["history"]]
    assert "msg-c1" in ids and "msg-c2" not in ids


def _blocking_new_task(scripted):
    async def main_factory():
        started, release = asyncio.Event(), asyncio.Event()
        steps = [("transition", S.WORKING), ("set", started), ("wait", release)]
        return scripted(new=steps + [("transition", S.COMPLETED, "ok")]).handlers(), started, release

    return main_factory


def test_continuation_while_new_task_handler_runs_returns_32004(scripted, fixed_ids):
    async def main():
        handlers, started, release = await _blocking_new_task(scripted)()
        store = TaskStore(fixed_ids(task=["task-aaaaaaaaaaaa"]))
        app = build_app(Settings("127.0.0.1", 7300, "http://l"), handlers=handlers, store=store)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://agente"
        ) as client:

            async def post(body):
                return (await client.post("/a2a", json=body)).json()

            first = asyncio.create_task(post(message("reservar")))
            await started.wait()
            second = await post(message("escolha=a", "task-aaaaaaaaaaaa", "msg-2"))
            during = await post(get_task("task-aaaaaaaaaaaa"))
            release.set()
            return second, during, await first

    second, during, first = asyncio.run(main())
    assert second["error"]["code"] == -32004
    assert second["error"]["message"] == "Task task-aaaaaaaaaaaa nao aguarda entrada"
    assert during["result"]["task"]["status"]["state"] == "TASK_STATE_WORKING"
    assert first["result"]["task"]["status"]["state"] == "TASK_STATE_COMPLETED"
    assert [m["messageId"] for m in first["result"]["task"]["history"]][0] == "msg-user"


def test_two_paused_tasks_resume_independently(scripted):
    observed = {}
    new = [
        ("transition", S.WORKING),
        ("call", lambda ctx, task: task.set_attachment(ctx.message.text)),
        ("transition", S.INPUT_REQUIRED, "alternativas: x"),
    ]
    cont = [
        ("call", lambda ctx, task: observed.update({ctx.task_id: task.get_attachment()})),
        ("transition", S.WORKING),
        ("transition", S.COMPLETED, "ok"),
    ]
    handlers = scripted(new=new, cont=cont).handlers()

    async def scenario(post, store):
        a = (await post(message("pedido-a", mid="msg-a")))["result"]["task"]["id"]
        b = (await post(message("pedido-b", mid="msg-b")))["result"]["task"]["id"]
        ra, rb = await asyncio.gather(
            post(message("escolha=1", a, "msg-a2")), post(message("escolha=2", b, "msg-b2"))
        )
        return a, b, ra, rb, store

    a, b, ra, rb, store = run_app(handlers, scenario)
    assert observed == {a: "pedido-a", b: "pedido-b"}
    for r in (ra, rb):
        assert r["result"]["task"]["status"]["state"] == "TASK_STATE_COMPLETED"
    assert store.handle(a).get_attachment() is None and store.handle(b).get_attachment() is None


def test_resume_without_continuation_claim_is_rejected(scripted):
    steps = PAUSE + [("transition", S.WORKING)]  # tries INPUT_REQUIRED -> WORKING in the new run

    async def scenario(post, store):
        return await post(message("reservar"))

    body = run_app(scripted(new=steps).handlers(), scenario)
    status = body["result"]["task"]["status"]
    assert status["state"] == "TASK_STATE_FAILED"
    assert status["message"]["parts"] == [{"text": "Falha interna do agente"}]
