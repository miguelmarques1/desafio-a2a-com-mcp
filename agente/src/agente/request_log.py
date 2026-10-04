"""stderr request log: one `a2a method=... id=... task=... state=...` line per request."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from typing import Any

_DASH_LINE = "a2a method=- id=- task=- state=-"
_NEEDS_QUOTE = re.compile(r"[\s\x00-\x1f\x7f]")


@dataclass(frozen=True)
class LogFields:
    method: Any = None
    rpc_id: Any = None
    task_id: Any = None
    state: Any = None


def _render_id(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return _render_text(value)


def _render_text(value: Any) -> str:
    if not isinstance(value, str):
        return "-"
    if value == "" or _NEEDS_QUOTE.search(value):
        return json.dumps(value)
    return value


def format_log_line(method: Any, rpc_id: Any, task_id: Any, state: Any) -> str:
    state_text = getattr(state, "value", state)
    return (
        f"a2a method={_render_text(method)} id={_render_id(rpc_id)} "
        f"task={_render_text(task_id)} state={_render_text(state_text)}"
    )


class RequestLogger:
    def __init__(self, stream: Any = None):
        self._stream = stream

    def log(self, fields: LogFields) -> None:
        try:
            line = format_log_line(fields.method, fields.rpc_id, fields.task_id, fields.state)
        except Exception:
            line = _DASH_LINE
        try:
            stream = self._stream if self._stream is not None else sys.stderr
            stream.write(line + "\n")
            stream.flush()
        except Exception:
            pass
