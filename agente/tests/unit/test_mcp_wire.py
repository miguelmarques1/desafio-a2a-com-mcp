import json

import pytest

from agente.jsonrpc import render
from agente.mcp_host import accept_response, decline_response
from agente.mcp_host.wire import build_headers, build_meta, build_request, decode_response

TP = "00-4bf92f3577b34da6a3ce929d0e0e4736-5a3c9e17b2d40f86-01"


def expected(wire, name):
    body = json.loads(json.dumps(wire(name)["request"]["body"]))
    body["params"]["_meta"]["traceparent"] = TP
    return body


def same(a, b):
    assert render(a) == render(b)  # equality including key order


def test_meta_has_all_mandatory_fields():
    meta = build_meta(TP)
    assert list(meta) == [
        "io.modelcontextprotocol/protocolVersion",
        "io.modelcontextprotocol/clientInfo",
        "io.modelcontextprotocol/clientCapabilities",
        "traceparent",
    ]
    assert meta["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
    assert meta["io.modelcontextprotocol/clientInfo"] == {"name": "agente-central-de-salas", "version": "1.0.0"}
    assert meta["io.modelcontextprotocol/clientCapabilities"] == {"elicitation": {"form": {}}}
    assert meta["traceparent"] == TP


def test_tools_list_request_matches_wire_01_shape(wire):
    body = expected(wire, "01-tools-list.json")
    same(build_request(body["id"], "tools/list", {}, TP), body)


def test_resources_read_request_matches_wire_05_shape(wire):
    body = expected(wire, "05-resources-read-politica.json")
    same(build_request(body["id"], "resources/read", {"uri": "politica://uso"}, TP), body)


def test_tools_call_request_matches_wire_03_shape(wire):
    body = expected(wire, "03-tools-call-conflito-input-required.json")
    params = {"name": "reservar_sala", "arguments": body["params"]["arguments"]}
    same(build_request(body["id"], "tools/call", params, TP), body)


@pytest.mark.parametrize(
    "name,response",
    [
        ("04-tools-call-retry.json", accept_response("sala-fusca")),
        ("11-tools-call-retry-recusa.json", decline_response()),
    ],
)
def test_retry_request_matches_wire_04_and_11_shape(wire, name, response):
    body = expected(wire, name)
    p = body["params"]
    key = next(iter(p["inputResponses"]))
    assert p["inputResponses"][key] == response
    params = {
        "name": p["name"],
        "arguments": p["arguments"],
        "inputResponses": {key: response},
        "requestState": p["requestState"],
    }
    same(build_request(body["id"], "tools/call", params, TP), body)


def test_headers_per_method():
    base = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28",
    }
    assert build_headers("tools/list") == {**base, "Mcp-Method": "tools/list"}
    assert build_headers("resources/read", "politica://uso") == {
        **base,
        "Mcp-Method": "resources/read",
        "Mcp-Name": "politica://uso",
    }
    assert build_headers("tools/call", "reservar_sala")["Mcp-Name"] == "reservar_sala"


RESP = {"jsonrpc": "2.0", "id": 1, "result": {"a": 1}}


def test_decode_json_body():
    assert decode_response("application/json; charset=utf-8", json.dumps(RESP).encode(), 1) == RESP
    assert decode_response(None, json.dumps(RESP).encode(), 1) == RESP


def test_decode_single_event_sse():
    body = f"event: message\ndata: {json.dumps(RESP)}\n\n".encode()
    assert decode_response("text/event-stream", body, 1) == RESP


def test_decode_sse_multiline_data_and_ignores_notifications():
    note = {"jsonrpc": "2.0", "method": "notifications/progress", "params": {}}
    lines = json.dumps(RESP, indent=1).split("\n")
    body = f"data: {json.dumps(note)}\n\n" + "".join(f"data: {t}\n" for t in lines) + "\n"
    assert decode_response("text/event-stream", body.encode(), 1) == RESP


@pytest.mark.parametrize(
    "body",
    [
        b"plain text",
        b"<html></html>",
        b"[]",
        b"{}",
        b'{"jsonrpc":"2.0"}',
        b'{"jsonrpc":"2.0","id":1,"result":{},"error":{}}',
        b'{"jsonrpc":"2.0","id":99,"result":{}}',
        b"\xff\xfe",
    ],
)
def test_decode_rejects_non_jsonrpc_bodies(body):
    assert decode_response("application/json", body, 1) is None


def test_error_with_null_id_is_accepted():
    err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32602, "message": "x"}}
    assert decode_response("application/json", json.dumps(err).encode(), 1) == err
