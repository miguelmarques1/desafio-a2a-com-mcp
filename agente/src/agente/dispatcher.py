"""Method dispatch: envelope, version, method, params, routing, handler run, settle."""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass
from typing import Any

from agente import jsonrpc, mensagens
from agente.handlers import Handlers, IncomingMessage, RequestContext
from agente.jsonrpc import Envelope, EnvelopeError, JsonRpcError
from agente.params import parse_get_task, parse_send_message
from agente.protocol import TaskState
from agente.request_log import LogFields
from agente.task_store import (
    NotAwaitingInputError,
    TaskImmutableError,
    TaskNotFoundError,
    TaskStore,
    TerminalTaskError,
)

SEND_MESSAGE = "SendMessage"
GET_TASK = "GetTask"
SUPPORTED_VERSION = ("1", "0")


@dataclass(frozen=True)
class DispatchOutcome:
    body: bytes
    log_fields: LogFields


def _version_supported(value: str | None) -> bool:
    if value is None or value.strip() == "":
        return True
    return tuple(value.strip().split(".")[:2]) == SUPPORTED_VERSION


def _referenced_task_id(method: str, params: Any) -> str | None:
    if not isinstance(params, dict):
        return None
    if method == GET_TASK:
        value = params.get("id")
    elif method == SEND_MESSAGE and isinstance(params.get("message"), dict):
        value = params["message"].get("taskId")
    else:
        return None
    return value if isinstance(value, str) else None


class Dispatcher:
    def __init__(self, store: TaskStore, handlers: Handlers, diag_stream: Any = None):
        self._store = store
        self._handlers = handlers
        self._diag_stream = diag_stream

    async def dispatch(
        self, body: bytes, *, a2a_version: str | None, traceparent: str | None
    ) -> DispatchOutcome:
        try:
            envelope = jsonrpc.parse_envelope(body)
        except EnvelopeError as exc:
            return self._error_outcome(exc.rpc_id, exc, LogFields(method=exc.method))
        task_ref = _referenced_task_id(envelope.method, envelope.params)
        fields = LogFields(envelope.method, envelope.id, task_ref, None)
        try:
            if not _version_supported(a2a_version):
                raise jsonrpc.version_not_supported(str(a2a_version))
            if envelope.method == SEND_MESSAGE:
                task_id = await self._send_message(envelope, traceparent)
            elif envelope.method == GET_TASK:
                task_id = parse_get_task(envelope.params)
            else:
                raise jsonrpc.method_not_found(envelope.method)
            snapshot = self._store.snapshot(task_id)
        except JsonRpcError as exc:
            return self._error_outcome(envelope.id, exc, fields)
        except TaskNotFoundError as exc:
            return self._error_outcome(envelope.id, jsonrpc.task_not_found(exc.task_id), fields)
        except Exception:
            self._report_exception()
            return self._error_outcome(envelope.id, jsonrpc.internal_error(), fields)
        state = snapshot["status"]["state"]
        return DispatchOutcome(
            jsonrpc.render(jsonrpc.success(envelope.id, {"task": snapshot})),
            LogFields(envelope.method, envelope.id, snapshot["id"], state),
        )

    # --- helpers ---

    @staticmethod
    def _error_outcome(rpc_id: Any, error: JsonRpcError, fields: LogFields) -> DispatchOutcome:
        return DispatchOutcome(
            jsonrpc.render(jsonrpc.failure(rpc_id, error)),
            LogFields(fields.method, fields.rpc_id, fields.task_id, None),
        )

    async def _send_message(self, envelope: Envelope, traceparent: str | None) -> str:
        incoming: IncomingMessage = parse_send_message(envelope.params)
        user_message = incoming.to_message()
        store = self._store
        if incoming.task_id is None:
            task_id = store.create_task(user_message)
            handler = self._handlers.new_task
        else:
            task_id = incoming.task_id
            try:
                store.begin_continuation(task_id, user_message)
            except TaskNotFoundError:
                raise jsonrpc.task_not_found(task_id) from None
            except TerminalTaskError as exc:
                raise jsonrpc.task_terminal(task_id, exc.state.value) from None
            except NotAwaitingInputError:
                raise jsonrpc.task_not_awaiting_input(task_id) from None
            handler = self._handlers.continuation
        handle = store.handle(task_id)
        ctx = RequestContext(
            rpc_id=envelope.id,
            task_id=task_id,
            context_id=handle.context_id,
            is_continuation=incoming.task_id is not None,
            message=incoming,
            traceparent=traceparent,
        )
        try:
            try:
                await handler(ctx, handle)
            except Exception:
                self._report_exception()
                try:
                    handle.transition(TaskState.FAILED, mensagens.FALHA_INTERNA)
                except TaskImmutableError:
                    pass
            store.settle(task_id)
        finally:
            store.end_claim(task_id)
        return task_id

    def _report_exception(self) -> None:
        """Write the exception type and stack frames only: never its message or locals."""
        exc = sys.exc_info()[1]
        if exc is None:
            return
        frames = traceback.extract_tb(exc.__traceback__)
        lines = [f"agente: excecao nao tratada: {type(exc).__name__}"]
        lines += [f"  em {f.filename}:{f.lineno} {f.name}" for f in frames]
        try:
            stream = self._diag_stream if self._diag_stream is not None else sys.stderr
            stream.write("\n".join(lines) + "\n")
            stream.flush()
        except Exception:
            pass
