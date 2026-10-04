import json
import re
import secrets
import urllib.error
import urllib.request

import pytest

from servidor_mcp import mensagens


def test_startup_without_secret_exits_1(start_server):
    server = start_server(env={"REQUEST_STATE_SECRET": None}, wait_banner=False)
    assert server.wait_exit() == 1
    server.stop()
    assert server.lines == [mensagens.SEGREDO_INVALIDO]


@pytest.mark.parametrize("segredo", ["a" * 63, "z" * 64])
def test_startup_with_short_or_non_hex_secret_exits_1(start_server, segredo):
    server = start_server(env={"REQUEST_STATE_SECRET": segredo}, wait_banner=False)
    assert server.wait_exit() == 1
    server.stop()
    assert server.lines == [mensagens.SEGREDO_INVALIDO]
    assert not any("ouvindo em" in line for line in server.lines)


def test_startup_with_valid_secret_prints_banner(start_server):
    server = start_server(env={"REQUEST_STATE_SECRET": secrets.token_hex(32)})
    assert any("ouvindo em" in line for line in server.lines)


def h(hora, dia="2026-11-03"):
    return f"{dia}T{hora}:00-03:00"


ARGS = {"sala": "sala-garagem", "inicio": h("14:00"), "fim": h("15:00"), "responsavel": "Marty"}
CHAVE = "reservar_sala:escolha_de_sala"


def rpc(port, params, id_):
    body = {
        "jsonrpc": "2.0",
        "id": id_,
        "method": "tools/call",
        "params": {
            **params,
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
            },
        },
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/call",
            "Mcp-Name": params["name"],
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read())


def primeira_rodada(server):
    corpo = rpc(server.port, {"name": "reservar_sala", "arguments": ARGS}, 1)
    assert corpo["result"]["resultType"] == "input_required"
    return corpo["result"]["requestState"]


def retry(server, estado, id_=2):
    params = {
        "name": "reservar_sala",
        "arguments": ARGS,
        "inputResponses": {CHAVE: {"action": "accept", "content": {"sala": "sala-fusca"}}},
        "requestState": estado,
    }
    return rpc(server.port, params, id_)


def test_retry_after_restart_with_same_secret(start_server):
    segredo = secrets.token_hex(32)
    primeiro = start_server(env={"REQUEST_STATE_SECRET": segredo})
    estado = primeira_rodada(primeiro)
    primeiro.stop()

    segundo = start_server(env={"REQUEST_STATE_SECRET": segredo})
    resultado = retry(segundo, estado)["result"]
    assert resultado["resultType"] == "complete"
    assert resultado["structuredContent"]["reserva"] == "res-0003"
    assert resultado["structuredContent"]["sala"] == "sala-fusca"


def test_retry_after_restart_with_new_secret_rejected(start_server):
    primeiro = start_server(env={"REQUEST_STATE_SECRET": secrets.token_hex(32)})
    estado = primeira_rodada(primeiro)
    primeiro.stop()

    segundo = start_server(env={"REQUEST_STATE_SECRET": secrets.token_hex(32)})
    assert retry(segundo, estado)["error"]["code"] == -32602


def test_rejected_retry_is_logged_with_its_id(start_server):
    server = start_server()
    estado = primeira_rodada(server)
    assert retry(server, estado[:-6] + "AAAAAA", id_="deadbeef0001")["error"]["code"] == -32602
    server.wait_for_log_count(2)
    assert any(
        ln.startswith("mcp method=tools/call id=deadbeef0001 name=reservar_sala") for ln in server.lines
    )
    assert any("requestState rejected" in ln for ln in server.lines)


_LITERAL_ATRIBUIDO = re.compile(r"REQUEST_STATE_SECRET\s*=\s*['\"][0-9a-fA-F]{32,}")
_LITERAL_HEX = re.compile(r"['\"][0-9a-fA-F]{64,}['\"]")


def test_source_tree_has_no_hardcoded_secret(repo_root):
    arquivos = []
    for pasta in ("servidor-mcp/src", "servidor-mcp/tests", "agente/src"):
        arquivos += [p for p in (repo_root / pasta).rglob("*") if p.is_file() and p.suffix in {".py", ".toml", ".md", ".json"}]
    arquivos += [p for p in repo_root.iterdir() if p.is_file() and p.suffix in {".md", ".toml", ".json", ".py"}]
    assert arquivos
    achados = []
    for arquivo in arquivos:
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        if _LITERAL_ATRIBUIDO.search(texto) or _LITERAL_HEX.search(texto):
            achados.append(str(arquivo))
    assert achados == []
