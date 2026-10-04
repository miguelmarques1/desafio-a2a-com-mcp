"""`reservar-sala` skill: new-Task handler, input-required hand-off and the F08 stub pause hook.

F09 plugs its pause in through `make_reservar_sala_handler(client, on_input_required=...)`.
The agent holds no domain logic: every decision about rooms, times and conflicts comes from MCP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from agente import mensagens
from agente.handlers import NewTaskHandler, RequestContext
from agente.mcp_host import (
    RESERVAR_SALA,
    InputRequired,
    McpClient,
    ProtocolFailure,
    TraceContext,
    open_task_context,
)
from agente.protocol import TaskState
from agente.skills.outcome_mapping import apply_final_outcome, fail_task
from agente.skills.request_parser import ReservationRequest, parse_reservation_request
from agente.task_store import TaskHandle


@dataclass(frozen=True)
class InputRequiredHandoff:
    request: ReservationRequest
    policy_version: str
    trace: TraceContext
    outcome: InputRequired = field(repr=False)


class InputRequiredHandler(Protocol):
    """Called with the Task in WORKING; must leave it terminal or INPUT_REQUIRED."""

    async def __call__(
        self, ctx: RequestContext, task: TaskHandle, handoff: InputRequiredHandoff
    ) -> None: ...


async def stub_input_required_handler(
    ctx: RequestContext, task: TaskHandle, handoff: InputRequiredHandoff
) -> None:
    task.transition(TaskState.FAILED, mensagens.STUB_PAUSA_NAO_IMPLEMENTADA)


def make_reservar_sala_handler(
    client: McpClient,
    *,
    on_input_required: InputRequiredHandler = stub_input_required_handler,
) -> NewTaskHandler:
    async def handle(ctx: RequestContext, task: TaskHandle) -> None:
        request = parse_reservation_request(ctx.message.text)
        if request is None:
            task.transition(TaskState.FAILED, mensagens.PEDIDO_INVALIDO)
            return
        task.transition(TaskState.WORKING)
        context = await open_task_context(client, ctx.traceparent)
        if isinstance(context, ProtocolFailure):
            fail_task(task, context.message)
            return
        outcome = await client.call_tool(context.trace, RESERVAR_SALA, request.arguments())
        if isinstance(outcome, InputRequired):
            handoff = InputRequiredHandoff(request, context.policy_version, context.trace, outcome)
            await on_input_required(ctx, task, handoff)
        else:
            apply_final_outcome(task, outcome, context.policy_version)

    return handle
