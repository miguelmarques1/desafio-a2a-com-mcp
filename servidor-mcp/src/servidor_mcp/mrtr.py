"""MCP-typed helpers for the Multi Round-Trip Request flow."""

from __future__ import annotations

from typing import Any

from mcp.shared.exceptions import MCPError
from mcp.types import (
    MISSING_REQUIRED_CLIENT_CAPABILITY,
    ElicitRequest,
    ElicitRequestFormParams,
    ElicitResult,
    InputRequiredResult,
    MissingRequiredClientCapabilityErrorData,
)

from servidor_mcp import mensagens
from servidor_mcp.estado_pedido import (
    CHAVE_ESCOLHA,
    FERRAMENTA,
    EstadoDoPedido,
    codificar,
    decodificar,
    expirado,
)
from servidor_mcp.request_context import declares_form_elicitation

INVALID_PARAMS = -32602


def esquema_de_escolha(alternativas: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "sala": {
                "type": "string",
                "title": mensagens.CAMPO_SALA_TITULO,
                "description": mensagens.CAMPO_SALA_DESCRICAO,
                "enum": list(alternativas),
            }
        },
        "required": ["sala"],
    }


def pedir_escolha(estado: EstadoDoPedido) -> InputRequiredResult:
    """One form elicitation; the plaintext payload is sealed by the SDK boundary."""
    pergunta = ElicitRequest(
        params=ElicitRequestFormParams(
            message=mensagens.MENSAGEM_ESCOLHA,
            requested_schema=esquema_de_escolha(estado.alternativas),
        )
    )
    return InputRequiredResult(
        input_requests={estado.chave: pergunta},
        request_state=codificar(estado),
    )


def exigir_elicitacao_form(ctx: Any) -> None:
    if declares_form_elicitation(ctx):
        return
    dados = MissingRequiredClientCapabilityErrorData.model_validate(
        {"requiredCapabilities": {"elicitation": {"form": {}}}}
    )
    raise MCPError(
        code=MISSING_REQUIRED_CLIENT_CAPABILITY,
        message=mensagens.CAPACIDADE_AUSENTE.format(chave=CHAVE_ESCOLHA),
        data=dados.model_dump(by_alias=True, mode="json", exclude_none=True),
    )


def estado_invalido() -> MCPError:
    """Same shape as the SDK boundary's own rejection, so clients see one error."""
    return MCPError(
        code=INVALID_PARAMS,
        message=mensagens.ESTADO_INVALIDO,
        data={"reason": "invalid_request_state"},
    )


def resposta_ausente(chave: str) -> MCPError:
    return MCPError(code=INVALID_PARAMS, message=mensagens.RESPOSTA_AUSENTE.format(chave=chave))


def resposta_para(ctx: Any, chave: str) -> ElicitResult:
    respostas = ctx.input_responses
    resposta = respostas.get(chave) if respostas else None
    if not isinstance(resposta, ElicitResult):
        raise resposta_ausente(chave)
    return resposta


def estado_da_rodada(ctx: Any) -> EstadoDoPedido:
    texto = ctx.request_state
    estado = decodificar(texto) if isinstance(texto, str) else None
    if estado is None or estado.ferramenta != FERRAMENTA or expirado(estado):
        raise estado_invalido()
    return estado
