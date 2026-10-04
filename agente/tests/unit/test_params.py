import pytest

from agente.jsonrpc import JsonRpcError
from agente.params import parse_get_task, parse_send_message


def good(**overrides):
    message = {"messageId": "msg-1", "role": "ROLE_USER", "parts": [{"text": "a"}]}
    message.update(overrides)
    return {"message": message}


def test_send_message_params_from_wire_08(wire):
    params = wire("08-a2a-send-message.json")["request"]["body"]["params"]
    incoming = parse_send_message(params)
    assert incoming.message_id == "msg-6ae2ad6802e5"
    assert incoming.text.startswith("reservar sala=sala-garagem")
    assert incoming.task_id is None and incoming.context_id is None


def test_send_message_continuation_params_from_wire_10(wire):
    params = wire("10-a2a-send-message-continuacao.json")["request"]["body"]["params"]
    incoming = parse_send_message(params)
    assert incoming.task_id == "task-3f658e57d468"
    assert incoming.text == "escolha=sala-mirante"


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        (None, "params deve ser um objeto"),
        ([], "params deve ser um objeto"),
        ({}, "params.message ausente"),
        ({"message": "x"}, "params.message deve ser um objeto"),
        (good(messageId=""), "params.message.messageId deve ser texto nao vazio"),
        (good(messageId=3), "params.message.messageId deve ser texto nao vazio"),
        (good(role="ROLE_AGENT"), "params.message.role deve ser ROLE_USER"),
        (good(parts=[]), "params.message.parts deve ser uma lista nao vazia"),
        (good(parts="x"), "params.message.parts deve ser uma lista nao vazia"),
        (good(parts=[{"text": "a"}, "x"]), "params.message.parts[1] invalida"),
        (good(parts=[{"text": 3}]), "params.message.parts[0] invalida"),
        (good(parts=[{"mediaType": "x"}]), "params.message.parts[0] invalida"),
        (good(taskId=""), "params.message.taskId deve ser texto nao vazio"),
        (good(taskId=5), "params.message.taskId deve ser texto nao vazio"),
        (good(contextId=""), "params.message.contextId deve ser texto nao vazio"),
    ],
)
def test_send_message_invalid_params(params, detail):
    with pytest.raises(JsonRpcError) as info:
        parse_send_message(params)
    assert info.value.code == -32602
    assert info.value.message == f"Parametros invalidos: {detail}"


@pytest.mark.parametrize("part", [{"raw": "AAAA"}, {"url": "http://x"}, {"data": {"a": 1}}])
def test_non_text_parts_return_32005(part):
    with pytest.raises(JsonRpcError) as info:
        parse_send_message(good(parts=[part]))
    assert info.value.code == -32005
    assert info.value.message == (
        "Tipo de conteudo nao suportado: o agente aceita apenas partes de texto"
    )


def test_text_joins_parts_with_single_space():
    incoming = parse_send_message(good(parts=[{"text": "a"}, {"text": "b"}]))
    assert incoming.text == "a b"
    assert incoming.text_parts == ("a", "b")
    assert [p.text for p in incoming.to_message().parts] == ["a", "b"]


def test_ignored_fields_are_accepted():
    params = good(extensions=["x"], metadata={"a": 1})
    params.update({"configuration": {"returnImmediately": True}, "metadata": {}, "tenant": "t"})
    assert parse_send_message(params).message_id == "msg-1"


def test_context_id_is_kept_as_received():
    incoming = parse_send_message(good(contextId="ctx-abc"))
    assert incoming.to_message().context_id == "ctx-abc"


def test_get_task_params():
    assert parse_get_task({"id": "task-1"}) == "task-1"
    assert parse_get_task({"id": "task-1", "historyLength": 2, "tenant": "t"}) == "task-1"
    for params, detail in (
        ({}, "params.id ausente"),
        ({"id": ""}, "params.id deve ser texto nao vazio"),
        ({"id": 5}, "params.id deve ser texto nao vazio"),
        (None, "params deve ser um objeto"),
    ):
        with pytest.raises(JsonRpcError) as info:
            parse_get_task(params)
        assert info.value.code == -32602
        assert info.value.message == f"Parametros invalidos: {detail}"
