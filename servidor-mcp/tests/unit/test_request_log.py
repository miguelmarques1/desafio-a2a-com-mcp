import asyncio
import io
import json

import pytest

from servidor_mcp import request_log
from servidor_mcp.request_log import RequestLogMiddleware, format_log_lines

DASH = "mcp method=- id=- name=- traceparent=-"
TP = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def wire_body(repo_root, nome):
    return json.loads((repo_root / "exemplos" / "wire" / nome).read_text(encoding="utf-8"))["request"]["body"]


def one(body: dict) -> str:
    lines = format_log_lines(json.dumps(body).encode())
    assert len(lines) == 1
    return lines[0]


def test_tools_call_line_matches_prd_example(repo_root):
    body = wire_body(repo_root, "02-tools-call-livre.json")
    body["id"] = 3
    assert one(body) == f"mcp method=tools/call id=3 name=reservar_sala traceparent={TP}"


def test_resources_read_uses_uri_as_name(repo_root):
    body = wire_body(repo_root, "05-resources-read-politica.json")
    assert "name=politica://uso" in one(body)


@pytest.mark.parametrize("method", ["tools/list", "server/discover"])
def test_other_methods_have_dash_name(method):
    assert f"method={method} id=1 name=- " in one({"jsonrpc": "2.0", "id": 1, "method": method, "params": {}})


def test_missing_traceparent_renders_dash():
    line = one({"id": 1, "method": "tools/list", "params": {"_meta": {}}})
    assert line.endswith("traceparent=-")


def test_missing_meta_still_logs_method_and_id():
    line = one({"id": 4, "method": "tools/call", "params": {"name": "listar_salas"}})
    assert line == "mcp method=tools/call id=4 name=listar_salas traceparent=-"


def test_string_and_integer_ids_render_unquoted():
    assert "id=7 " in one({"id": 7, "method": "m"})
    assert "id=3f1a9c0b2d4e " in one({"id": "3f1a9c0b2d4e", "method": "m"})


def test_notification_and_null_id_render_dash():
    assert "id=- " in one({"method": "notifications/x"})
    assert "id=- " in one({"id": None, "method": "m"})


@pytest.mark.parametrize("body", [b'{"jsonrpc": "2.0", "id": 9, "method": ', b"\xff\xfe\x00"])
def test_invalid_json_logs_all_dashes(body):
    assert format_log_lines(body) == [DASH]


def test_array_body_logs_one_line_per_element():
    lines = format_log_lines(json.dumps([{"id": 1, "method": "a"}, {"id": 2, "method": "b"}]).encode())
    assert [ln.split()[1:3] for ln in lines] == [["method=a", "id=1"], ["method=b", "id=2"]]
    assert format_log_lines(b"[]") == [DASH]
    assert format_log_lines(b"42") == [DASH]


def test_values_with_whitespace_are_json_quoted():
    body = {"id": 1, "method": "tools/list", "params": {"_meta": {"traceparent": "a b\nc"}}}
    lines = format_log_lines(json.dumps(body).encode())
    assert len(lines) == 1 and "\n" not in lines[0]
    assert lines[0].endswith('traceparent="a b\\nc"')


# --- ASGI behavior -----------------------------------------------------------

def run(coro):
    return asyncio.run(coro)


def http_scope(method="POST", path="/mcp"):
    return {"type": "http", "method": method, "path": path}


def make_receive(body: bytes, chunk: int | None = None):
    parts = [body] if chunk is None else [body[i:i + chunk] for i in range(0, len(body), chunk)] or [b""]
    queue = [{"type": "http.request", "body": p, "more_body": i < len(parts) - 1} for i, p in enumerate(parts)]

    async def receive():
        if queue:
            return queue.pop(0)
        return {"type": "http.disconnect"}

    return receive


async def noop_send(message):
    pass


def test_line_written_before_inner_app_runs():
    stream = io.StringIO()
    seen = []

    async def inner(scope, receive, send):
        seen.append(stream.getvalue())

    mw = RequestLogMiddleware(inner, stream=stream)
    body = json.dumps({"id": 1, "method": "tools/list"}).encode()
    run(mw(http_scope(), make_receive(body), noop_send))
    assert seen == ["mcp method=tools/list id=1 name=- traceparent=-\n"]


def test_body_replayed_unchanged():
    got = []

    async def inner(scope, receive, send):
        msg = await receive()
        got.append((msg["body"], msg.get("more_body")))

    mw = RequestLogMiddleware(inner, stream=io.StringIO())
    body = json.dumps({"id": 1, "method": "tools/list", "pad": "x" * 100}).encode()
    run(mw(http_scope(), make_receive(body, chunk=10), noop_send))
    assert got == [(body, False)]


def test_only_post_to_mcp_path_is_logged():
    stream = io.StringIO()
    called = []

    async def inner(scope, receive, send):
        called.append(scope["path"])

    mw = RequestLogMiddleware(inner, stream=stream)
    run(mw(http_scope("GET", "/mcp"), make_receive(b""), noop_send))
    run(mw(http_scope("POST", "/other"), make_receive(b"{}"), noop_send))
    assert stream.getvalue() == "" and called == ["/mcp", "/other"]


def test_lifespan_scope_passes_through():
    seen = []

    async def inner(scope, receive, send):
        seen.append(scope["type"])
        assert (await receive())["type"] == "lifespan.startup"
        await send({"type": "lifespan.startup.complete"})

    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "lifespan.startup"}

    mw = RequestLogMiddleware(inner, stream=io.StringIO())
    run(mw({"type": "lifespan"}, receive, send))
    assert seen == ["lifespan"] and sent == [{"type": "lifespan.startup.complete"}]


def test_formatting_failure_falls_back_and_request_is_served(monkeypatch):
    stream = io.StringIO()
    served = []

    def boom(body):
        raise RuntimeError("x")

    monkeypatch.setattr(request_log, "format_log_lines", boom)

    async def inner(scope, receive, send):
        served.append(True)

    mw = RequestLogMiddleware(inner, stream=stream)
    run(mw(http_scope(), make_receive(b"{}"), noop_send))
    assert stream.getvalue() == DASH + "\n" and served == [True]


def test_stream_failure_does_not_break_request():
    class Broken:
        def write(self, s):
            raise OSError("closed")

        def flush(self):
            raise OSError("closed")

    served = []

    async def inner(scope, receive, send):
        served.append(True)

    run(RequestLogMiddleware(inner, stream=Broken())(http_scope(), make_receive(b"{}"), noop_send))
    assert served == [True]
