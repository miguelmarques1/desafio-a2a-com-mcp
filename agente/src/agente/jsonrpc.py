"""JSON-RPC 2.0 envelope, error model and response rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agente import mensagens

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
TASK_NOT_FOUND = -32001
UNSUPPORTED_OPERATION = -32004
CONTENT_TYPE_NOT_SUPPORTED = -32005
VERSION_NOT_SUPPORTED = -32009

_ERROR_INFO_TYPE = "type.googleapis.com/google.rpc.ErrorInfo"
_ERROR_DOMAIN = "a2a-protocol.org"


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: list[dict[str, Any]] | None = None):
        self.code, self.message, self.data = code, message, data
        super().__init__(message)


class EnvelopeError(JsonRpcError):
    """Invalid envelope; carries whatever id/method were readable for the response and log."""

    def __init__(self, code: int, message: str, rpc_id: Any = None, method: str | None = None):
        super().__init__(code, message)
        self.rpc_id, self.method = rpc_id, method


@dataclass(frozen=True)
class Envelope:
    id: str | int
    method: str
    params: Any


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool))


def parse_envelope(body: bytes) -> Envelope:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise EnvelopeError(PARSE_ERROR, mensagens.ERRO_PARSE) from None

    def invalid(detail: str, rpc_id: Any = None, method: Any = None) -> EnvelopeError:
        return EnvelopeError(
            INVALID_REQUEST,
            mensagens.REQUISICAO_INVALIDA.format(detalhe=detail),
            rpc_id if _valid_id(rpc_id) else None,
            method if isinstance(method, str) else None,
        )

    if isinstance(data, list):
        raise invalid(mensagens.DET_LOTES)
    if not isinstance(data, dict):
        raise invalid(mensagens.DET_CORPO_NAO_OBJETO)
    rpc_id, method = data.get("id"), data.get("method")
    if data.get("jsonrpc") != "2.0":
        raise invalid(mensagens.DET_JSONRPC, rpc_id, method)
    if not isinstance(method, str):
        raise invalid(mensagens.DET_METHOD, rpc_id, method)
    if not _valid_id(rpc_id):
        raise invalid(mensagens.DET_ID, None, method)
    return Envelope(id=rpc_id, method=method, params=data.get("params"))


def success(rpc_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def failure(rpc_id: Any, error: JsonRpcError) -> dict[str, Any]:
    body: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.data is not None:
        body["data"] = error.data
    return {"jsonrpc": "2.0", "id": rpc_id, "error": body}


def _error_info(reason: str, metadata: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "@type": _ERROR_INFO_TYPE,
            "reason": reason,
            "domain": _ERROR_DOMAIN,
            "metadata": metadata,
        }
    ]


def task_not_found(task_id: str) -> JsonRpcError:
    return JsonRpcError(
        TASK_NOT_FOUND,
        mensagens.TASK_NAO_ENCONTRADA.format(id=task_id),
        _error_info("TASK_NOT_FOUND", {"taskId": task_id}),
    )


def task_terminal(task_id: str, state: str) -> JsonRpcError:
    return JsonRpcError(
        UNSUPPORTED_OPERATION,
        mensagens.TASK_TERMINAL.format(id=task_id, state=state),
        _error_info("UNSUPPORTED_OPERATION", {"taskId": task_id, "state": state}),
    )


def task_not_awaiting_input(task_id: str) -> JsonRpcError:
    return JsonRpcError(
        UNSUPPORTED_OPERATION,
        mensagens.TASK_NAO_AGUARDA_ENTRADA.format(id=task_id),
        _error_info("UNSUPPORTED_OPERATION", {"taskId": task_id}),
    )


def content_type_not_supported() -> JsonRpcError:
    return JsonRpcError(
        CONTENT_TYPE_NOT_SUPPORTED,
        mensagens.CONTEUDO_NAO_SUPORTADO,
        _error_info("CONTENT_TYPE_NOT_SUPPORTED", {}),
    )


def version_not_supported(value: str) -> JsonRpcError:
    return JsonRpcError(
        VERSION_NOT_SUPPORTED,
        mensagens.VERSAO_NAO_SUPORTADA.format(valor=value),
        _error_info("VERSION_NOT_SUPPORTED", {"version": value}),
    )


def method_not_found(method: str) -> JsonRpcError:
    return JsonRpcError(METHOD_NOT_FOUND, mensagens.METODO_NAO_ENCONTRADO.format(method=method))


def invalid_params(detail: str) -> JsonRpcError:
    return JsonRpcError(INVALID_PARAMS, mensagens.PARAMETROS_INVALIDOS.format(detalhe=detail))


def internal_error() -> JsonRpcError:
    return JsonRpcError(INTERNAL_ERROR, mensagens.ERRO_INTERNO_AGENTE)


def render(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
