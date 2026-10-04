"""Task-level F06 criteria. Each test is skipped while the F07 stub handlers are still in place
(F08 for new Tasks, F09 for continuations) or while the MCP server lacks reservar_sala."""

import json
import urllib.request

import pytest

from agente.mensagens import STUB_SKILL_NAO_IMPLEMENTADA

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
TP = f"00-{TRACE}-00f067aa0ba902b7-01"
COMMAND = "reservar sala=sala-aquario inicio=2026-11-03T10:00:00-03:00 fim=2026-11-03T11:00:00-03:00 responsavel=Doc"


def send(agent, text=COMMAND, *, traceparent=None, task_id=None, n=1, timeout=30):
    message = {"messageId": f"msg-{n:012d}", "role": "ROLE_USER", "parts": [{"text": text}]}
    if task_id:
        message["taskId"] = task_id
    body = {"jsonrpc": "2.0", "id": n, "method": "SendMessage", "params": {"message": message}}
    headers = {"Content-Type": "application/json"}
    if traceparent:
        headers["traceparent"] = traceparent
    req = urllib.request.Request(
        f"http://127.0.0.1:{agent.port}/a2a", json.dumps(body).encode(), headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["result"]["task"]


def status_text(task):
    return " ".join(p.get("text", "") for p in task["status"].get("message", {}).get("parts", []))


@pytest.fixture
def stack(start_mcp_server, start_agent):
    mcp = start_mcp_server()
    agent = start_agent(env={"MCP_URL": f"http://localhost:{mcp.port}/mcp"})
    probe = send(agent, n=100)
    if STUB_SKILL_NAO_IMPLEMENTADA in status_text(probe):
        pytest.skip("consumer feature not registered yet (F08)")
    if "reservar_sala nao encontrada" in status_text(probe):
        pytest.skip("MCP server lacks reservar_sala")
    mcp.lines.clear()
    return mcp, agent


def rows(mcp):
    out = []
    for line in list(mcp.lines):
        if line.startswith("mcp "):
            f = dict(p.split("=", 1) for p in line.split()[1:] if "=" in p)
            out.append((f["method"], int(f["id"]), f["name"], f["traceparent"]))
    return out


def by_trace(mcp):
    groups: dict[str, list] = {}
    for row in rows(mcp):
        groups.setdefault(row[3].split("-")[1], []).append(row)
    return groups


def run_two_tasks(mcp, agent):
    send(agent, n=1)
    send(agent, n=2)
    mcp.wait_for_count("mcp ", 6)


def test_tools_list_precedes_first_tool_call_per_task(stack):
    mcp, agent = stack
    run_two_tasks(mcp, agent)
    groups = by_trace(mcp)
    assert len(groups) == 2
    for group in groups.values():
        methods = [r[0] for r in group]
        assert methods.index("tools/list") < methods.index("tools/call")


def test_policy_read_precedes_first_tool_call_per_task(stack):
    mcp, agent = stack
    run_two_tasks(mcp, agent)
    for group in by_trace(mcp).values():
        methods = [(r[0], r[2]) for r in group]
        assert methods.index(("resources/read", "politica://uso")) < [m[0] for m in methods].index("tools/call")


def test_every_agent_request_declares_meta(stack):
    mcp, agent = stack
    run_two_tasks(mcp, agent)
    assert all(r[3] != "-" for r in rows(mcp))


def test_no_request_rejected_for_header_mismatch(stack):
    mcp, agent = stack
    tasks = [send(agent, n=1), send(agent, n=2)]
    assert all("-32020" not in status_text(t) for t in tasks)


def test_traceparent_trace_id_propagated_with_new_span(stack):
    mcp, agent = stack
    send(agent, traceparent=TP)
    mcp.wait_for_count("mcp ", 3)
    lines = rows(mcp)
    assert lines and all(r[3].split("-")[1] == TRACE and r[3].split("-")[2] != "00f067aa0ba902b7" for r in lines)


def test_generated_trace_id_shared_by_task_requests(stack):
    mcp, agent = stack
    run_two_tasks(mcp, agent)
    groups = by_trace(mcp)
    assert len(groups) == 2 and all(len(g) >= 3 for g in groups.values())


def test_no_two_agent_requests_share_an_id(stack):
    mcp, agent = stack
    for n in range(1, 4):
        send(agent, n=n)
    mcp.wait_for_count("mcp ", 9)
    ids = [r[1] for r in rows(mcp)]
    assert len(ids) == len(set(ids))


def test_mcp_down_fails_task_within_10_seconds(stack):
    import time

    mcp, agent = stack
    mcp.stop()
    started = time.time()
    task = send(agent, n=5, timeout=15)
    assert task["status"]["state"] == "TASK_STATE_FAILED"
    assert "Servidor MCP indisponivel" in status_text(task)
    assert time.time() - started < 10


def test_artifact_politica_equals_extracted_version(stack):
    mcp, agent = stack
    task = send(agent)
    art = json.loads(task["artifacts"][0]["parts"][0]["text"])
    assert art["politica"] == "2026-11-01"


def test_is_error_text_reaches_task_verbatim(stack):
    mcp, agent = stack
    task = send(agent, COMMAND.replace("sala-aquario", "sala-delorean"))
    assert "Sala inexistente: sala-delorean" in status_text(task)


def test_agent_tools_list_lists_server_tools(stack):
    mcp, agent = stack
    assert send(agent)["status"]["state"] == "TASK_STATE_COMPLETED"
    assert any(r[0] == "tools/list" for r in rows(mcp))


def test_retry_uses_new_id_and_verbatim_state(stack):
    mcp, agent = stack
    conflict = COMMAND.replace("sala-aquario", "sala-garagem").replace("10:00", "14:00").replace("11:00", "15:00")
    task = send(agent, conflict)
    if task["status"]["state"] != "TASK_STATE_INPUT_REQUIRED":
        pytest.skip("consumer feature not registered yet (F09)")
    done = send(agent, "escolha=sala-fusca", task_id=task["id"], n=2)
    assert done["status"]["state"] == "TASK_STATE_COMPLETED"
    calls = [r for r in rows(mcp) if r[0] == "tools/call" and r[2] == "reservar_sala"]
    assert len(calls) == 2 and calls[0][1] != calls[1][1]

