"""W3C trace context: one TraceContext per Task, a new span-id per MCP request."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field

_TRACEPARENT = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")
_ZERO_TRACE = "0" * 32
_ZERO_SPAN = "0" * 16


def new_span_id(avoid: str | None = None) -> str:
    while True:
        span = secrets.token_hex(8)
        if span != _ZERO_SPAN and span != avoid:
            return span


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    flags: str
    generated: bool
    _parent_id: str | None = field(default=None, repr=False, compare=False)

    @classmethod
    def for_task(cls, raw: str | None) -> TraceContext:
        parsed = parse_traceparent(raw)
        if parsed is not None:
            return parsed
        while True:
            trace_id = secrets.token_hex(16)
            if trace_id != _ZERO_TRACE:
                return cls(trace_id=trace_id, flags="01", generated=True)

    @classmethod
    def for_continuation(cls, stored: TraceContext, raw: str | None) -> TraceContext:
        return parse_traceparent(raw) or stored

    def new_span_id(self) -> str:
        return new_span_id(self._parent_id)

    def header_value(self, span_id: str) -> str:
        return f"00-{self.trace_id}-{span_id}-{self.flags}"


def parse_traceparent(raw: str | None) -> TraceContext | None:
    if not isinstance(raw, str):
        return None
    match = _TRACEPARENT.match(raw.strip())
    if match is None:
        return None
    trace_id, parent_id, flags = match.groups()
    if trace_id == _ZERO_TRACE or parent_id == _ZERO_SPAN:
        return None
    return TraceContext(trace_id=trace_id, flags=flags, generated=False, _parent_id=parent_id)
