from __future__ import annotations

import asyncio
import io
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from agente.app import build_app
from agente.config import Settings
from agente.handlers import Handlers, stub_continuation_handler, stub_new_task_handler
from agente.protocol import TaskState


class FixedIds:
    """IdFactory double: per-kind queues, then deterministic counters."""

    def __init__(self, *, task=(), context=(), message=(), artifact=()):
        self._queues = {
            "task": list(task),
            "ctx": list(context),
            "msg": list(message),
            "art": list(artifact),
        }
        self._counters = {"task": 0, "ctx": 0, "msg": 0, "art": 0}

    def _next(self, kind: str) -> str:
        queue = self._queues[kind]
        if queue:
            return queue.pop(0)
        self._counters[kind] += 1
        return f"{kind}-{self._counters[kind]:012d}"

    def task_id(self) -> str:
        return self._next("task")

    def context_id(self) -> str:
        return self._next("ctx")

    def message_id(self) -> str:
        return self._next("msg")

    def artifact_id(self) -> str:
        return self._next("art")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "exemplos").is_dir() and (parent / "agente").is_dir():
            return parent
    raise RuntimeError("repo root not found")


@pytest.fixture(scope="session")
def wire(repo_root: Path):
    def load(name: str) -> dict:
        return json.loads((repo_root / "exemplos" / "wire" / name).read_text(encoding="utf-8"))

    return load


@pytest.fixture
def fixed_ids():
    return FixedIds


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(name="free_port")
def free_port_fixture():
    return free_port


# --- app-level helpers ---------------------------------------------------


class Scripted:
    """Handlers built from steps: ("transition", state, text|None), ("artifact", name, text),
    ("append", text), ("attach", value), ("raise", exc), ("wait", asyncio.Event),
    ("set", asyncio.Event), ("resume",) is not needed: use transition."""

    def __init__(self, new=None, cont=None):
        self.new_steps = new
        self.cont_steps = cont

    @staticmethod
    def _make(steps, fallback):
        if steps is None:
            return fallback

        async def handler(ctx, task):
            for step in steps:
                kind = step[0]
                if kind == "transition":
                    task.transition(step[1], step[2] if len(step) > 2 else None)
                elif kind == "artifact":
                    task.add_artifact(step[1], step[2])
                elif kind == "append":
                    task.append_message(step[1])
                elif kind == "attach":
                    task.set_attachment(step[1])
                elif kind == "raise":
                    raise step[1]
                elif kind == "wait":
                    await step[1].wait()
                elif kind == "set":
                    step[1].set()
                elif kind == "call":
                    step[1](ctx, task)
                else:
                    raise AssertionError(kind)

        return handler

    def handlers(self) -> Handlers:
        return Handlers(
            new_task=self._make(self.new_steps, stub_new_task_handler),
            continuation=self._make(self.cont_steps, stub_continuation_handler),
        )


class Recorder:
    """Records each RequestContext and the Task state it saw, then fails the Task."""

    def __init__(self):
        self.new_calls: list = []
        self.cont_calls: list = []

    def handlers(self) -> Handlers:
        async def new(ctx, task):
            self.new_calls.append((ctx, task.snapshot()))
            task.transition(TaskState.FAILED, "gravado")

        async def cont(ctx, task):
            self.cont_calls.append((ctx, task.snapshot()))
            task.transition(TaskState.FAILED, "gravado")

        return Handlers(new_task=new, continuation=cont)


@pytest.fixture
def scripted():
    return Scripted


@pytest.fixture
def recording():
    return Recorder


@pytest.fixture
def make_client():
    opened: list[TestClient] = []

    def factory(handlers=None, ids=None, public_url="http://localhost:7300", store=None):
        settings = Settings("127.0.0.1", 7300, public_url)
        log = io.StringIO()
        handlers = handlers or Handlers(stub_new_task_handler, stub_continuation_handler)
        app = build_app(settings, handlers=handlers, ids=ids, store=store, log_stream=log)
        client = TestClient(app, base_url="http://127.0.0.1:7300")
        client.__enter__()
        opened.append(client)
        return SimpleNamespace(
            client=client,
            app=app,
            log=log,
            lines=lambda: [line for line in log.getvalue().splitlines() if line.startswith("a2a ")],
        )

    yield factory
    for client in opened:
        client.__exit__(None, None, None)


def _body(method, params, rpc_id):
    return {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params}


def _headers(traceparent, version):
    headers = {"Content-Type": "application/json"}
    if traceparent:
        headers["traceparent"] = traceparent
    if version is not None:
        headers["A2A-Version"] = version
    return headers


@pytest.fixture
def a2a_post():
    def post(client, method=None, params=None, *, id=1, traceparent=None, version=None, raw=None):
        content = raw if raw is not None else json.dumps(_body(method, params, id))
        return client.post("/a2a", content=content, headers=_headers(traceparent, version))

    return post


def message_params(text, *, task_id=None, message_id="msg-6ae2ad6802e5"):
    message = {"messageId": message_id, "role": "ROLE_USER", "parts": [{"text": text}]}
    if task_id:
        message["taskId"] = task_id
    return {"message": message}


@pytest.fixture
def send(a2a_post):
    def do(client, text="reservar sala=x", *, task_id=None, id=1, message_id="msg-6ae2ad6802e5", **kw):
        return a2a_post(
            client, "SendMessage", message_params(text, task_id=task_id, message_id=message_id),
            id=id, **kw
        )

    return do


@pytest.fixture
def run_async():
    return asyncio.run


# --- subprocess helpers --------------------------------------------------


class Process:
    def __init__(self, proc: subprocess.Popen, port: int):
        self.proc = proc
        self.port = port
        self.lines: list[str] = []
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        for line in self.proc.stderr:
            self.lines.append(line.rstrip("\r\n"))

    def wait_for_line(self, fragment: str, timeout: float = 20.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if any(fragment in line for line in self.lines):
                return True
            if self.proc.poll() is not None:
                time.sleep(0.2)
                return any(fragment in line for line in self.lines)
            time.sleep(0.05)
        return False

    def wait_for_count(self, prefix: str, count: int, timeout: float = 10.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len([ln for ln in self.lines if ln.startswith(prefix)]) >= count:
                return
            time.sleep(0.05)

    def stop(self) -> int | None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self._thread.join(timeout=5)
        return self.proc.returncode

    def wait_exit(self, timeout: float = 20.0) -> int:
        return self.proc.wait(timeout=timeout)


def _spawn(module: str, env: dict, cwd, port: int) -> Process:
    proc = subprocess.Popen(
        [sys.executable, "-m", module],
        env={k: v for k, v in env.items() if v is not None},
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return Process(proc, port)


@pytest.fixture
def start_agent():
    started: list[Process] = []

    def start(*, port: int | None = None, env: dict | None = None, cwd=None, wait_banner=True):
        port = port if port is not None else free_port()
        full_env = dict(os.environ)
        for key in ("AGENT_PORT", "AGENT_HOST", "AGENT_PUBLIC_URL", "MCP_URL"):
            full_env.pop(key, None)
        full_env["AGENT_PORT"] = str(port)
        full_env.update(env or {})
        agent = _spawn("agente", full_env, cwd, port)
        started.append(agent)
        if wait_banner:
            agent.wait_for_line("ouvindo em")
        return agent

    yield start
    for agent in started:
        agent.stop()


@pytest.fixture
def start_mcp_server():
    pytest.importorskip("servidor_mcp")
    started: list[Process] = []

    def start(*, port: int | None = None):
        port = port if port is not None else free_port()
        env = dict(os.environ)
        env.update(MCP_PORT=str(port), REQUEST_STATE_SECRET=secrets.token_hex(32))
        server = _spawn("servidor_mcp", env, None, port)
        started.append(server)
        server.wait_for_line("ouvindo em")
        return server

    yield start
    for server in started:
        server.stop()


# --- MCP host client helpers (F06) ---------------------------------------


class MockMcp:
    """McpClient on httpx.MockTransport. `answers` is a queue of (status, content_type, body)
    tuples (body: dict/str/bytes), exceptions to raise, or a callable taking the request."""

    def __init__(self, answers=(), timeout=10.0):
        import httpx

        from agente.mcp_host import McpClient

        self.requests: list = []
        self.bodies: list[dict] = []
        self._answers = answers if callable(answers) else list(answers)
        self.client = McpClient(
            "http://localhost:7301/mcp", timeout=timeout, transport=httpx.MockTransport(self._handle)
        )

    async def _handle(self, request):
        import httpx

        self.requests.append(request)
        self.bodies.append(json.loads(request.content))
        answer = self._answers(request) if callable(self._answers) else self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, content_type, body = answer
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        return httpx.Response(status, headers={"content-type": content_type}, content=body)


def json_answer(body, status=200):
    return (status, "application/json", body)


@pytest.fixture
def mock_mcp():
    return MockMcp


class _HungServer:
    def __init__(self):
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.port = self._sock.getsockname()[1]
        self._conns: list[socket.socket] = []
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            self._conns.append(conn)

    def close(self):
        self._sock.close()
        for conn in self._conns:
            conn.close()


@pytest.fixture
def hung_server():
    server = _HungServer()
    yield server
    server.close()


@pytest.fixture
def mcp_lines():
    def parse(process):
        rows = []
        for line in list(process.lines):
            if not line.startswith("mcp "):
                continue
            fields = dict(part.split("=", 1) for part in line.split()[1:] if "=" in part)
            rows.append((fields.get("method"), fields.get("id"), fields.get("name"), fields.get("traceparent")))
        return rows

    return parse
