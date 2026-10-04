"""MCP 2026-07-28 wire format: stateless request envelope, mirrored headers, response decoding."""

from __future__ import annotations

import json
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
CLIENT_INFO = {"name": "agente-central-de-salas", "version": "1.0.0"}
CLIENT_CAPABILITIES = {"elicitation": {"form": {}}}
ACCEPT = "application/json, text/event-stream"

METHOD_TOOLS_LIST = "tools/list"
METHOD_TOOLS_CALL = "tools/call"
METHOD_RESOURCES_READ = "resources/read"


def build_meta(traceparent: str) -> dict[str, Any]:
    return {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": dict(CLIENT_INFO),
        "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
        "traceparent": traceparent,
    }


def build_request(rpc_id: int, method: str, params: dict[str, Any], traceparent: str) -> dict[str, Any]:
    """`params` keeps its own order; `_meta` always goes last."""
    return {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": method,
        "params": {**params, "_meta": build_meta(traceparent)},
    }


def build_headers(method: str, name: str | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": ACCEPT,
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if name is not None:
        headers["Mcp-Name"] = name
    return headers


def _is_response(value: Any, rpc_id: int) -> bool:
    """A JSON-RPC response to this request; only an error may carry a null id (SDK ladder)."""
    if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
        return False
    has_result, has_error = "result" in value, "error" in value
    if has_result == has_error:
        return False
    response_id = value.get("id")
    if has_result:
        return isinstance(value["result"], dict) and _same_id(response_id, rpc_id)
    return isinstance(value["error"], dict) and (response_id is None or _same_id(response_id, rpc_id))


def _same_id(value: Any, rpc_id: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == rpc_id


def _loads(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


def _sse_events(text: str) -> list[str]:
    events: list[str] = []
    data: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line == "":
            if data:
                events.append("\n".join(data))
            data = []
        elif line.startswith("data:"):
            value = line[5:]
            data.append(value[1:] if value.startswith(" ") else value)
    if data:
        events.append("\n".join(data))
    return events


def decode_response(content_type: str | None, body: bytes, rpc_id: int) -> dict[str, Any] | None:
    """Return the JSON-RPC response object for this request, or None when there is none."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    kind = (content_type or "").split(";")[0].strip().lower()
    if kind == "text/event-stream":
        for event in _sse_events(text):
            candidate = _loads(event)
            if _is_response(candidate, rpc_id):
                return candidate
        return None
    candidate = _loads(text)
    return candidate if _is_response(candidate, rpc_id) else None
