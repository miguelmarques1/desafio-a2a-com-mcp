import json
import urllib.error
import urllib.request

from conftest import build_envelope, build_headers

BANNER = ("central-de-salas ouvindo", "salas carregadas", "reservas iniciais", "politica de uso")


def post(port, body):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp", data=json.dumps(body).encode(), headers=build_headers(body), method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def test_real_process_serves_catalog_and_policy(start_server, repo_root):
    server = start_server()
    _, listed = post(server.port, build_envelope("tools/list", id=1))
    entry = next(t for t in listed["result"]["tools"] if t["name"] == "listar_salas")
    assert entry["inputSchema"]["type"] == "object"

    _, called = post(server.port, build_envelope("tools/call", {"name": "listar_salas", "arguments": {}}, id=2))
    result = called["result"]
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]

    _, read = post(server.port, build_envelope("resources/read", {"uri": "politica://uso"}, id=3))
    text = read["result"]["contents"][0]["text"]
    assert "2026-11-01" in text
    assert text.encode("utf-8") == (repo_root / "dados" / "politica-de-uso.md").read_bytes()

    status, unknown = post(server.port, build_envelope("resources/read", {"uri": "politica://inexistente"}, id=4))
    assert status == 400 and unknown["error"]["code"] == -32602

    server.wait_for_log_count(4)
    lines = list(server.lines)
    mcp = [ln for ln in lines if ln.startswith("mcp ")]
    assert any("name=listar_salas" in ln for ln in mcp)
    assert any("name=politica://uso" in ln for ln in mcp)
    assert any("name=politica://inexistente" in ln for ln in mcp)
    assert [ln for ln in lines if not ln.startswith("mcp ") and not ln.startswith(BANNER)] == []
