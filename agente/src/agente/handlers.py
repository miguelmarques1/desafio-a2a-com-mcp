"""Extension points: request context, handler protocols and the stub handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from agente import mensagens
from agente.protocol import Message, Part, Role, TaskState
from agente.task_store import TaskHandle


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    text_parts: tuple[str, ...]
    task_id: str | None = None
    context_id: str | None = None

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)

    def to_message(self) -> Message:
        return Message(
            message_id=self.message_id,
            role=Role.USER,
            parts=tuple(Part(t) for t in self.text_parts),
            task_id=self.task_id,
            context_id=self.context_id,
        )


@dataclass(frozen=True)
class RequestContext:
    rpc_id: str | int
    task_id: str
    context_id: str
    is_continuation: bool
    message: IncomingMessage
    traceparent: str | None


class NewTaskHandler(Protocol):
    def __call__(self, ctx: RequestContext, task: TaskHandle) -> Awaitable[None]: ...


class ContinuationHandler(Protocol):
    def __call__(self, ctx: RequestContext, task: TaskHandle) -> Awaitable[None]: ...


@dataclass(frozen=True)
class Handlers:
    new_task: NewTaskHandler
    continuation: ContinuationHandler
    aclose: Callable[[], Awaitable[None]] | None = None


async def stub_new_task_handler(ctx: RequestContext, task: TaskHandle) -> None:
    task.transition(TaskState.FAILED, mensagens.STUB_SKILL_NAO_IMPLEMENTADA)


async def stub_continuation_handler(ctx: RequestContext, task: TaskHandle) -> None:
    task.transition(TaskState.FAILED, mensagens.STUB_CONTINUACAO_NAO_IMPLEMENTADA)
