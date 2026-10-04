"""A2A server contracts exercised by the skill and the bridge, against both real processes."""

import json
import urllib.request

import pytest

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
TRACEPARENT = f"00-{TRACE_ID}-00f067aa0ba902b7-01"


def rpc(port, method, params, rpc_id=1, traceparent=None):
    body = {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params}
    headers = {"Content-Type": "application/json"}
    if traceparent:
        headers["traceparent"] = traceparent
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/a2a", data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def message(text, task_id=None, mid="msg-6ae2ad6802e5"):
    msg = {"messageId": mid, "role": "ROLE_USER", "parts": [{"text": text}]}
    if task_id:
        msg["taskId"] = task_id
    return {"message": msg}


@pytest.fixture
def both(start_mcp_server, start_agent):
    mcp = start_mcp_server()
    agent = start_agent(env={"MCP_URL": f"http://127.0.0.1:{mcp.port}/mcp"})
    return mcp, agent


def test_tasks_created_by_skill_are_retrievable_by_get_task(both):
    _, agent = both
    text = (
        "reservar sala=sala-porao inicio=2026-11-03T09:00:00-03:00 "
        "fim=2026-11-03T10:00:00-03:00 responsavel=Doc"
    )
    sent = rpc(agent.port, "SendMessage", message(text))["result"]["task"]
    assert sent["status"]["state"] == "TASK_STATE_COMPLETED"
    got = rpc(agent.port, "GetTask", {"id": sent["id"]}, rpc_id=2)["result"]["task"]
    assert (got["id"], got["contextId"], got["status"]["state"]) == (
        sent["id"],
        sent["contextId"],
        sent["status"]["state"],
    )


def test_traceparent_trace_id_reaches_every_mcp_request_of_the_task(both):
    mcp, agent = both
    before = len(mcp.lines)
    text = (
        "reservar sala=sala-garagem inicio=2026-11-03T14:00:00-03:00 "
        "fim=2026-11-03T15:00:00-03:00 responsavel=Marty"
    )
    paused = rpc(agent.port, "SendMessage", message(text), traceparent=TRACEPARENT)
    task_id = paused["result"]["task"]["id"]
    assert paused["result"]["task"]["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    done = rpc(
        agent.port,
        "SendMessage",
        message("escolha=sala-fusca", task_id, "msg-441d0aa3db41"),
        rpc_id=2,
        traceparent=TRACEPARENT,
    )
    assert done["result"]["task"]["status"]["state"] == "TASK_STATE_COMPLETED"
    mcp.wait_for_count("mcp ", 2)
    lines = [ln for ln in mcp.lines[before:] if ln.startswith("mcp ")]
    assert lines and all(TRACE_ID in ln for ln in lines)


def test_continuation_updates_same_task_history(both):
    _, agent = both
    text = (
        "reservar sala=sala-garagem inicio=2026-11-03T14:00:00-03:00 "
        "fim=2026-11-03T15:00:00-03:00 responsavel=Marty"
    )
    paused = rpc(agent.port, "SendMessage", message(text))["result"]["task"]
    after = rpc(
        agent.port,
        "SendMessage",
        message("escolha=sala-fusca", paused["id"], "msg-441d0aa3db41"),
        rpc_id=2,
    )["result"]["task"]
    assert (after["id"], after["contextId"]) == (paused["id"], paused["contextId"])
    added = after["history"][len(paused["history"]) :]
    assert [m["role"] for m in added] == ["ROLE_USER", "ROLE_AGENT"]
