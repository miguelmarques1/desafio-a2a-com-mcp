"""Shared execution-error tool result (text identical to the policy message, no SDK prefix)."""

from __future__ import annotations

from mcp.types import CallToolResult, TextContent


def erro_de_execucao(mensagem: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=mensagem)], is_error=True)
