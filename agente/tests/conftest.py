from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest


class FixedIds:
    """IdFactory double: per-kind queues, then deterministic counters."""

    def __init__(self, *, task=(), context=(), message=(), artifact=()):
        self._queues = {
            "task": list(task),
            "ctx": list(context),
            "msg": list(message),
            "art": list(artifact),
        }
        self._counters = {"task": 0, "ctx": 0, "msg": 0, "art": 0}

    def _next(self, kind: str) -> str:
        queue = self._queues[kind]
        if queue:
            return queue.pop(0)
        self._counters[kind] += 1
        return f"{kind}-{self._counters[kind]:012d}"

    def task_id(self) -> str:
        return self._next("task")

    def context_id(self) -> str:
        return self._next("ctx")

    def message_id(self) -> str:
        return self._next("msg")

    def artifact_id(self) -> str:
        return self._next("art")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "exemplos").is_dir() and (parent / "agente").is_dir():
            return parent
    raise RuntimeError("repo root not found")


@pytest.fixture(scope="session")
def wire(repo_root: Path):
    def load(name: str) -> dict:
        return json.loads((repo_root / "exemplos" / "wire" / name).read_text(encoding="utf-8"))

    return load


@pytest.fixture
def fixed_ids():
    return FixedIds


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(name="free_port")
def free_port_fixture():
    return free_port
