import asyncio
import json

import httpx
import pytest

from agente.mcp_host import ProtocolFailure, TaskMcpContext, open_task_context
from agente.mcp_host import ToolInfo, accepts_arguments
from agente.mcp_host.task_context import extract_policy_version


def json_answer(body, status=200):
    return (status, "application/json", body)


TP = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def result_of(wire, name):
    return wire(name)["response"]["body"]["result"]


def scripted(*results):
    """Answer each request in order with the given result (or error body) and the request's id."""
    queue = list(results)

    def answer(request):
        body = json.loads(request.content)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        key = "error" if "code" in item else "result"
        return json_answer({"jsonrpc": "2.0", "id": body["id"], key: item})

    return answer


def policy(text):
    return {"contents": [{"uri": "politica://uso", "mimeType": "text/markdown", "text": text}]}


def tools(*names):
    return {"tools": [{"name": n} for n in names]}


def test_open_sends_tools_list_then_resources_read(mock_mcp, wire):
    m = mock_mcp(scripted(result_of(wire, "01-tools-list.json"), result_of(wire, "05-resources-read-politica.json")))
    ctx = asyncio.run(open_task_context(m.client, TP, required_tool="listar_salas"))
    assert isinstance(ctx, TaskMcpContext)
    assert [b["method"] for b in m.bodies] == ["tools/list", "resources/read"]
    traces = {b["params"]["_meta"]["traceparent"].split("-")[1] for b in m.bodies}
    assert traces == {"4bf92f3577b34da6a3ce929d0e0e4736"} == {ctx.trace.trace_id}
    assert ctx.policy_version == "2026-11-01"
    assert ctx.tool_names == tuple(t["name"] for t in result_of(wire, "01-tools-list.json")["tools"])


def test_missing_required_tool_stops_after_discovery(mock_mcp):
    m = mock_mcp(scripted(tools("listar_salas")))
    out = asyncio.run(open_task_context(m.client, None))
    assert out == ProtocolFailure("Ferramenta reservar_sala nao encontrada no servidor MCP")
    assert len(m.bodies) == 1


@pytest.mark.parametrize(
    "contents",
    [
        policy("# Politica"),
        policy("versao:"),
        policy(" versao: x"),
        policy("VERSAO: x"),
        {"contents": []},
    ],
)
def test_policy_without_version_line(mock_mcp, contents):
    m = mock_mcp(scripted(tools("reservar_sala"), contents))
    out = asyncio.run(open_task_context(m.client, None))
    assert out == ProtocolFailure("Politica de uso sem versao declarada")


def test_policy_version_trimmed_and_crlf(mock_mcp):
    m = mock_mcp(scripted(tools("reservar_sala"), policy("versao:  2026-11-01 \r\n# resto")))
    assert asyncio.run(open_task_context(m.client, None)).policy_version == "2026-11-01"


def test_policy_entry_selected_by_uri(mock_mcp):
    contents = {
        "contents": [
            {"uri": "outro://x", "text": "versao: errada"},
            {"uri": "politica://uso", "text": "versao: certa"},
        ]
    }
    m = mock_mcp(scripted(tools("reservar_sala"), contents))
    assert asyncio.run(open_task_context(m.client, None)).policy_version == "certa"


def test_discovery_failure_propagates_message(mock_mcp):
    m = mock_mcp(scripted(httpx.ConnectError("refused")))
    assert asyncio.run(open_task_context(m.client, None)) == ProtocolFailure("Servidor MCP indisponivel")
    assert len(m.bodies) == 1

    m = mock_mcp(scripted({"code": -32602, "message": "bad"}))
    out = asyncio.run(open_task_context(m.client, None))
    assert out == ProtocolFailure("Erro do servidor MCP: -32602 bad", -32602)
    assert len(m.bodies) == 1


def test_policy_read_failure_propagates(mock_mcp):
    m = mock_mcp(scripted(tools("reservar_sala"), {"code": -32601, "message": "nope"}))
    assert asyncio.run(open_task_context(m.client, None)).code == -32601


@pytest.mark.parametrize(
    "text,expected",
    [
        ("versao: 2026-11-01\n", "2026-11-01"),
        ("versao: 2026-11-01", "2026-11-01"),
        ("versao:x\r\nmais", "x"),
        ("versao:   \n", None),
        ("", None),
        ("\nversao: x", None),
        ("# versao: x", None),
    ],
)
def test_extract_policy_version_matches_server_rule(text, expected):
    assert extract_policy_version(text) == expected


ARGS = {"sala": "s", "inicio": "i", "fim": "f", "responsavel": "r"}
PROPS = {key: {"type": "string"} for key in ARGS}


@pytest.mark.parametrize(
    ("schema", "ok"),
    [
        (None, True),
        ({"type": "object"}, True),
        ({"type": "object", "properties": PROPS, "required": list(ARGS)}, True),
        ({"type": "object", "properties": PROPS, "required": [*ARGS, "extra"]}, False),
        ({"type": "object", "properties": {"sala": {"type": "string"}}}, False),
    ],
)
def test_accepts_arguments_checks_required_and_known_names(schema, ok):
    assert accepts_arguments(ToolInfo("reservar_sala", schema), ARGS) is ok
