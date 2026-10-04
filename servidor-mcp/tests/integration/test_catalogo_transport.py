import json

import pytest

from conftest import build_envelope, build_headers

SALAS_IDS = ["sala-aquario", "sala-porao", "sala-garagem", "sala-fusca", "sala-mirante"]


def tools(client, mcp_post):
    return mcp_post(client, "tools/list").json()["result"]["tools"]


def call(client, mcp_post, arguments=None, **options):
    params = {"name": "listar_salas"}
    if arguments is not None:
        params["arguments"] = arguments
    return mcp_post(client, "tools/call", params, **options)


def wire_tools(repo_root):
    wire = json.loads((repo_root / "exemplos" / "wire" / "01-tools-list.json").read_text(encoding="utf-8"))
    return wire["response"]["body"]["result"]["tools"]


def test_tools_list_includes_listar_salas_with_object_input_and_output_schema(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    entry = next(t for t in tools(client, mcp_post) if t["name"] == "listar_salas")
    assert entry["inputSchema"]["type"] == "object"
    assert "outputSchema" in entry


def test_listar_salas_definition_matches_wire_example(fresh_app, mcp_post, repo_root):
    client, _, _ = fresh_app()
    entry = next(t for t in tools(client, mcp_post) if t["name"] == "listar_salas")
    assert entry == wire_tools(repo_root)[0]


def test_listar_salas_is_first_in_tools_list(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    assert tools(client, mcp_post)[0]["name"] == "listar_salas"


def test_tools_list_order_matches_wire_example_for_registered_tools(fresh_app, mcp_post, repo_root):
    client, _, _ = fresh_app()
    registered = [t["name"] for t in tools(client, mcp_post)]
    wire = [t["name"] for t in wire_tools(repo_root)]
    assert [n for n in wire if n in registered] == [n for n in registered if n in wire]


def test_listar_salas_returns_five_rooms_in_file_order(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = call(client, mcp_post, {})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["resultType"] == "complete" and result["isError"] is False
    salas = result["structuredContent"]["salas"]
    assert [s["id"] for s in salas] == SALAS_IDS
    assert [s["capacidade"] for s in salas] == [4, 6, 12, 12, 20]


def test_listar_salas_text_block_equals_structured_content(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    result = call(client, mcp_post, {}).json()["result"]
    assert len(result["content"]) == 1 and result["content"][0]["type"] == "text"
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]


def test_listar_salas_structured_content_matches_output_schema(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    sc = call(client, mcp_post, {}).json()["result"]["structuredContent"]
    assert set(sc) == {"salas"}
    for sala in sc["salas"]:
        assert set(sala) == {"id", "nome", "capacidade", "recursos"}
        assert isinstance(sala["id"], str) and isinstance(sala["nome"], str)
        assert isinstance(sala["capacidade"], int) and not isinstance(sala["capacidade"], bool)
        assert isinstance(sala["recursos"], list) and all(isinstance(x, str) for x in sala["recursos"])


def test_listar_salas_ignores_extra_and_missing_arguments(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    base = call(client, mcp_post, {}).json()["result"]
    extra = call(client, mcp_post, {"x": 1}).json()["result"]
    missing = call(client, mcp_post).json()["result"]
    assert extra == base and missing == base


def test_listar_salas_needs_no_client_capability(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    r = call(client, mcp_post, {}, caps={})
    assert r.status_code == 200 and r.json()["result"]["isError"] is False


@pytest.mark.parametrize(
    "dropped",
    ["io.modelcontextprotocol/protocolVersion", "io.modelcontextprotocol/clientCapabilities"],
)
def test_listar_salas_without_envelope_keys_returns_32602_http_400(fresh_app, mcp_post, dropped):
    client, _, _ = fresh_app()
    r = call(client, mcp_post, {}, drop_meta=(dropped,))
    assert r.status_code == 400 and r.json()["error"]["code"] == -32602


def test_resources_list_contains_politica_uso(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    resources = mcp_post(client, "resources/list").json()["result"]["resources"]
    (entry,) = [r for r in resources if r["uri"] == "politica://uso"]
    assert entry["name"] == "politica-de-uso"
    assert entry["mimeType"] == "text/markdown"
    assert entry["description"]


def test_read_politica_returns_file_bytes_as_markdown(fresh_app, mcp_post, repo_root):
    client, _, _ = fresh_app()
    r = mcp_post(client, "resources/read", {"uri": "politica://uso"})
    assert r.status_code == 200
    (content,) = r.json()["result"]["contents"]
    assert content["uri"] == "politica://uso" and content["mimeType"] == "text/markdown"
    assert content["text"].encode("utf-8") == (repo_root / "dados" / "politica-de-uso.md").read_bytes()
    assert "2026-11-01" in content["text"]
    assert content["text"].splitlines()[0].rstrip("\r") == "versao: 2026-11-01"


@pytest.mark.parametrize("uri", ["politica://inexistente", "politica://uso/", "politica://USO", "arquivo://politica"])
def test_read_unknown_uri_returns_32602_never_empty_contents(fresh_app, mcp_post, uri):
    client, _, _ = fresh_app()
    r = mcp_post(client, "resources/read", {"uri": uri})
    body = r.json()
    assert r.status_code == 400 and "result" not in body
    assert body["error"]["code"] == -32602 and body["error"]["data"]["uri"] == uri


def test_unknown_uri_is_logged_with_method_id_and_uri(fresh_app, mcp_post):
    client, log_lines, _ = fresh_app()
    mcp_post(client, "resources/read", {"uri": "politica://inexistente"}, id=6)
    assert log_lines() == ["mcp method=resources/read id=6 name=politica://inexistente traceparent=-"]


def test_read_without_uri_returns_32602(fresh_app, mcp_post):
    client, _, _ = fresh_app()
    body = build_envelope("resources/read", {})
    headers = {**build_headers({**body, "method": "other"}), "Mcp-Method": "resources/read", "Mcp-Name": "politica://uso"}
    r = client.post("/mcp", json=body, headers=headers)
    assert r.status_code == 400 and r.json()["error"]["code"] == -32602
