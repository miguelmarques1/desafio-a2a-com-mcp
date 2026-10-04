import asyncio
import time

import httpx
import pytest

from agente.mcp_host import (
    CompleteSuccess,
    InputRequired,
    McpClient,
    ProtocolFailure,
    TraceContext,
    accept_response,
)


def json_answer(body, status=200):
    return (status, "application/json", body)


TP = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
UNAVAILABLE = ProtocolFailure("Servidor MCP indisponivel")


def ok(result=None, rpc_id=None):
    return lambda request: None


def reply(request_id, result):
    return json_answer({"jsonrpc": "2.0", "id": request_id, "result": result})


def echo(result_for=None):
    """Answer every request with a success carrying the request's own id."""
    import json

    def answer(request):
        body = json.loads(request.content)
        result = {"resultType": "complete", "structuredContent": {"ok": True}, "tools": [], "contents": []}
        if result_for:
            result.update(result_for(body))
        return reply(body["id"], result)

    return answer


def test_ids_start_at_1_and_increase_across_methods(mock_mcp):
    m = mock_mcp(echo())
    trace = TraceContext.for_task(None)

    async def go():
        await m.client.list_tools(trace)
        await m.client.read_resource(trace, "politica://uso")
        await m.client.call_tool(trace, "t", {})
        await m.client.retry_tool(trace, "t", {}, input_key="k", input_response=accept_response("a"), request_state="s")

    asyncio.run(go())
    assert [b["id"] for b in m.bodies] == [1, 2, 3, 4]


def test_ids_never_repeat_under_concurrency(mock_mcp):
    m = mock_mcp(echo())
    trace = TraceContext.for_task(None)

    async def go():
        return await asyncio.gather(*(m.client.call_tool(trace, "t", {}) for _ in range(50)))

    outcomes = asyncio.run(go())
    assert all(isinstance(o, CompleteSuccess) for o in outcomes)
    assert len({b["id"] for b in m.bodies}) == 50


def test_failed_request_still_consumes_an_id(mock_mcp):
    first = httpx.ConnectError("refused")
    m = mock_mcp([first])

    async def go():
        trace = TraceContext.for_task(None)
        a = await m.client.call_tool(trace, "t", {})
        m._answers = echo()
        b = await m.client.call_tool(trace, "t", {})
        return a, b

    a, b = asyncio.run(go())
    assert a == UNAVAILABLE and isinstance(b, CompleteSuccess)
    assert [x["id"] for x in m.bodies] == [1, 2]


def test_every_request_has_meta_and_headers(mock_mcp):
    m = mock_mcp(echo())
    trace = TraceContext.for_task(TP)

    async def go():
        await m.client.list_tools(trace)
        await m.client.read_resource(trace, "politica://uso")
        await m.client.call_tool(trace, "reservar_sala", {"sala": "x"})
        await m.client.retry_tool(
            trace, "reservar_sala", {"sala": "x"}, input_key="k", input_response=accept_response("a"), request_state="s"
        )

    asyncio.run(go())
    for request, body in zip(m.requests, m.bodies):
        meta = body["params"]["_meta"]
        assert meta["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
        assert meta["io.modelcontextprotocol/clientCapabilities"] == {"elicitation": {"form": {}}}
        assert meta["io.modelcontextprotocol/clientInfo"]["name"] == "agente-central-de-salas"
        assert meta["traceparent"].startswith("00-4bf92f3577b34da6a3ce929d0e0e4736-")
        assert request.headers["MCP-Protocol-Version"] == "2026-07-28"
        assert request.headers["Mcp-Method"] == body["method"]
        assert request.headers["Content-Type"] == "application/json"
        assert request.headers["Accept"] == "application/json, text/event-stream"
        assert "traceparent" not in request.headers and "mcp-session-id" not in request.headers
        if body["method"] == "tools/list":
            assert "Mcp-Name" not in request.headers
        else:
            assert request.headers["Mcp-Name"] == (body["params"].get("name") or body["params"]["uri"])
        assert request.headers["host"] == "localhost:7301"


def test_same_trace_id_new_span_per_request(mock_mcp):
    m = mock_mcp(echo())
    trace = TraceContext.for_task(TP)

    async def go():
        for _ in range(3):
            await m.client.call_tool(trace, "t", {})

    asyncio.run(go())
    parents = [b["params"]["_meta"]["traceparent"].split("-") for b in m.bodies]
    assert {p[1] for p in parents} == {"4bf92f3577b34da6a3ce929d0e0e4736"}
    spans = {p[2] for p in parents}
    assert len(spans) == 3 and "00f067aa0ba902b7" not in spans


def test_retry_echoes_request_state_and_key(mock_mcp, wire):
    state = wire("03-tools-call-conflito-input-required.json")["response"]["body"]["result"]["requestState"]
    m = mock_mcp(echo())
    args = {"sala": "sala-garagem", "inicio": "i", "fim": "f", "responsavel": "Marty"}

    asyncio.run(
        m.client.retry_tool(
            TraceContext.for_task(None),
            "reservar_sala",
            args,
            input_key="__main__:escolha_de_sala",
            input_response=accept_response("sala-fusca"),
            request_state=state,
        )
    )
    params = m.bodies[0]["params"]
    assert params["requestState"] == state
    assert params["inputResponses"] == {"__main__:escolha_de_sala": accept_response("sala-fusca")}
    assert params["name"] == "reservar_sala" and params["arguments"] == args


def test_retry_without_request_state_omits_key(mock_mcp):
    m = mock_mcp(echo())
    asyncio.run(
        m.client.retry_tool(
            TraceContext.for_task(None), "t", {}, input_key="k", input_response=accept_response("a"), request_state=None
        )
    )
    assert "requestState" not in m.bodies[0]["params"]


def test_call_tool_returns_input_required_raw(mock_mcp, wire):
    result = wire("03-tools-call-conflito-input-required.json")["response"]["body"]["result"]
    m = mock_mcp(echo(lambda body: result))
    outcome = asyncio.run(m.client.call_tool(TraceContext.for_task(None), "reservar_sala", {}))
    assert isinstance(outcome, InputRequired) and outcome.request_state == result["requestState"]


def test_connect_error_is_unavailable(mock_mcp):
    m = mock_mcp([httpx.ConnectError("refused")])
    assert asyncio.run(m.client.call_tool(TraceContext.for_task(None), "t", {})) == UNAVAILABLE


def test_timeout_is_unavailable(hung_server):
    client = McpClient(f"http://localhost:{hung_server.port}/mcp", timeout=0.5)

    async def go():
        try:
            return await client.call_tool(TraceContext.for_task(None), "t", {})
        finally:
            await client.aclose()

    started = time.time()
    assert asyncio.run(go()) == UNAVAILABLE
    assert time.time() - started < 2


def test_default_timeout_is_10_seconds(mock_mcp):
    m = mock_mcp([])
    assert m.client._timeout == 10.0
    assert m.client._http.timeout == httpx.Timeout(10.0)


def test_jsonrpc_error_with_http_400_is_server_error(mock_mcp):
    body = {"jsonrpc": "2.0", "id": None, "error": {"code": -32602, "message": "Bad _meta"}}
    m = mock_mcp([json_answer(body, status=400)])
    outcome = asyncio.run(m.client.call_tool(TraceContext.for_task(None), "t", {}))
    assert outcome == ProtocolFailure("Erro do servidor MCP: -32602 Bad _meta", -32602)


def test_non_json_421_is_unexpected(mock_mcp):
    m = mock_mcp([(421, "text/plain", "Invalid Host header")])
    outcome = asyncio.run(m.client.call_tool(TraceContext.for_task(None), "t", {}))
    assert outcome == ProtocolFailure("Resposta inesperada do servidor MCP")


def test_result_with_other_id_is_unexpected(mock_mcp):
    m = mock_mcp([reply(99, {"resultType": "complete", "structuredContent": {}})])
    outcome = asyncio.run(m.client.call_tool(TraceContext.for_task(None), "t", {}))
    assert outcome == ProtocolFailure("Resposta inesperada do servidor MCP")


def test_sse_response_is_decoded(mock_mcp):
    import json

    def answer(request):
        body = json.loads(request.content)
        data = {"jsonrpc": "2.0", "id": body["id"], "result": {"structuredContent": {"a": 1}}}
        return (200, "text/event-stream", f"event: message\ndata: {json.dumps(data)}\n\n")

    m = mock_mcp(answer)
    assert asyncio.run(m.client.call_tool(TraceContext.for_task(None), "t", {})) == CompleteSuccess({"a": 1})


def test_tools_list_pagination(mock_mcp):
    def pages(request):
        import json

        body = json.loads(request.content)
        if "cursor" not in body["params"]:
            return reply(body["id"], {"tools": [{"name": "a", "inputSchema": {"type": "object"}}], "nextCursor": "c2"})
        assert body["params"]["cursor"] == "c2"
        return reply(body["id"], {"tools": [{"name": "b"}, {"nope": 1}, {"name": ""}]})

    m = mock_mcp(pages)
    tools = asyncio.run(m.client.list_tools(TraceContext.for_task(None)))
    assert [t.name for t in tools] == ["a", "b"]
    assert tools[0].input_schema == {"type": "object"} and tools[1].input_schema is None
    assert [b["id"] for b in m.bodies] == [1, 2]
    assert list(m.bodies[1]["params"]) == ["cursor", "_meta"]


def test_tools_list_page_limit(mock_mcp):
    m = mock_mcp(echo(lambda body: {"nextCursor": "again"}))
    outcome = asyncio.run(m.client.list_tools(TraceContext.for_task(None)))
    assert outcome == ProtocolFailure("Resposta inesperada do servidor MCP")
    assert len(m.bodies) == 10


def test_no_environment_proxy_is_used(mock_mcp, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    m = mock_mcp(echo())
    assert isinstance(asyncio.run(m.client.call_tool(TraceContext.for_task(None), "t", {})), CompleteSuccess)
    assert len(m.requests) == 1


def test_redirects_are_not_followed(mock_mcp):
    m = mock_mcp([(307, "text/plain", "")])
    outcome = asyncio.run(m.client.call_tool(TraceContext.for_task(None), "t", {}))
    assert outcome == ProtocolFailure("Resposta inesperada do servidor MCP")
    assert len(m.requests) == 1


def test_aclose_is_idempotent(mock_mcp):
    m = mock_mcp([])

    async def go():
        await m.client.aclose()
        await m.client.aclose()

    asyncio.run(go())


def test_cancelled_error_propagates():
    class Forever(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            await asyncio.Event().wait()

    client = McpClient("http://localhost:7301/mcp", transport=Forever())

    async def go():
        task = asyncio.ensure_future(client.call_tool(TraceContext.for_task(None), "t", {}))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(go())


def test_build_handlers_registers_client_aclose():
    from agente.config import load_settings
    from agente.skills import build_handlers

    handlers = build_handlers(load_settings({"MCP_URL": "http://127.0.0.1:9/mcp"}))
    assert handlers.aclose is not None
    asyncio.run(handlers.aclose())
    asyncio.run(handlers.aclose())
