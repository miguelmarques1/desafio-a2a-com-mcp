"""Normalized `tools/call` outcomes and the input-response builders."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agente import mensagens


@dataclass(frozen=True)
class CompleteSuccess:
    structured: dict[str, Any]


@dataclass(frozen=True)
class CompleteError:
    text: str


@dataclass(frozen=True)
class InputRequired:
    input_key: str
    alternatives: tuple[str, ...]
    request_state: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class ProtocolFailure:
    message: str
    code: int | None = None


ToolOutcome = CompleteSuccess | CompleteError | InputRequired | ProtocolFailure

_UNEXPECTED = ProtocolFailure(mensagens.MCP_RESPOSTA_INESPERADA)
_UNSUPPORTED = ProtocolFailure(mensagens.MCP_PEDIDO_NAO_SUPORTADO)


def unexpected() -> ProtocolFailure:
    return _UNEXPECTED


def accept_response(sala: str) -> dict[str, Any]:
    return {"action": "accept", "content": {"sala": sala}}


def decline_response() -> dict[str, Any]:
    return {"action": "decline"}


def error_failure(error: dict[str, Any]) -> ProtocolFailure:
    code = error.get("code")
    if not isinstance(code, int) or isinstance(code, bool):
        return _UNEXPECTED
    message = error.get("message")
    detail = f"{code} {message.strip()}".strip() if isinstance(message, str) else str(code)
    return ProtocolFailure(mensagens.MCP_ERRO.format(detalhe=detail), code)


def _text_blocks(result: dict[str, Any]) -> list[str]:
    content = result.get("content")
    if not isinstance(content, list):
        return []
    return [
        block["text"]
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    ]


def _alternatives(schema: Any) -> tuple[str, ...] | None:
    properties = schema.get("properties") if isinstance(schema, dict) else None
    sala = properties.get("sala") if isinstance(properties, dict) else None
    if not isinstance(sala, dict):
        return None
    enum = sala.get("enum")
    if enum is not None:
        ok = isinstance(enum, list) and enum and all(isinstance(v, str) and v for v in enum)
        return tuple(enum) if ok else None
    const = sala.get("const")
    return (const,) if isinstance(const, str) and const else None


def _input_required(result: dict[str, Any]) -> ToolOutcome:
    requests = result.get("inputRequests")
    if not isinstance(requests, dict) or len(requests) != 1:
        return _UNSUPPORTED
    key, request = next(iter(requests.items()))
    if not isinstance(request, dict) or request.get("method") != "elicitation/create":
        return _UNSUPPORTED
    params = request.get("params")
    if not isinstance(params, dict) or params.get("mode", "form") != "form":
        return _UNSUPPORTED
    alternatives = _alternatives(params.get("requestedSchema"))
    if alternatives is None:
        return _UNSUPPORTED
    state = result.get("requestState")
    if state is not None and not (isinstance(state, str) and state):
        return _UNSUPPORTED
    return InputRequired(input_key=key, alternatives=alternatives, request_state=state)


def normalize_tool_result(result: dict[str, Any]) -> ToolOutcome:
    result_type = result.get("resultType", "complete")
    if result_type == "input_required":
        return _input_required(result)
    if result_type != "complete":
        return _UNEXPECTED
    if result.get("isError") is True:
        texts = _text_blocks(result)
        return CompleteError("\n".join(texts)) if texts else _UNEXPECTED
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return CompleteSuccess(json.loads(json.dumps(structured)))
    for text in _text_blocks(result)[:1]:
        try:
            parsed = json.loads(text)
        except ValueError:
            break
        if isinstance(parsed, dict):
            return CompleteSuccess(parsed)
    return _UNEXPECTED
