import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

TP = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def http(port, path="/.well-known/agent-card.json", body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers=headers or {},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read().decode()


def rpc(port, method, params, rpc_id=1):
    body = {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params}
    headers = {"Content-Type": "application/json", "traceparent": TP}
    status, text = http(port, "/a2a", body, headers)
    return status, json.loads(text)


def send_params(text="reservar sala=x"):
    return {"message": {"messageId": "msg-6ae2ad6802e5", "role": "ROLE_USER", "parts": [{"text": text}]}}


def a2a_lines(agent):
    return [line for line in agent.lines if line.startswith("a2a ")]


def test_starts_on_default_port_and_serves_card(start_agent):
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 7300)) == 0:
            pytest.skip("port 7300 is busy")
    agent = start_agent(port=7300, env={"AGENT_PORT": None})
    assert agent.wait_for_line("ouvindo em http://127.0.0.1:7300")
    card = json.loads(http(7300)[1])
    assert card["supportedInterfaces"][0]["url"] == "http://localhost:7300/a2a"


def test_banner_lines_and_nothing_on_stdout(start_agent):
    agent = start_agent()
    assert agent.wait_for_line("endpoint A2A anunciado")
    assert agent.lines[:3] == [
        f"agente central-de-salas ouvindo em http://127.0.0.1:{agent.port}",
        f"agent card: http://127.0.0.1:{agent.port}/.well-known/agent-card.json",
        f"endpoint A2A anunciado: http://localhost:{agent.port}/a2a",
    ]
    assert agent.stop() is not None
    assert agent.proc.stdout.read() == ""


def test_respects_agent_port_host_and_public_url(start_agent, free_port):
    port = free_port()
    agent = start_agent(
        port=port,
        env={"AGENT_HOST": "127.0.0.1", "AGENT_PUBLIC_URL": "http://agente.example:9000"},
    )
    assert agent.wait_for_line("ouvindo em")
    card = json.loads(http(port)[1])
    assert card["supportedInterfaces"][0]["url"] == "http://agente.example:9000/a2a"
    assert agent.wait_for_line("endpoint A2A anunciado: http://agente.example:9000/a2a")


def test_validator_style_requests_over_http(start_agent):
    agent = start_agent()
    status, text = http(agent.port)
    card = json.loads(text)
    assert status == 200
    interface = card["supportedInterfaces"][0]
    assert interface["url"].endswith("/a2a")
    assert (interface["protocolBinding"], interface["protocolVersion"]) == ("JSONRPC", "1.0")
    assert any(s["id"] == "reservar-sala" for s in card["skills"])
    status, body = rpc(agent.port, "SendMessage", send_params())
    task = body["result"]["task"]
    assert status == 200 and task["status"]["state"] == "TASK_STATE_FAILED"
    agent.wait_for_count("a2a ", 1)
    assert a2a_lines(agent) == [
        f"a2a method=SendMessage id=1 task={task['id']} state=TASK_STATE_FAILED"
    ]


def test_port_in_use_exits_1(start_agent, free_port):
    port = free_port()
    with socket.socket() as holder:
        if sys.platform == "win32":
            holder.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        holder.bind(("127.0.0.1", port))
        holder.listen(1)
        agent = start_agent(port=port, wait_banner=False)
        assert agent.wait_exit() == 1
        agent.wait_for_line("em uso")
        assert agent.lines == [
            f"Porta {port} em uso: defina AGENT_PORT ou encerre o processo anterior"
        ]


def test_invalid_agent_port_exits_1(start_agent):
    agent = start_agent(env={"AGENT_PORT": "abc"}, wait_banner=False)
    assert agent.wait_exit() == 1
    agent.wait_for_line("invalida")
    assert agent.lines == ["AGENT_PORT invalida: abc"]


def test_invalid_public_url_exits_1(start_agent):
    agent = start_agent(env={"AGENT_PUBLIC_URL": "localhost:7300"}, wait_banner=False)
    assert agent.wait_exit() == 1
    agent.wait_for_line("invalida")
    assert agent.lines == ["AGENT_PUBLIC_URL invalida: localhost:7300"]


def test_python_m_agente_from_repo_root_imports_installed_package(start_agent, repo_root):
    probe = subprocess.run(
        [sys.executable, "-c", "import agente; print(agente.__file__)"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    path = os.path.normpath(probe.stdout.strip())
    assert path.endswith(os.path.join("agente", "src", "agente", "__init__.py"))
    agent = start_agent(cwd=repo_root)
    assert agent.wait_for_line("ouvindo em")


def test_starts_from_unrelated_working_directory(start_agent, tmp_path):
    agent = start_agent(cwd=tmp_path)
    assert agent.wait_for_line("ouvindo em")
    assert http(agent.port)[0] == 200


def test_tasks_do_not_survive_restart(start_agent):
    agent = start_agent()
    task_id = rpc(agent.port, "SendMessage", send_params())[1]["result"]["task"]["id"]
    port = agent.port
    agent.stop()
    again = start_agent(port=port)
    assert again.wait_for_line("ouvindo em")
    body = rpc(port, "GetTask", {"id": task_id})[1]
    assert body["error"]["code"] == -32001


@pytest.mark.skipif(sys.platform == "win32", reason="Process.terminate() is a hard kill on Windows")
def test_sigterm_shuts_down_with_exit_code_0(start_agent):
    agent = start_agent()
    assert agent.wait_for_line("ouvindo em")
    assert agent.stop() == 0


def test_request_lines_match_contract(start_agent):
    agent = start_agent()
    rpc(agent.port, "CancelTask", {}, rpc_id=7)
    agent.wait_for_count("a2a ", 1)
    assert a2a_lines(agent) == ["a2a method=CancelTask id=7 task=- state=-"]
    assert re.fullmatch(r"a2a method=\S+ id=\S+ task=\S+ state=\S+", a2a_lines(agent)[0])


def test_invalid_mcp_url_exits_1(start_agent):
    agent = start_agent(env={"MCP_URL": "localhost:7301"}, wait_banner=False)
    assert agent.wait_exit() == 1
    assert agent.wait_for_line("MCP_URL invalida: localhost:7301")


def test_agent_starts_without_mcp_server(start_agent, free_port):
    agent = start_agent(env={"MCP_URL": f"http://127.0.0.1:{free_port()}/mcp"})
    assert agent.wait_for_line("endpoint A2A anunciado")
    status, text = http(agent.port)
    assert status == 200 and json.loads(text)["supportedInterfaces"]
    assert all(line.startswith(("agente ", "agent card", "endpoint A2A")) for line in agent.lines)
