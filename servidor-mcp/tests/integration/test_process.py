import hashlib
import json
import os
import re
import signal
import socket
import stat
import sys
import urllib.error
import urllib.request

import pytest

from conftest import build_envelope, build_headers

TP = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


def post(port, body=None, *, raw=None, headers=None):
    if raw is None:
        raw = json.dumps(body).encode()
        headers = headers if headers is not None else build_headers(body)
    req = urllib.request.Request(f"http://127.0.0.1:{port}/mcp", data=raw, headers=headers or {}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.headers.get("content-type", ""), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", ""), e.read().decode()


def mcp_lines(server):
    return [ln for ln in server.lines if ln.startswith("mcp ")]


def test_starts_on_default_port_and_answers_tools_list(start_server):
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 7301)) == 0:
            pytest.skip("port 7301 is busy")
    server = start_server(port=7301, env={"MCP_PORT": None})
    assert server.wait_for_line("central-de-salas ouvindo em http://127.0.0.1:7301/mcp")
    status, ctype, text = post(7301, build_envelope("tools/list"))
    assert status == 200 and json.loads(text)["result"]["resultType"] == "complete"


def test_startup_banner_reports_counts_and_policy_version(start_server):
    server = start_server()
    assert server.wait_for_line("politica de uso")
    assert server.lines[:4] == [
        f"central-de-salas ouvindo em http://127.0.0.1:{server.port}/mcp",
        "salas carregadas: 5",
        "reservas iniciais: 2",
        "politica de uso: versao 2026-11-01",
    ]
    assert server.proc.stdout.readable()
    assert server.stop() is not None
    assert server.proc.stdout.read() == ""


def test_respects_mcp_port_and_mcp_host(start_server, free_port):
    port = free_port()
    server = start_server(port=port, env={"MCP_HOST": "127.0.0.1"})
    assert server.lines[0].endswith(f"127.0.0.1:{port}/mcp")
    assert post(port, build_envelope("tools/list"))[0] == 200


def test_every_request_logs_one_stderr_line(start_server):
    server = start_server()
    port = server.port
    post(port, build_envelope("tools/list", id=1, traceparent=TP))
    post(port, build_envelope("tools/list", id=2))
    post(port, build_envelope("tools/list", id=3,
                              drop_meta=("io.modelcontextprotocol/protocolVersion",)))
    body = build_envelope("tools/list", id=4)
    post(port, body, headers=build_headers(body, Mcp_Method="tools/call"))
    post(port, raw=b'{"jsonrpc": "2.0", "id": 9, "method": ',
         headers={"Content-Type": "application/json"})
    server.wait_for_log_count(5)
    assert mcp_lines(server) == [
        f"mcp method=tools/list id=1 name=- traceparent={TP}",
        "mcp method=tools/list id=2 name=- traceparent=-",
        "mcp method=tools/list id=3 name=- traceparent=-",
        "mcp method=tools/list id=4 name=- traceparent=-",
        "mcp method=- id=- name=- traceparent=-",
    ]


def test_traceparent_trace_id_is_greppable(start_server):
    server = start_server()
    trace_id = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
    post(server.port, build_envelope("tools/list", id="x1", traceparent=f"00-{trace_id}-1122334455667788-01"))
    post(server.port, build_envelope("tools/list", id="x2"))
    server.wait_for_log_count(2)
    assert len([ln for ln in server.lines if trace_id in ln]) == 1


@pytest.mark.skipif(sys.platform == "win32" or IS_ROOT, reason="chmod 000 not effective here")
def test_unreadable_salas_json_exits_1(start_server, dados_tmp):
    alvo = dados_tmp / "salas.json"
    alvo.chmod(0)
    try:
        server = start_server(env={"MCP_DADOS_DIR": str(dados_tmp)}, wait_banner=False)
        assert server.wait_exit() == 1
    finally:
        alvo.chmod(stat.S_IRUSR | stat.S_IWUSR)
    server.stop()
    assert any(ln.startswith("Falha ao carregar dados/: salas.json") for ln in server.lines)
    assert not any("ouvindo em" in ln for ln in server.lines)


@pytest.mark.parametrize("arquivo", ["salas.json", "reservas.json", "politica-de-uso.md"])
def test_missing_data_file_exits_1(start_server, dados_tmp, arquivo):
    (dados_tmp / arquivo).unlink()
    server = start_server(env={"MCP_DADOS_DIR": str(dados_tmp)}, wait_banner=False)
    assert server.wait_exit() == 1
    server.stop()
    assert any(ln.startswith(f"Falha ao carregar dados/: {arquivo}") for ln in server.lines)
    assert not any("ouvindo em" in ln for ln in server.lines)


def test_policy_without_version_exits_1(start_server, dados_tmp):
    (dados_tmp / "politica-de-uso.md").write_text("sem versao\n", encoding="utf-8")
    server = start_server(env={"MCP_DADOS_DIR": str(dados_tmp)}, wait_banner=False)
    assert server.wait_exit() == 1
    server.stop()
    assert "Politica de uso sem versao declarada" in server.lines


def test_port_in_use_exits_1(start_server, free_port):
    from servidor_mcp.network import bind_listening_socket

    port = free_port()
    holder = bind_listening_socket("127.0.0.1", port)
    try:
        server = start_server(port=port, wait_banner=False)
        assert server.wait_exit() == 1
        server.stop()
    finally:
        holder.close()
    assert f"Porta {port} em uso: defina MCP_PORT ou encerre o processo anterior" in server.lines


def test_invalid_mcp_port_exits_1(start_server):
    server = start_server(env={"MCP_PORT": "abc"}, wait_banner=False)
    assert server.wait_exit() == 1
    server.stop()
    assert "MCP_PORT invalida: abc" in server.lines


def test_starts_from_unrelated_working_directory(start_server, tmp_path):
    server = start_server(cwd=tmp_path)
    assert "salas carregadas: 5" in server.lines


def test_dados_files_unchanged_after_session(start_server, repo_root):
    def digest():
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((repo_root / "dados").iterdir())
        }

    antes = digest()
    server = start_server()
    for i in range(3):
        post(server.port, build_envelope("tools/list", id=i))
    server.stop()
    assert digest() == antes


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM semantics are POSIX only")
def test_sigterm_shuts_down_with_exit_code_0(start_server):
    server = start_server()
    server.proc.send_signal(signal.SIGTERM)
    assert server.wait_exit() == 0
