import copy

import pytest

from agente.mcp_host import (
    CompleteError,
    CompleteSuccess,
    InputRequired,
    ProtocolFailure,
    accept_response,
    decline_response,
)
from agente.mcp_host.outcomes import error_failure, normalize_tool_result

UNEXPECTED = "Resposta inesperada do servidor MCP"
UNSUPPORTED = "Pedido de entrada nao suportado pelo agente"
STATE = "v1." + "A" * 61


def result_of(wire, name):
    return wire(name)["response"]["body"]["result"]


def input_required(**overrides):
    result = {
        "resultType": "input_required",
        "inputRequests": {
            "k": {
                "method": "elicitation/create",
                "params": {
                    "message": "m",
                    "mode": "form",
                    "requestedSchema": {"properties": {"sala": {"enum": ["a", "b"]}}},
                },
            }
        },
        "requestState": STATE,
    }
    result.update(overrides)
    return result


def test_wire_02_is_complete_success(wire):
    result = result_of(wire, "02-tools-call-livre.json")
    outcome = normalize_tool_result(result)
    assert isinstance(outcome, CompleteSuccess)
    assert outcome.structured == result["structuredContent"]
    assert list(outcome.structured) == list(result["structuredContent"])


def test_wire_11_decline_is_complete_success_with_reservado_false(wire):
    outcome = normalize_tool_result(result_of(wire, "11-tools-call-retry-recusa.json"))
    assert isinstance(outcome, CompleteSuccess)
    assert outcome.structured["reservado"] is False
    assert outcome.structured["motivo"] == "recusado"


@pytest.mark.parametrize("text", ["Sala inexistente: sala-delorean", "Error executing tool reservar_sala: 1 validation error"])
def test_is_error_text_is_verbatim(text):
    result = {"content": [{"type": "text", "text": text}], "isError": True, "resultType": "complete"}
    assert normalize_tool_result(result) == CompleteError(text)


def test_multiple_text_blocks_joined_with_newline():
    result = {
        "isError": True,
        "content": [{"type": "text", "text": "a"}, {"type": "image", "data": "x"}, {"type": "text", "text": "b"}],
    }
    assert normalize_tool_result(result) == CompleteError("a\nb")


def test_is_error_without_text_is_unexpected():
    assert normalize_tool_result({"isError": True, "content": []}) == ProtocolFailure(UNEXPECTED)


def test_missing_structured_content_falls_back_to_text_json():
    result = {"content": [{"type": "text", "text": '{"reservado": true}'}]}
    assert normalize_tool_result(result) == CompleteSuccess({"reservado": True})


@pytest.mark.parametrize("content", [[], [{"type": "text", "text": "nao json"}], [{"type": "text", "text": "[1]"}]])
def test_missing_payload_is_unexpected(content):
    assert normalize_tool_result({"content": content}) == ProtocolFailure(UNEXPECTED)


def test_structured_content_is_detached_copy():
    result = {"structuredContent": {"a": {"b": 1}}}
    outcome = normalize_tool_result(result)
    result["structuredContent"]["a"]["b"] = 2
    assert outcome.structured == {"a": {"b": 1}}


def test_wire_03_is_input_required(wire):
    result = result_of(wire, "03-tools-call-conflito-input-required.json")
    outcome = normalize_tool_result(result)
    assert isinstance(outcome, InputRequired)
    assert outcome.input_key == "__main__:escolha_de_sala"
    assert outcome.alternatives == ("sala-fusca", "sala-mirante")
    assert outcome.request_state == result["requestState"]


def test_const_gives_single_alternative():
    result = input_required()
    schema = result["inputRequests"]["k"]["params"]["requestedSchema"]
    schema["properties"]["sala"] = {"const": "sala-mirante"}
    assert normalize_tool_result(result).alternatives == ("sala-mirante",)


def test_enum_wins_over_const():
    result = input_required()
    result["inputRequests"]["k"]["params"]["requestedSchema"]["properties"]["sala"]["const"] = "x"
    assert normalize_tool_result(result).alternatives == ("a", "b")


def test_absent_mode_counts_as_form():
    result = input_required()
    del result["inputRequests"]["k"]["params"]["mode"]
    assert isinstance(normalize_tool_result(result), InputRequired)


def _mutated(mutate):
    result = copy.deepcopy(input_required())
    mutate(result)
    return result


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["inputRequests"].update(extra=r["inputRequests"]["k"]),
        lambda r: r["inputRequests"].clear(),
        lambda r: r["inputRequests"]["k"].update(method="sampling/createMessage"),
        lambda r: r["inputRequests"]["k"]["params"].update(mode="url"),
        lambda r: r["inputRequests"]["k"]["params"]["requestedSchema"]["properties"].clear(),
        lambda r: r["inputRequests"]["k"]["params"]["requestedSchema"]["properties"].update(sala={"enum": []}),
        lambda r: r["inputRequests"]["k"]["params"]["requestedSchema"]["properties"].update(sala={"enum": ["a", 1]}),
        lambda r: r.update(requestState=""),
        lambda r: r.update(requestState=123),
        lambda r: r.update(inputRequests=["x"]),
    ],
)
def test_unsupported_input_required_shapes(mutate):
    assert normalize_tool_result(_mutated(mutate)) == ProtocolFailure(UNSUPPORTED)


def test_absent_request_state_is_none():
    result = input_required()
    del result["requestState"]
    assert normalize_tool_result(result).request_state is None


def test_unknown_result_type_is_unexpected():
    assert normalize_tool_result({"resultType": "task"}) == ProtocolFailure(UNEXPECTED)


def test_error_failure_rendering():
    assert error_failure({"code": -32602, "message": " bad "}) == ProtocolFailure(
        "Erro do servidor MCP: -32602 bad", -32602
    )
    assert error_failure({"code": -32602}).message == "Erro do servidor MCP: -32602"
    assert error_failure({"code": "x", "message": "m"}) == ProtocolFailure(UNEXPECTED)


def test_request_state_hidden_from_repr():
    outcome = InputRequired("k", ("a",), "S" * 64)
    assert "S" * 64 not in repr(outcome) and "S" * 64 not in str(outcome)


def test_input_response_builders(wire):
    p4 = wire("04-tools-call-retry.json")["request"]["body"]["params"]["inputResponses"]
    p11 = wire("11-tools-call-retry-recusa.json")["request"]["body"]["params"]["inputResponses"]
    assert accept_response("sala-fusca") == next(iter(p4.values()))
    assert decline_response() == next(iter(p11.values()))
