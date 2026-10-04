import json

import pytest

from agente import jsonrpc
from agente.jsonrpc import EnvelopeError, parse_envelope


@pytest.mark.parametrize("body", [b'{"jsonrpc": "2.0", "id"', b"\xff\xfe\x00"])
def test_invalid_json_and_non_utf8_return_parse_error(body):
    with pytest.raises(EnvelopeError) as info:
        parse_envelope(body)
    assert info.value.code == -32700
    assert info.value.message == "Erro de parse: o corpo nao e JSON valido"
    assert info.value.rpc_id is None


DET = "Requisicao invalida: "
BAD_ID = "id ausente ou com tipo invalido"


@pytest.mark.parametrize(
    ("body", "detail", "echoed"),
    [
        ([], "lotes nao sao suportados", None),
        ([{"jsonrpc": "2.0"}], "lotes nao sao suportados", None),
        ("x", "corpo deve ser um objeto JSON", None),
        (7, "corpo deve ser um objeto JSON", None),
        ({"id": 1, "method": "GetTask"}, 'jsonrpc deve ser "2.0"', 1),
        ({"jsonrpc": "1.0", "id": 1, "method": "GetTask"}, 'jsonrpc deve ser "2.0"', 1),
        ({"jsonrpc": "2.0", "id": 1}, "method ausente ou nao textual", 1),
        ({"jsonrpc": "2.0", "id": 1, "method": 5}, "method ausente ou nao textual", 1),
        ({"jsonrpc": "2.0", "method": "GetTask"}, BAD_ID, None),
        ({"jsonrpc": "2.0", "id": None, "method": "GetTask"}, BAD_ID, None),
        ({"jsonrpc": "2.0", "id": 1.5, "method": "GetTask"}, BAD_ID, None),
        ({"jsonrpc": "2.0", "id": True, "method": "GetTask"}, BAD_ID, None),
        ({"jsonrpc": "2.0", "id": {}, "method": "GetTask"}, BAD_ID, None),
    ],
)
def test_invalid_request_variants(body, detail, echoed):
    with pytest.raises(EnvelopeError) as info:
        parse_envelope(json.dumps(body).encode())
    assert info.value.code == -32600
    assert info.value.message == DET + detail
    assert info.value.rpc_id == echoed


@pytest.mark.parametrize("rpc_id", ["9c1e04aa77b2", 3])
def test_valid_envelope_accepts_string_and_integer_ids(rpc_id):
    body = {"jsonrpc": "2.0", "id": rpc_id, "method": "GetTask", "params": {"id": "t"}}
    env = parse_envelope(json.dumps(body).encode())
    assert (env.id, env.method, env.params) == (rpc_id, "GetTask", {"id": "t"})
    assert jsonrpc.success(rpc_id, {})["id"] == rpc_id


def test_success_and_error_response_key_order():
    assert list(jsonrpc.success(1, {})) == ["jsonrpc", "id", "result"]
    err = jsonrpc.failure(1, jsonrpc.task_not_found("t"))
    assert list(err) == ["jsonrpc", "id", "error"]
    assert list(err["error"]) == ["code", "message", "data"]
    assert list(jsonrpc.failure(1, jsonrpc.internal_error())["error"]) == ["code", "message"]


@pytest.mark.parametrize(
    ("error", "code", "reason"),
    [
        (jsonrpc.task_not_found("t"), -32001, "TASK_NOT_FOUND"),
        (jsonrpc.task_terminal("t", "TASK_STATE_FAILED"), -32004, "UNSUPPORTED_OPERATION"),
        (jsonrpc.task_not_awaiting_input("t"), -32004, "UNSUPPORTED_OPERATION"),
        (jsonrpc.content_type_not_supported(), -32005, "CONTENT_TYPE_NOT_SUPPORTED"),
        (jsonrpc.version_not_supported("2.0"), -32009, "VERSION_NOT_SUPPORTED"),
    ],
)
def test_a2a_errors_carry_error_info(error, code, reason):
    assert error.code == code
    info = error.data[0]
    assert info["@type"] == "type.googleapis.com/google.rpc.ErrorInfo"
    assert (info["reason"], info["domain"]) == (reason, "a2a-protocol.org")
    assert all(isinstance(v, str) for v in info["metadata"].values())


def test_standard_errors_have_no_data():
    for error in (
        jsonrpc.method_not_found("X"),
        jsonrpc.invalid_params("x"),
        jsonrpc.internal_error(),
        EnvelopeError(-32700, "m"),
    ):
        assert "data" not in jsonrpc.failure(1, error)["error"]


def test_render_is_compact_utf8_without_ascii_escaping():
    raw = jsonrpc.render({"a": "Joao", "b": "João", "c": [1, 2]})
    assert raw == '{"a":"Joao","b":"João","c":[1,2]}'.encode()
