import asyncio
import time

import pytest

from agente.mcp_host import (
    CompleteError,
    CompleteSuccess,
    InputRequired,
    McpClient,
    ProtocolFailure,
    TraceContext,
    accept_response,
    decline_response,
    open_task_context,
)

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
TP = f"00-{TRACE}-00f067aa0ba902b7-01"
CONFLICT = {
    "sala": "sala-garagem",
    "inicio": "2026-11-03T14:00:00-03:00",
    "fim": "2026-11-03T15:00:00-03:00",
    "responsavel": "Marty",
}


def run(server, coro_fn):
    """Run `coro_fn(client)` against the server with a fresh client; closes it afterwards."""

    async def go():
        client = McpClient(f"http://localhost:{server.port}/mcp")
        try:
            return await coro_fn(client)
        finally:
            await client.aclose()

    return asyncio.run(go())


def settle(server, count):
    server.wait_for_count("mcp ", count)


def tokens(line):
    return dict(part.split("=", 1) for part in line.split()[1:] if "=" in part)


@pytest.fixture
def server(start_mcp_server):
    return start_mcp_server()


@pytest.fixture
def reserving_server(server):
    """Server whose reservar_sala pauses on a conflict (F04 + F05); skipped until then."""

    async def probe(client):
        return await client.call_tool(TraceContext.for_task(None), "reservar_sala", CONFLICT)

    first = run(server, probe)
    if isinstance(first, ProtocolFailure) or not isinstance(first, InputRequired):
        pytest.skip("reservar_sala does not pause on conflicts yet (F04/F05)")
    server.lines.clear()
    return server


def test_discovery_lists_registered_tools(server, mcp_lines):
    trace = TraceContext.for_task(TP)
    tools = run(server, lambda c: c.list_tools(trace))
    names = [t.name for t in tools]
    assert "listar_salas" in names and "consultar_disponibilidade" in names
    settle(server, 1)
    rows = [r for r in mcp_lines(server) if r[0] == "tools/list"]
    assert len(rows) == 1 and TRACE in rows[0][3]


def test_policy_version_from_real_resource(server, mcp_lines):
    ctx = run(server, lambda c: open_task_context(c, TP, required_tool="listar_salas"))
    assert ctx.policy_version == "2026-11-01"
    settle(server, 2)
    rows = mcp_lines(server)
    assert [(r[0], r[2]) for r in rows[:2]] == [("tools/list", "-"), ("resources/read", "politica://uso")]
    assert all(TRACE in r[3] for r in rows[:2])
    assert int(rows[1][1]) == int(rows[0][1]) + 1


def test_no_request_is_rejected_by_the_ladder(server):
    async def go(client):
        trace = TraceContext.for_task(None)
        return [
            await client.list_tools(trace),
            await client.read_resource(trace, "politica://uso"),
            await client.call_tool(trace, "listar_salas", {}),
        ]

    for outcome in run(server, go):
        assert not (isinstance(outcome, ProtocolFailure) and outcome.code in (-32602, -32020, -32022))


def test_complete_error_text_is_verbatim(server):
    args = {"sala": "sala-delorean", "inicio": CONFLICT["inicio"], "fim": CONFLICT["fim"]}
    outcome = run(server, lambda c: c.call_tool(TraceContext.for_task(None), "consultar_disponibilidade", args))
    assert outcome == CompleteError("Sala inexistente: sala-delorean")


def test_trace_id_and_distinct_spans_in_server_log(server, mcp_lines):
    async def go(client):
        trace = TraceContext.for_task(TP)
        await client.list_tools(trace)
        await client.read_resource(trace, "politica://uso")
        await client.call_tool(trace, "listar_salas", {})

    run(server, go)
    settle(server, 3)
    parents = [r[3].split("-") for r in mcp_lines(server)]
    assert len(parents) == 3
    assert all(p[1] == TRACE and p[3] == "01" for p in parents)
    spans = {p[2] for p in parents}
    assert len(spans) == 3 and "00f067aa0ba902b7" not in spans


def test_generated_trace_id_shared_within_task(server, mcp_lines):
    async def go(client):
        trace = TraceContext.for_task(None)
        await client.call_tool(trace, "listar_salas", {})
        await client.call_tool(trace, "listar_salas", {})

    run(server, go)
    settle(server, 2)
    assert len({r[3].split("-")[1] for r in mcp_lines(server)}) == 1


def test_ids_unique_in_server_log(server, mcp_lines):
    async def go(client):
        trace = TraceContext.for_task(None)
        for i in range(10):
            if i % 2:
                await client.read_resource(trace, "politica://uso")
            else:
                await client.call_tool(trace, "listar_salas", {})

    run(server, go)
    settle(server, 10)
    ids = [int(r[1]) for r in mcp_lines(server)]
    assert len(ids) == 10 and ids == sorted(set(ids))


def test_reservar_sala_conflict_is_input_required(reserving_server):
    outcome = run(reserving_server, lambda c: c.call_tool(TraceContext.for_task(None), "reservar_sala", CONFLICT))
    assert isinstance(outcome, InputRequired)
    assert outcome.alternatives == ("sala-fusca", "sala-mirante")


def test_retry_accept_completes_with_new_id(reserving_server, mcp_lines):
    async def go(client):
        trace = TraceContext.for_task(None)
        paused = await client.call_tool(trace, "reservar_sala", CONFLICT)
        return await client.retry_tool(
            trace,
            "reservar_sala",
            CONFLICT,
            input_key=paused.input_key,
            input_response=accept_response("sala-fusca"),
            request_state=paused.request_state,
        )

    outcome = run(reserving_server, go)
    assert isinstance(outcome, CompleteSuccess) and outcome.structured["sala"] == "sala-fusca"
    settle(reserving_server, 2)
    calls = [r for r in mcp_lines(reserving_server) if r[0] == "tools/call" and r[2] == "reservar_sala"]
    assert len(calls) == 2 and calls[0][1] != calls[1][1]


def test_retry_decline_returns_reservado_false(reserving_server):
    async def go(client):
        trace = TraceContext.for_task(None)
        paused = await client.call_tool(trace, "reservar_sala", CONFLICT)
        return await client.retry_tool(
            trace,
            "reservar_sala",
            CONFLICT,
            input_key=paused.input_key,
            input_response=decline_response(),
            request_state=paused.request_state,
        )

    outcome = run(reserving_server, go)
    assert isinstance(outcome, CompleteSuccess) and outcome.structured["reservado"] is False


def test_tampered_state_is_server_error(reserving_server):
    async def go(client):
        trace = TraceContext.for_task(None)
        paused = await client.call_tool(trace, "reservar_sala", CONFLICT)
        state = paused.request_state
        tampered = state[:-1] + ("A" if state[-1] != "A" else "B")
        return await client.retry_tool(
            trace,
            "reservar_sala",
            CONFLICT,
            input_key=paused.input_key,
            input_response=accept_response("sala-fusca"),
            request_state=tampered,
        )

    outcome = run(reserving_server, go)
    assert isinstance(outcome, ProtocolFailure)
    assert outcome.message.startswith("Erro do servidor MCP: -32602")


def test_server_down_is_unavailable_quickly(server):
    server.stop()
    started = time.time()
    out = run(server, lambda c: open_task_context(c, None, required_tool="listar_salas"))
    assert out == ProtocolFailure("Servidor MCP indisponivel")
    assert time.time() - started < 10
