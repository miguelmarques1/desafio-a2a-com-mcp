"""The bridge: MCP `input_required` <-> A2A `TASK_STATE_INPUT_REQUIRED`.

`pause_task` is where an MCP input request becomes a paused Task; `send_retry` is where the
stored `requestState` goes back to the server. The paused record is the only place the agent
keeps MCP protocol state; it lives in the Task's private attachment and never reaches a
response or a log.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from agente import mensagens
from agente.handlers import ContinuationHandler, RequestContext
from agente.mcp_host import (
    RESERVAR_SALA,
    CompleteSuccess,
    InputRequired,
    McpClient,
    ProtocolFailure,
    ToolOutcome,
    TraceContext,
    accept_response,
    decline_response,
)
from agente.protocol import TaskState
from agente.skills.choice_parser import AcceptChoice, DeclineChoice, classify_choice
from agente.skills.outcome_mapping import apply_final_outcome, fail_task
from agente.skills.request_parser import ReservationRequest
from agente.skills.reservar_sala import InputRequiredHandoff
from agente.task_store import TaskHandle


@dataclass(frozen=True)
class PausedRecord:
    tool_name: str
    request: ReservationRequest
    input_key: str
    alternatives: tuple[str, ...]
    policy_version: str
    trace: TraceContext
    request_state: str | None = field(repr=False)

    @classmethod
    def from_handoff(cls, handoff: InputRequiredHandoff) -> PausedRecord:
        outcome = handoff.outcome
        return cls(
            tool_name=RESERVAR_SALA,
            request=handoff.request,
            input_key=outcome.input_key,
            alternatives=outcome.alternatives,
            policy_version=handoff.policy_version,
            trace=handoff.trace,
            request_state=outcome.request_state,
        )

    def next_round(self, outcome: InputRequired) -> PausedRecord:
        return replace(
            self,
            input_key=outcome.input_key,
            alternatives=outcome.alternatives,
            request_state=outcome.request_state,
        )


def render_alternatives(alternatives: tuple[str, ...]) -> str:
    return mensagens.ALTERNATIVAS.format(lista=", ".join(alternatives))


def pause_task(task: TaskHandle, record: PausedRecord) -> None:
    """MCP input_required becomes TASK_STATE_INPUT_REQUIRED."""
    task.set_attachment(record)
    task.transition(TaskState.INPUT_REQUIRED, render_alternatives(record.alternatives))


async def pause_for_choice(ctx: RequestContext, task: TaskHandle, handoff: InputRequiredHandoff) -> None:
    pause_task(task, PausedRecord.from_handoff(handoff))


async def send_retry(
    client: McpClient, ctx: RequestContext, record: PausedRecord, input_response: dict
) -> ToolOutcome:
    """The stored requestState goes back to the server, with a new JSON-RPC id."""
    return await client.retry_tool(
        TraceContext.for_continuation(record.trace, ctx.traceparent),
        record.tool_name,
        record.request.arguments(),
        input_key=record.input_key,
        input_response=input_response,
        request_state=record.request_state,
    )


def apply_decline_outcome(task: TaskHandle, outcome: ToolOutcome) -> None:
    match outcome:
        case CompleteSuccess(structured) if structured.get("reservado") is False:
            task.transition(TaskState.CANCELED, mensagens.RESERVA_RECUSADA)
        case ProtocolFailure(message):
            fail_task(task, message)
        case _:
            fail_task(task, mensagens.MCP_RESPOSTA_INESPERADA)


def make_continuation_handler(client: McpClient) -> ContinuationHandler:
    async def handle(ctx: RequestContext, task: TaskHandle) -> None:
        record = task.get_attachment()
        if not isinstance(record, PausedRecord):
            fail_task(task, mensagens.FALHA_INTERNA)
            return
        choice = classify_choice(ctx.message.text, record.alternatives)
        if choice is None:
            task.transition(TaskState.INPUT_REQUIRED, render_alternatives(record.alternatives))
            return
        task.transition(TaskState.WORKING)
        if isinstance(choice, AcceptChoice):
            outcome = await send_retry(client, ctx, record, accept_response(choice.sala))
            if isinstance(outcome, InputRequired):
                pause_task(task, record.next_round(outcome))
            else:
                apply_final_outcome(task, outcome, record.policy_version)
        elif isinstance(choice, DeclineChoice):
            outcome = await send_retry(client, ctx, record, decline_response())
            apply_decline_outcome(task, outcome)

    return handle
