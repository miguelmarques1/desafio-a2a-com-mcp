import time
from types import SimpleNamespace

import pytest
from mcp.shared.exceptions import MCPError
from mcp.types import ElicitRequestFormParams, ElicitResult, ElicitationCapability, ClientCapabilities

from servidor_mcp import mensagens
from servidor_mcp.estado_pedido import EstadoDoPedido, codificar
from servidor_mcp.mrtr import (
    esquema_de_escolha,
    estado_da_rodada,
    exigir_elicitacao_form,
    pedir_escolha,
    resposta_para,
)

CHAVE = "reservar_sala:escolha_de_sala"


def estado(**mudancas):
    base = dict(
        sala="sala-garagem",
        inicio="2026-11-03T14:00:00-03:00",
        fim="2026-11-03T15:00:00-03:00",
        responsavel="Marty",
        alternativas=("sala-fusca", "sala-mirante"),
        expira=int(time.time()) + 600,
    )
    return EstadoDoPedido(**{**base, **mudancas})


def caps(dados):
    return SimpleNamespace(client_capabilities=None if dados is None else ClientCapabilities.model_validate(dados))


def test_pedir_escolha_shape():
    e = estado()
    resultado = pedir_escolha(e)
    assert list(resultado.input_requests) == [CHAVE]
    pergunta = resultado.input_requests[CHAVE]
    assert pergunta.method == "elicitation/create"
    assert isinstance(pergunta.params, ElicitRequestFormParams) and pergunta.params.mode == "form"
    assert pergunta.params.message == "A sala pedida esta ocupada nesse intervalo. Escolha uma alternativa."
    assert pergunta.params.requested_schema == {
        "type": "object",
        "properties": {
            "sala": {
                "type": "string",
                "title": "Sala",
                "description": "Sala alternativa escolhida",
                "enum": ["sala-fusca", "sala-mirante"],
            }
        },
        "required": ["sala"],
    }
    assert resultado.request_state == codificar(e)


def test_single_alternative_uses_enum():
    sala = esquema_de_escolha(("sala-mirante",))["properties"]["sala"]
    assert sala["enum"] == ["sala-mirante"]
    assert "const" not in sala


def test_exigir_elicitacao_form_passes_with_form():
    exigir_elicitacao_form(caps({"elicitation": {"form": {}}}))


@pytest.mark.parametrize("dados", [{}, {"elicitation": {}}, {"elicitation": {"url": {}}}, None])
def test_exigir_elicitacao_form_raises_32021(dados):
    with pytest.raises(MCPError) as exc:
        exigir_elicitacao_form(caps(dados))
    assert exc.value.code == -32021
    assert exc.value.error.message == mensagens.CAPACIDADE_AUSENTE.format(chave=CHAVE)
    assert exc.value.error.data == {"requiredCapabilities": {"elicitation": {"form": {}}}}


def ctx_com(respostas=None, estado_texto=None):
    return SimpleNamespace(input_responses=respostas, request_state=estado_texto)


def test_resposta_para_returns_elicit_result():
    ctx = ctx_com({CHAVE: ElicitResult(action="accept", content={"sala": "sala-fusca"})})
    assert resposta_para(ctx, CHAVE).action == "accept"


@pytest.mark.parametrize(
    "respostas",
    [None, {}, {"outra": ElicitResult(action="decline")}, {CHAVE: {"action": "accept"}}],
)
def test_resposta_para_missing_raises_32602(respostas):
    with pytest.raises(MCPError) as exc:
        resposta_para(ctx_com(respostas), CHAVE)
    assert exc.value.code == -32602
    assert exc.value.error.message == "inputResponses sem resposta para reservar_sala:escolha_de_sala"
    assert exc.value.error.data is None


def test_estado_da_rodada_accepts_valid_state():
    e = estado()
    assert estado_da_rodada(ctx_com(estado_texto=codificar(e))) == e


@pytest.mark.parametrize(
    "texto",
    [
        "garbage",
        None,
        codificar(estado(ferramenta="outra_ferramenta")),
        codificar(estado(expira=int(time.time()) - 1)),
    ],
)
def test_estado_da_rodada_invalid_or_expired(texto):
    with pytest.raises(MCPError) as exc:
        estado_da_rodada(ctx_com(estado_texto=texto))
    assert exc.value.code == -32602
    assert exc.value.error.message == "Invalid or expired requestState"
    assert exc.value.error.data == {"reason": "invalid_request_state"}
