"""Request log ASGI middleware: one stderr line per JSON-RPC request."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

_DASH_LINE = "mcp method=- id=- name=- traceparent=-"
_NEEDS_QUOTE = re.compile(r"[\s\x00-\x1f\x7f]")


def _render_id(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return _render_text(value)


def _render_text(value: Any) -> str:
    if not isinstance(value, str):
        return "-"
    if value == "" or _NEEDS_QUOTE.search(value):
        return json.dumps(value)
    return value


def _line_for(message: Any) -> str:
    if not isinstance(message, dict):
        return _DASH_LINE
    method = message.get("method")
    params = message.get("params")
    params = params if isinstance(params, dict) else {}
    name: Any = None
    if method == "tools/call":
        name = params.get("name")
    elif method == "resources/read":
        name = params.get("uri")
    meta = params.get("_meta")
    traceparent = meta.get("traceparent") if isinstance(meta, dict) else None
    return (
        f"mcp method={_render_text(method)} id={_render_id(message.get('id'))} "
        f"name={_render_text(name)} traceparent={_render_text(traceparent)}"
    )


def format_log_lines(body: bytes) -> list[str]:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return [_DASH_LINE]
    if isinstance(data, list):
        return [_line_for(m) for m in data] or [_DASH_LINE]
    return [_line_for(data)]


class RequestLogMiddleware:
    def __init__(self, app: Any, *, path: str = "/mcp", stream: Any = None):
        self.app = app
        self.path = path
        self.stream = stream if stream is not None else sys.stderr

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in (self.path, self.path + "/")
        ):
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        more = True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunks.append(message.get("body", b""))
            more = message.get("more_body", False)
        body = b"".join(chunks)

        try:
            lines = format_log_lines(body)
        except Exception:
            lines = [_DASH_LINE]
        try:
            for line in lines:
                self.stream.write(line + "\n")
            self.stream.flush()
        except Exception:
            pass

        replayed = False

        async def replay() -> dict:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
