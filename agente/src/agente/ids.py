"""Identifier generation: task-, ctx-, msg-, art- plus 12 lowercase hex digits."""

from __future__ import annotations

import secrets
from typing import Protocol

TASK_PREFIX = "task-"
CONTEXT_PREFIX = "ctx-"
MESSAGE_PREFIX = "msg-"
ARTIFACT_PREFIX = "art-"


class IdFactory(Protocol):
    def task_id(self) -> str: ...
    def context_id(self) -> str: ...
    def message_id(self) -> str: ...
    def artifact_id(self) -> str: ...


def _hex12() -> str:
    return secrets.token_hex(6)


class RandomIdFactory:
    def task_id(self) -> str:
        return TASK_PREFIX + _hex12()

    def context_id(self) -> str:
        return CONTEXT_PREFIX + _hex12()

    def message_id(self) -> str:
        return MESSAGE_PREFIX + _hex12()

    def artifact_id(self) -> str:
        return ARTIFACT_PREFIX + _hex12()
