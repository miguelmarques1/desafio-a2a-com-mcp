"""F08 acceptance and cross-feature criteria against real agent and MCP server processes."""

import asyncio
import json
import re
import urllib.request

import pytest

from agente.mcp_host import CompleteSuccess, McpClient, TraceContext

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
TP = f"00-{TRACE}-00f067aa0ba902b7-01"
INICIO = "2026-11-03T09:00:00-03:00"
FIM = "2026-11-03T10:00:00-03:00"
TEXT = f"reservar sala=sala-porao inicio={INICIO} fim={FIM} responsavel=Doc"
USAGE = "Pedido invalido: use reservar sala=<id> inicio=<iso8601> fim=<iso8601> responsavel=<nome>"


def rpc(agent, method, params, rpc_id=1, traceparent=None):
    body = {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params}
    headers = {"Content-Type": "application/json"}
    if traceparent:
        headers["traceparent"] = traceparent
    req = urllib.request.Request(
        f"http://127.0.0.1:{agent.port}/a2a", json.dumps(body).encode(), headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())["result"]["task"]


def send(agent, text=TEXT, **kwargs):
    message = {"messageId": "msg-6ae2ad6802e5", "role": "ROLE_USER", "parts": [{"text": text}]}
    return rpc(agent, "SendMessage", {"message": message}, **kwargs)


def status_text(task):
    return task["status"]["message"]["parts"][0]["text"]


def mcp_rows(mcp):
    return [line for line in list(mcp.lines) if line.startswith("mcp ")]


@pytest.fixture
def stack(start_mcp_server, start_agent):
    mcp = start_mcp_server()
    agent = start_agent(env={"MCP_URL": f"http://localhost:{mcp.port}/mcp"})
    return mcp, agent


def test_free_room_completes_on_fresh_processes(stack):
    _, agent = stack
    assert send(agent)["status"]["state"] == "TASK_STATE_COMPLETED"


def test_artifact_named_reserva_with_sala_and_politica(stack, repo_root):
    _, agent = stack
    task = send(agent)
    assert [a["name"] for a in task["artifacts"]] == ["reserva"]
    document = json.loads(task["artifacts"][0]["parts"][0]["text"])
    version = (repo_root / "dados" / "politica-de-uso.md").read_text(encoding="utf-8").splitlines()[0]
    assert document["sala"] == "sala-porao"
    assert document["politica"] == version.removeprefix("versao:").strip() == "2026-11-01"


def test_completed_status_message(stack):
    _, agent = stack
    text = status_text(send(agent))
    assert re.fullmatch(r"Reserva res-\d{4} confirmada na sala-porao\.", text)
    assert text == "Reserva res-0003 confirmada na sala-porao."


def test_unknown_room_fails_with_tool_text_in_status_and_history(stack):
    _, agent = stack
    task = send(agent, TEXT.replace("sala-porao", "sala-delorean"))
    assert task["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(task) == "Sala inexistente: sala-delorean"
    agent_messages = [m["parts"][0]["text"] for m in task["history"] if m["role"] == "ROLE_AGENT"]
    assert "Sala inexistente: sala-delorean" in agent_messages
    assert task["artifacts"] == []


def test_malformed_request_fails_with_zero_mcp_lines(stack):
    mcp, agent = stack
    before = len(mcp_rows(mcp))
    task = send(agent, "reservar sala=sala-porao")
    assert task["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(task) == USAGE
    assert len(mcp_rows(mcp)) == before


def test_artifact_fields_equal_reservar_sala_structured_content(stack):
    mcp, agent = stack
    task = send(agent)
    document = json.loads(task["artifacts"][0]["parts"][0]["text"])
    assert (document["reserva"], document["sala"], document["inicio"], document["fim"], document["responsavel"]) == (
        "res-0003",
        "sala-porao",
        INICIO,
        FIM,
        "Doc",
    )

    async def query():
        client = McpClient(f"http://localhost:{mcp.port}/mcp")
        try:
            args = {"sala": "sala-porao", "inicio": INICIO, "fim": FIM}
            return await client.call_tool(TraceContext.for_task(None), "consultar_disponibilidade", args)
        finally:
            await client.aclose()

    outcome = asyncio.run(query())
    assert isinstance(outcome, CompleteSuccess)
    conflict = outcome.structured["conflitos"][0]
    for key in ("reserva", "inicio", "fim", "responsavel"):
        expected = conflict["id" if key == "reserva" else key]
        assert document[key] == expected


def test_task_retrievable_by_get_task(stack):
    _, agent = stack
    sent = send(agent)
    got = rpc(agent, "GetTask", {"id": sent["id"]}, rpc_id=2)
    assert (got["id"], got["contextId"], got["status"]["state"]) == (
        sent["id"],
        sent["contextId"],
        sent["status"]["state"],
    )


def test_trace_id_reaches_every_mcp_request_of_the_task(stack):
    mcp, agent = stack
    before = len(mcp_rows(mcp))
    assert send(agent, traceparent=TP)["status"]["state"] == "TASK_STATE_COMPLETED"
    mcp.wait_for_count("mcp ", before + 3)
    lines = mcp_rows(mcp)[before:]
    assert [re.search(r"method=(\S+)", line).group(1) for line in lines] == [
        "tools/list",
        "resources/read",
        "tools/call",
    ]
    assert all(TRACE in line for line in lines)


def test_mcp_down_fails_task_with_unavailable_message(stack):
    mcp, agent = stack
    mcp.stop()
    task = send(agent)
    assert task["status"]["state"] == "TASK_STATE_FAILED"
    assert status_text(task) == "Servidor MCP indisponivel"
