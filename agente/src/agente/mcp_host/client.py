"""Thin MCP client: one process-wide id counter, one pooled HTTP client, typed outcomes.

Every public operation returns its declared union; transport and protocol problems become
`ProtocolFailure`. Only `asyncio.CancelledError` and programming errors propagate. Nothing is
written to stdout/stderr (the MCP server's request log is the evidence), so `requestState`
can never leak into an agent log.
"""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass
from typing import Any

import httpx

from agente import mensagens
from agente.jsonrpc import render
from agente.mcp_host import wire
from agente.mcp_host.outcomes import (
    ProtocolFailure,
    ToolOutcome,
    error_failure,
    normalize_tool_result,
    unexpected,
)
from agente.mcp_host.trace_context import TraceContext

MAX_TOOL_PAGES = 10


@dataclass(frozen=True)
class ToolInfo:
    name: str
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None


def _schema(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


class McpClient:
    def __init__(
        self,
        url: str,
        *,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._url = url
        self._timeout = timeout
        self._ids = itertools.count(1)
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _exchange(
        self, method: str, params: dict[str, Any], trace: TraceContext, name: str | None = None
    ) -> dict[str, Any] | ProtocolFailure:
        rpc_id = next(self._ids)
        traceparent = trace.header_value(trace.new_span_id())
        body = render(wire.build_request(rpc_id, method, params, traceparent))
        headers = wire.build_headers(method, name)
        try:
            response = await asyncio.wait_for(
                self._http.post(self._url, content=body, headers=headers), self._timeout
            )
        except (httpx.TransportError, asyncio.TimeoutError):
            return ProtocolFailure(mensagens.MCP_INDISPONIVEL)
        decoded = wire.decode_response(response.headers.get("content-type"), response.content, rpc_id)
        if decoded is None:
            return unexpected()
        if "error" in decoded:
            return error_failure(decoded["error"])
        return decoded["result"]

    async def list_tools(self, trace: TraceContext) -> tuple[ToolInfo, ...] | ProtocolFailure:
        tools: list[ToolInfo] = []
        params: dict[str, Any] = {}
        for _ in range(MAX_TOOL_PAGES):
            result = await self._exchange(wire.METHOD_TOOLS_LIST, params, trace)
            if isinstance(result, ProtocolFailure):
                return result
            for entry in result.get("tools") or []:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry["name"]:
                    tools.append(
                        ToolInfo(entry["name"], _schema(entry.get("inputSchema")), _schema(entry.get("outputSchema")))
                    )
            cursor = result.get("nextCursor")
            if not (isinstance(cursor, str) and cursor):
                return tuple(tools)
            params = {"cursor": cursor}
        return unexpected()

    async def read_resource(self, trace: TraceContext, uri: str) -> str | ProtocolFailure:
        """Text of the entry for `uri` (first entry with text when none matches); "" when none."""
        result = await self._exchange(wire.METHOD_RESOURCES_READ, {"uri": uri}, trace, name=uri)
        if isinstance(result, ProtocolFailure):
            return result
        entries = [
            e for e in result.get("contents") or [] if isinstance(e, dict) and isinstance(e.get("text"), str)
        ]
        chosen = next((e for e in entries if e.get("uri") == uri), entries[0] if entries else None)
        return chosen["text"] if chosen is not None else ""

    async def call_tool(self, trace: TraceContext, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        return await self._call(trace, {"name": name, "arguments": arguments}, name)

    async def retry_tool(
        self,
        trace: TraceContext,
        name: str,
        arguments: dict[str, Any],
        *,
        input_key: str,
        input_response: dict[str, Any],
        request_state: str | None,
    ) -> ToolOutcome:
        params: dict[str, Any] = {
            "name": name,
            "arguments": arguments,
            "inputResponses": {input_key: input_response},
        }
        if request_state is not None:
            params["requestState"] = request_state
        return await self._call(trace, params, name)

    async def _call(self, trace: TraceContext, params: dict[str, Any], name: str) -> ToolOutcome:
        result = await self._exchange(wire.METHOD_TOOLS_CALL, params, trace, name=name)
        if isinstance(result, ProtocolFailure):
            return result
        return normalize_tool_result(result)
