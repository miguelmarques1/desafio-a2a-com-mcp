"""Per-Task MCP context: discovery first, then the policy resource."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agente import mensagens
from agente.mcp_host.client import McpClient, ToolInfo
from agente.mcp_host.outcomes import ProtocolFailure
from agente.mcp_host.trace_context import TraceContext

RESERVAR_SALA = "reservar_sala"
POLICY_URI = "politica://uso"
_VERSION_PREFIX = "versao:"


@dataclass(frozen=True)
class TaskMcpContext:
    trace: TraceContext
    tools: tuple[ToolInfo, ...]
    policy_version: str

    @property
    def tool_names(self) -> tuple[str, ...]:
        return tuple(tool.name for tool in self.tools)

    def tool(self, name: str) -> ToolInfo | None:
        return next((tool for tool in self.tools if tool.name == name), None)


def accepts_arguments(tool: ToolInfo, arguments: Mapping[str, Any]) -> bool:
    """Shape check against the discovered `inputSchema`: required names sent, no unknown names."""
    schema = tool.input_schema
    if schema is None:
        return True
    required = schema.get("required")
    if isinstance(required, list) and not set(required) <= set(arguments):
        return False
    properties = schema.get("properties")
    return not isinstance(properties, dict) or set(arguments) <= set(properties)


def extract_policy_version(text: str) -> str | None:
    first_line = text.split("\n", 1)[0].removesuffix("\r")
    if not first_line.startswith(_VERSION_PREFIX):
        return None
    return first_line[len(_VERSION_PREFIX):].strip() or None


async def open_task_context(
    client: McpClient, traceparent: str | None, *, required_tool: str = RESERVAR_SALA
) -> TaskMcpContext | ProtocolFailure:
    trace = TraceContext.for_task(traceparent)
    tools = await client.list_tools(trace)
    if isinstance(tools, ProtocolFailure):
        return tools
    if required_tool not in {tool.name for tool in tools}:
        return ProtocolFailure(mensagens.MCP_FERRAMENTA_AUSENTE.format(nome=required_tool))
    text = await client.read_resource(trace, POLICY_URI)
    if isinstance(text, ProtocolFailure):
        return text
    version = extract_policy_version(text)
    if version is None:
        return ProtocolFailure(mensagens.POLITICA_SEM_VERSAO)
    return TaskMcpContext(trace=trace, tools=tools, policy_version=version)
