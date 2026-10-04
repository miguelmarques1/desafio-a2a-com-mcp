"""F09 acceptance and cross-feature criteria against real agent and MCP server processes."""

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
TP = f"00-{TRACE}-00f067aa0ba902b7-01"
INICIO = "2026-11-03T14:00:00-03:00"
FIM = "2026-11-03T15:00:00-03:00"
TEXT = f"reservar sala=sala-garagem inicio={INICIO} fim={FIM} responsavel=Marty"
TEXT_FUSCA = (
    "reservar sala=sala-fusca inicio=2026-11-03T16:00:00-03:00 "
    "fim=2026-11-03T17:00:00-03:00 responsavel=Emmett"
)
LINE = "alternativas: sala-fusca, sala-mirante"
SECRET = "ab" * 32


def rpc(agent, method, params, rpc_id=1, traceparent=None, raw=False):
    body = {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params}
    headers = {"Content-Type": "application/json"}
    if traceparent:
        headers["traceparent"] = traceparent
    req = urllib.request.Request(
        f"http://127.0.0.1:{agent.port}/a2a", json.dumps(body).encode(), headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        text = response.read().decode("utf-8")
    return text if raw else json.loads(text)


def send(agent, text=TEXT, task_id=None, **kwargs):
    message = {"messageId": "msg-6ae2ad6802e5", "role": "ROLE_USER", "parts": [{"text": text}]}
    if task_id:
        message["taskId"] = task_id
    reply = rpc(agent, "SendMessage", {"message": message}, **kwargs)
    return reply["result"]["task"] if "result" in reply else reply


def status_text(task):
    return task["status"]["message"]["parts"][0]["text"]


def mcp_rows(mcp):
    return [line for line in list(mcp.lines) if line.startswith("mcp ")]


def call_rows(mcp):
    return [line for line in mcp_rows(mcp) if "method=tools/call" in line]


class Relay:
    """Recording HTTP forwarder between the agent and the real MCP server."""

    def __init__(self, target_port):
        self.exchanges: list[tuple[dict, dict]] = []
        relay = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}
                req = urllib.request.Request(
                    f"http://127.0.0.1:{target_port}{self.path}", body, headers, method="POST"
                )
                try:
                    with urllib.request.urlopen(req, timeout=30) as response:
                        status, ctype, data = response.status, response.headers.get("Content-Type"), response.read()
                except urllib.error.HTTPError as error:
                    status, ctype, data = error.code, error.headers.get("Content-Type"), error.read()
                relay.exchanges.append((json.loads(body), data.decode("utf-8", "replace")))
                self.send_response(status)
                if ctype:
                    self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def issued_states(self):
        states = []
        for _, response in self.exchanges:
            for chunk in response.splitlines():
                chunk = chunk.removeprefix("data:").strip()
                if chunk.startswith("{"):
                    result = json.loads(chunk).get("result") or {}
                    if result.get("requestState"):
                        states.append(result["requestState"])
        return states


@pytest.fixture
def stack(start_mcp_server, start_agent):
    mcp = start_mcp_server(secret=SECRET)
    agent = start_agent(env={"MCP_URL": f"http://localhost:{mcp.port}/mcp"})
    return mcp, agent


@pytest.fixture
def relayed(start_mcp_server, start_agent):
    mcp = start_mcp_server(secret=SECRET)
    relay = Relay(mcp.port)
    agent = start_agent(env={"MCP_URL": f"http://127.0.0.1:{relay.port}/mcp"})
    yield mcp, agent, relay
    relay.close()


def test_conflict_pauses_with_exact_alternatives(stack):
    _, agent = stack
    task = send(agent)
    assert task["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert status_text(task) == LINE


def test_invalid_choice_reprompts_without_mcp_traffic(stack):
    mcp, agent = stack
    task = send(agent)
    before = len(mcp_rows(mcp))
    again = send(agent, "escolha=sala-aquario", task_id=task["id"], rpc_id=2)
    assert again["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert status_text(again) == LINE
    assert len(mcp_rows(mcp)) == before


def test_valid_choice_completes_in_chosen_room(stack, repo_root):
    _, agent = stack
    task = send(agent)
    done = send(agent, "escolha=sala-fusca", task_id=task["id"], rpc_id=2)
    assert done["status"]["state"] == "TASK_STATE_COMPLETED"
    document = json.loads(done["artifacts"][0]["parts"][0]["text"])
    version = (repo_root / "dados" / "politica-de-uso.md").read_text(encoding="utf-8").splitlines()[0]
    assert document["sala"] == "sala-fusca"
    assert (document["inicio"], document["fim"], document["responsavel"]) == (INICIO, FIM, "Marty")
    assert document["politica"] == version.removeprefix("versao:").strip()
    assert (done["id"], done["contextId"]) == (task["id"], task["contextId"])
    assert [m["role"] for m in done["history"]][-2:] == ["ROLE_USER", "ROLE_AGENT"]


def test_initial_and_retry_tool_calls_have_different_ids(stack):
    mcp, agent = stack
    task = send(agent)
    send(agent, "escolha=sala-fusca", task_id=task["id"], rpc_id=2)
    mcp.wait_for_count("mcp ", 4)
    rows = [line for line in call_rows(mcp) if "name=reservar_sala" in line]
    ids = [dict(p.split("=", 1) for p in line.split()[1:] if "=" in p)["id"] for line in rows]
    assert len(ids) == 2 and ids[0] != ids[1]


def test_retry_reuses_key_and_state_verbatim(relayed):
    _, agent, relay = relayed
    task = send(agent)
    send(agent, "escolha=sala-fusca", task_id=task["id"], rpc_id=2)
    calls = [(req, res) for req, res in relay.exchanges if req.get("method") == "tools/call"]
    assert len(calls) == 2
    first_result = json.loads(calls[0][1].removeprefix("data:").strip().splitlines()[-1].removeprefix("data:").strip())["result"]
    key = next(iter(first_result["inputRequests"]))
    retry = calls[1][0]["params"]
    assert list(retry["inputResponses"]) == [key]
    assert retry["requestState"] == first_result["requestState"]


def test_recusar_cancels_without_reservation(stack):
    _, agent = stack
    task = send(agent)
    done = send(agent, "escolha=recusar", task_id=task["id"], rpc_id=2)
    assert done["status"]["state"] == "TASK_STATE_CANCELED"
    assert status_text(done) == "Reserva recusada: nenhuma alternativa escolhida."
    assert done["artifacts"] == []
    # nothing was booked: the next free reservation is still the first new id
    next_task = send(agent, TEXT.replace("sala-garagem", "sala-porao"), rpc_id=3)
    assert status_text(next_task) == "Reserva res-0003 confirmada na sala-porao."


def test_two_paused_tasks_complete_independently(stack):
    _, agent = stack
    a = send(agent, TEXT_FUSCA)
    b = send(agent, TEXT, rpc_id=2)
    assert a["status"]["state"] == b["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    done_a = send(agent, "escolha=sala-mirante", task_id=a["id"], rpc_id=3)
    done_b = send(agent, "escolha=sala-mirante", task_id=b["id"], rpc_id=4)
    docs = [json.loads(t["artifacts"][0]["parts"][0]["text"]) for t in (done_a, done_b)]
    assert done_a["status"]["state"] == done_b["status"]["state"] == "TASK_STATE_COMPLETED"
    assert docs[0]["reserva"] != docs[1]["reserva"]
    assert docs[0]["inicio"] != docs[1]["inicio"]


def test_no_a2a_body_contains_request_state_and_lines_are_identical(relayed):
    _, agent, relay = relayed
    bodies = []
    with urllib.request.urlopen(f"http://127.0.0.1:{agent.port}/.well-known/agent-card.json") as card:
        bodies.append(card.read().decode())
    first = rpc(agent, "SendMessage", {"message": {"messageId": "m1", "role": "ROLE_USER", "parts": [{"text": TEXT}]}}, raw=True)
    second = rpc(agent, "SendMessage", {"message": {"messageId": "m2", "role": "ROLE_USER", "parts": [{"text": TEXT}]}}, rpc_id=2, raw=True)
    task = json.loads(first)["result"]["task"]
    bodies += [first, second, rpc(agent, "GetTask", {"id": task["id"]}, rpc_id=3, raw=True)]
    bodies.append(rpc(agent, "SendMessage", {"message": {"messageId": "m3", "role": "ROLE_USER", "parts": [{"text": "escolha=sala-fusca"}], "taskId": task["id"]}}, rpc_id=4, raw=True))
    bodies.append(rpc(agent, "SendMessage", {"message": {"messageId": "m4", "role": "ROLE_USER", "parts": [{"text": "escolha=sala-fusca"}], "taskId": task["id"]}}, rpc_id=5, raw=True))
    states = relay.issued_states()
    assert states
    for state in states:
        for body in bodies:
            assert not any(state[i : i + 40] in body for i in range(0, len(state) - 39, 10))
    assert status_text(json.loads(first)["result"]["task"]) == status_text(json.loads(second)["result"]["task"]) == LINE


def test_invalid_state_fails_with_mcp_error(start_mcp_server, start_agent):
    mcp = start_mcp_server(secret=SECRET)
    agent = start_agent(env={"MCP_URL": f"http://localhost:{mcp.port}/mcp"})
    task = send(agent)
    mcp.stop()
    start_mcp_server(port=mcp.port, secret="cd" * 32)
    done = send(agent, "escolha=sala-fusca", task_id=task["id"], rpc_id=2)
    assert done["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(done).startswith("Erro do servidor MCP: -32602")


def test_retry_after_restart_with_same_secret_completes(start_mcp_server, start_agent):
    mcp = start_mcp_server(secret=SECRET)
    agent = start_agent(env={"MCP_URL": f"http://localhost:{mcp.port}/mcp"})
    task = send(agent)
    mcp.stop()
    start_mcp_server(port=mcp.port, secret=SECRET)
    done = send(agent, "escolha=sala-fusca", task_id=task["id"], rpc_id=2)
    assert done["status"]["state"] == "TASK_STATE_COMPLETED"


def test_mcp_down_during_retry_fails(stack):
    mcp, agent = stack
    task = send(agent)
    mcp.stop()
    done = send(agent, "escolha=sala-fusca", task_id=task["id"], rpc_id=2)
    assert done["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(done) == "Servidor MCP indisponivel"


def test_trace_id_reaches_retry(stack):
    mcp, agent = stack
    task = send(agent, traceparent=TP)
    send(agent, "escolha=sala-fusca", task_id=task["id"], rpc_id=2, traceparent=TP)
    mcp.wait_for_count("mcp ", 4)
    rows = mcp_rows(mcp)
    assert len(rows) == 4
    assert all(TRACE in row for row in rows)


def test_retry_without_header_keeps_task_trace(stack):
    mcp, agent = stack
    task = send(agent, traceparent=TP)
    send(agent, "escolha=sala-fusca", task_id=task["id"], rpc_id=2)
    mcp.wait_for_count("mcp ", 4)
    assert all(TRACE in row for row in mcp_rows(mcp))


def test_terminal_task_refuses_choice(stack):
    _, agent = stack
    task = send(agent)
    send(agent, "escolha=sala-fusca", task_id=task["id"], rpc_id=2)
    again = send(agent, "escolha=sala-mirante", task_id=task["id"], rpc_id=3)
    assert again["error"]["code"] == -32004
