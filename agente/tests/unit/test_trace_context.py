import re

import pytest

from agente.mcp_host.trace_context import TraceContext, new_span_id, parse_traceparent

TP = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"


def test_valid_traceparent_keeps_trace_id_and_flags():
    t = TraceContext.for_task(TP)
    assert (t.trace_id, t.flags, t.generated) == (TRACE, "01", False)
    assert TraceContext.for_task(TP.replace("-01", "-00")).flags == "00"


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        TP.upper(),
        "01" + TP[2:],
        "ff" + TP[2:],
        "00-" + "0" * 32 + "-00f067aa0ba902b7-01",
        "00-" + TRACE + "-" + "0" * 16 + "-01",
        "00-abc-def-01",
        TP + "-extra",
        "garbage",
    ],
)
def test_invalid_traceparent_variants_generate(raw):
    t = TraceContext.for_task(raw)
    assert t.generated is True
    assert re.fullmatch(r"[0-9a-f]{32}", t.trace_id) and t.trace_id != "0" * 32
    assert t.flags == "01"


def test_whitespace_around_header_is_stripped():
    assert parse_traceparent(f"  {TP}  ").trace_id == TRACE


def test_new_span_id_format_and_difference_from_parent():
    parent = "00f067aa0ba902b7"
    spans = [new_span_id(parent) for _ in range(1000)]
    assert all(re.fullmatch(r"[0-9a-f]{16}", s) and s != "0" * 16 and s != parent for s in spans)
    t = TraceContext.for_task(TP)
    assert all(t.new_span_id() != parent for _ in range(200))


def test_header_value_rendering():
    t = TraceContext.for_task(TP)
    assert t.header_value("aaaaaaaaaaaaaaaa") == f"00-{TRACE}-aaaaaaaaaaaaaaaa-01"


def test_for_continuation_prefers_valid_new_header():
    stored = TraceContext.for_task(None)
    assert TraceContext.for_continuation(stored, TP).trace_id == TRACE


@pytest.mark.parametrize("raw", [None, "", "nope"])
def test_for_continuation_falls_back_to_stored(raw):
    stored = TraceContext.for_task(None)
    assert TraceContext.for_continuation(stored, raw) is stored


def test_two_tasks_without_header_get_different_trace_ids():
    assert TraceContext.for_task(None).trace_id != TraceContext.for_task(None).trace_id
