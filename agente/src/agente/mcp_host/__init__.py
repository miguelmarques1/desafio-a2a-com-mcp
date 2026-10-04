"""MCP host client: the agent's inward-facing half, speaking only the MCP wire contract.

Rules for consumers (F08, F09):
- Call `open_task_context(client, ctx.traceparent)` once per new Task, before any `call_tool`;
  on `ProtocolFailure` fail the Task with `failure.message` verbatim.
- Match exhaustively on the four outcome types. Never catch transport exceptions: the client
  already turns them into `ProtocolFailure`.
- Never register an elicitation callback: `InputRequired` always comes back raw.
- `InputRequired.request_state` is opaque. Store it in the Task's private attachment and pass it
  back unchanged to `retry_tool`; never decode, slice, log, or put it in a message, artifact or
  exception text.
- To resume, derive the trace with `TraceContext.for_continuation(stored_trace, ctx.traceparent)`
  and call `retry_tool(..., input_response=accept_response(sala) | decline_response())`.
- Nothing here imports `servidor_mcp`; domain rules stay out of `agente/`.
"""

from agente.mcp_host.client import McpClient, ToolInfo
from agente.mcp_host.outcomes import (
    CompleteError,
    CompleteSuccess,
    InputRequired,
    ProtocolFailure,
    ToolOutcome,
    accept_response,
    decline_response,
)
from agente.mcp_host.task_context import POLICY_URI, RESERVAR_SALA, TaskMcpContext, open_task_context
from agente.mcp_host.trace_context import TraceContext

__all__ = [
    "POLICY_URI",
    "RESERVAR_SALA",
    "CompleteError",
    "CompleteSuccess",
    "InputRequired",
    "McpClient",
    "ProtocolFailure",
    "TaskMcpContext",
    "ToolInfo",
    "ToolOutcome",
    "TraceContext",
    "accept_response",
    "decline_response",
    "open_task_context",
]
