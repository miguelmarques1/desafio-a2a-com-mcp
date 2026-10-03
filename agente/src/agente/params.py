"""SendMessage / GetTask params validation and message parsing."""

from __future__ import annotations

from typing import Any

from agente import mensagens
from agente.handlers import IncomingMessage
from agente.jsonrpc import content_type_not_supported, invalid_params
from agente.protocol import Role


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and value != ""


def _parse_part(part: Any, index: int) -> str:
    if isinstance(part, dict):
        if isinstance(part.get("text"), str):
            return part["text"]
        if any(key in part for key in ("raw", "url", "data")) and "text" not in part:
            raise content_type_not_supported()
    raise invalid_params(mensagens.DET_MESSAGE_PART_INVALIDA.format(i=index))


def parse_send_message(params: Any) -> IncomingMessage:
    if not isinstance(params, dict):
        raise invalid_params(mensagens.DET_PARAMS_OBJETO)
    message = params.get("message")
    if message is None:
        raise invalid_params(mensagens.DET_MESSAGE_AUSENTE)
    if not isinstance(message, dict):
        raise invalid_params(mensagens.DET_MESSAGE_OBJETO)
    if not _non_empty_str(message.get("messageId")):
        raise invalid_params(mensagens.DET_MESSAGE_ID)
    if message.get("role") != Role.USER.value:
        raise invalid_params(mensagens.DET_MESSAGE_ROLE)
    parts = message.get("parts")
    if not isinstance(parts, list) or not parts:
        raise invalid_params(mensagens.DET_MESSAGE_PARTS)
    texts = tuple(_parse_part(p, i) for i, p in enumerate(parts))
    task_id, context_id = message.get("taskId"), message.get("contextId")
    if "taskId" in message and not _non_empty_str(task_id):
        raise invalid_params(mensagens.DET_MESSAGE_TASK_ID)
    if "contextId" in message and not _non_empty_str(context_id):
        raise invalid_params(mensagens.DET_MESSAGE_CONTEXT_ID)
    return IncomingMessage(
        message_id=message["messageId"],
        text_parts=texts,
        task_id=task_id,
        context_id=context_id,
    )


def parse_get_task(params: Any) -> str:
    if not isinstance(params, dict):
        raise invalid_params(mensagens.DET_PARAMS_OBJETO)
    if "id" not in params or params["id"] is None:
        raise invalid_params(mensagens.DET_ID_AUSENTE)
    if not _non_empty_str(params["id"]):
        raise invalid_params(mensagens.DET_ID_TEXTO)
    return params["id"]
