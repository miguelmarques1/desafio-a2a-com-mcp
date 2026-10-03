import json

import pytest
from mcp.server.mcpserver import Context, MCPServer

from servidor_mcp.request_context import declares_form_elicitation

SERVER_INFO = {"name": "central-de-salas", "version": "1.0.0"}
PV_KEY = "io.modelcontextprotocol/protocolVersion"
CAPS_KEY = "io.modelcontextprotocol/clientCapabilities"


def register_probe(server: MCPServer, dominio) -> None:
    @server.tool()
    def sonda_capacidades(ctx: Context) -> dict:
        """Test-only probe."""
        return {"form": declares_form_elicitation(ctx)}


def register_dummy(server: MCPServer, dominio) -> None:
    @server.tool()
    def ferramenta_falsa(x: str) -> str:
        """Test-only dummy."""
        return x


def test_tools_list_first_request_succeeds_without_initialize(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = mcp_post(client, "tools/list")
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["resultType"] == "complete"
    assert isinstance(result["tools"], list)
    assert "mcp-session-id" not in r.headers


def test_responses_are_plain_json(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    ok = mcp_post(client, "tools/list")
    bad = mcp_post(client, "tools/list", drop_meta=(PV_KEY,))
    for r in (ok, bad):
        assert r.headers["content-type"].startswith("application/json")
        assert json.loads(r.text)
        assert "event:" not in r.text and not r.text.startswith("data:")


def test_missing_protocol_version_returns_32602_http_400(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = mcp_post(client, "tools/list", drop_meta=(PV_KEY,))
    assert r.status_code == 400 and r.json()["error"]["code"] == -32602


def test_missing_client_capabilities_after_valid_request_returns_32602_http_400(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    assert mcp_post(client, "tools/list").status_code == 200
    r = mcp_post(client, "tools/list", drop_meta=(CAPS_KEY,))
    assert r.status_code == 400 and r.json()["error"]["code"] == -32602


def test_missing_meta_object_returns_32602_http_400(fresh_app):
    client, _, _ = fresh_app()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "tools/list",
    }
    for params in ({}, {"_meta": "texto"}):
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": params}
        r = client.post("/mcp", json=body, headers=headers)
        assert r.status_code == 400 and r.json()["error"]["code"] == -32602


def test_meta_is_checked_before_headers(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = mcp_post(client, "tools/list", drop_meta=(PV_KEY,), headers={"Mcp_Method": "tools/call"})
    assert r.json()["error"]["code"] == -32602


def test_mcp_method_header_mismatch_returns_32020(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = mcp_post(client, "tools/list", headers={"Mcp_Method": "tools/call"})
    assert r.status_code == 400 and r.json()["error"]["code"] == -32020


def test_protocol_version_header_mismatch_returns_32020(fresh_app, mcp_post):
    # SDK limitation (see progress.md): a header naming a handshake-era version
    # ("2025-11-25") or an absent header is routed to the SDK's legacy path and
    # served (200); only a header the modern entry owns is checked against the body.
    client, _, _ = fresh_app()
    r = mcp_post(client, "tools/list", headers={"MCP_Protocol_Version": "2099-01-01"})
    assert r.status_code == 400 and r.json()["error"]["code"] == -32020


@pytest.mark.parametrize(
    "method,params,wrong",
    [
        ("tools/call", {"name": "listar_salas", "arguments": {}}, "outra"),
        ("resources/read", {"uri": "politica://uso"}, "politica://outra"),
    ],
)
def test_mcp_name_header_mismatch_returns_32020(fresh_app, mcp_post, method, params, wrong):
    client, _, _ = fresh_app()
    r = mcp_post(client, method, params, headers={"Mcp_Name": wrong})
    assert r.status_code == 400 and r.json()["error"]["code"] == -32020


def test_invalid_json_returns_32700(fresh_app):
    client, _, _ = fresh_app()
    r = client.post(
        "/mcp",
        content=b'{"jsonrpc": "2.0", "id": 9, "method": ',
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == -32700


def test_discover_declares_tools_and_resources(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = mcp_post(client, "server/discover", id="a1b2c3d4e5f6")
    assert r.status_code == 200
    caps = r.json()["result"]["capabilities"]
    assert "tools" in caps and "resources" in caps
    assert "2026-07-28" in r.json()["result"]["supportedVersions"]


def test_results_carry_server_info_stamp(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = mcp_post(client, "tools/list")
    assert r.json()["result"]["_meta"]["io.modelcontextprotocol/serverInfo"] == SERVER_INFO


def test_capabilities_are_taken_from_each_request(fresh_app, mcp_post):
    client, _, _ = fresh_app(registrars=(register_probe,))
    form = {"elicitation": {"form": {}}}
    seen = []
    for caps in (form, {}, {"elicitation": {}}, form):
        r = mcp_post(client, "tools/call", {"name": "sonda_capacidades", "arguments": {}}, caps=caps)
        assert r.status_code == 200, r.text
        seen.append(json.loads(r.json()["result"]["content"][0]["text"])["form"])
    assert seen == [True, False, False, True]


def test_tools_list_reflects_registrars(fresh_app, mcp_post):
    client, _, _ = fresh_app(registrars=(register_dummy,))
    tools = mcp_post(client, "tools/list").json()["result"]["tools"]
    assert [t["name"] for t in tools] == ["ferramenta_falsa"]
    assert tools[0]["inputSchema"]["type"] == "object"


def test_every_request_produces_one_log_line_in_process(fresh_app, mcp_post):
    client, log_lines, _ = fresh_app()
    tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    mcp_post(client, "tools/list", id=1, traceparent=tp)
    mcp_post(client, "tools/list", id=2, drop_meta=(PV_KEY,))
    mcp_post(client, "tools/list", id=3, headers={"Mcp_Method": "tools/call"})
    client.post("/mcp", content=b"{nope", headers={"Content-Type": "application/json"})
    assert log_lines() == [
        f"mcp method=tools/list id=1 name=- traceparent={tp}",
        "mcp method=tools/list id=2 name=- traceparent=-",
        "mcp method=tools/list id=3 name=- traceparent=-",
        "mcp method=- id=- name=- traceparent=-",
    ]
