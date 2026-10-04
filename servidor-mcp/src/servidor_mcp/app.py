"""ASGI app assembly: SDK Streamable HTTP app wrapped by the request log."""

from __future__ import annotations

import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

from servidor_mcp.config import Settings
from servidor_mcp.request_log import RequestLogMiddleware

MCP_PATH = "/mcp"


def build_app(server: MCPServer, settings: Settings, *, log_stream: Any = None) -> RequestLogMiddleware:
    sdk_app = server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        host=settings.host,
    )
    return RequestLogMiddleware(
        sdk_app, path=MCP_PATH, stream=log_stream if log_stream is not None else sys.stderr
    )
