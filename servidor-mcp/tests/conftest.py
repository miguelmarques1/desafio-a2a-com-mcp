from __future__ import annotations

import io
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from servidor_mcp.app import build_app
from servidor_mcp.config import Settings
from servidor_mcp.loader import load_dominio
from servidor_mcp.paths import find_repo_root
from servidor_mcp.primitives import REGISTRARS
from servidor_mcp.server import build_server

PROTOCOL_VERSION = "2026-07-28"
FORM_CAPS = {"elicitation": {"form": {}}}
TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
_SENTINEL = object()


@pytest.fixture(scope="session")
def repo_root() -> Path:
    root = find_repo_root(Path(__file__).parent)
    assert root is not None
    return root


@pytest.fixture
def dados_tmp(repo_root: Path, tmp_path: Path) -> Path:
    destino = tmp_path / "dados"
    shutil.copytree(repo_root / "dados", destino)
    return destino


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(name="free_port")
def free_port_fixture():
    return free_port


def build_envelope(
    method: str,
    params: dict | None = None,
    *,
    id=1,
    caps=_SENTINEL,
    traceparent: str | None = None,
    drop_meta: tuple[str, ...] = (),
) -> dict:
    meta = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": FORM_CAPS if caps is _SENTINEL else caps,
    }
    if traceparent:
        meta["traceparent"] = traceparent
    for key in drop_meta:
        meta.pop(key, None)
    return {
        "jsonrpc": "2.0",
        "id": id,
        "method": method,
        "params": {**(params or {}), "_meta": meta},
    }


def build_headers(body: dict, **overrides) -> dict:
    method = body["method"]
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    params = body.get("params") or {}
    if method == "tools/call":
        headers["Mcp-Name"] = params["name"]
    elif method == "resources/read":
        headers["Mcp-Name"] = params["uri"]
    for key, value in overrides.items():
        header = key.replace("_", "-")
        if value is None:
            headers.pop(header, None)
        else:
            headers[header] = value
    return headers


@pytest.fixture
def mcp_post():
    """Returns ``call(client, method, params=None, **options)`` -> httpx.Response.

    Options: id, caps, traceparent, drop_meta (tuple of _meta keys to omit) and
    header overrides through ``headers={...}`` (value ``None`` removes a header).
    """

    def call(client, method, params=None, *, headers=None, **options):
        body = build_envelope(method, params, **options)
        return client.post("/mcp", json=body, headers=build_headers(body, **(headers or {})))

    return call


@pytest.fixture
def fresh_app(repo_root: Path):
    """Factory: ``make(registrars=None, request_state_security=None)`` -> (TestClient, log_lines, dominio).

    ``registrars=None`` means the production registry; ``request_state_security=None`` keeps the SDK's
    ephemeral per-process key. Close handled at teardown.
    """
    stack: list[TestClient] = []

    def make(registrars=None, request_state_security=None):
        dominio = load_dominio(repo_root / "dados")
        if registrars is None:
            registrars = REGISTRARS
        server = build_server(dominio, registrars=registrars, request_state_security=request_state_security)
        stream = io.StringIO()
        settings = Settings("127.0.0.1", 7301, None, None)
        app = build_app(server, settings, log_stream=stream)
        client = TestClient(app, base_url="http://127.0.0.1:7301")
        client.__enter__()
        stack.append(client)

        def log_lines() -> list[str]:
            return [line for line in stream.getvalue().splitlines() if line]

        return client, log_lines, dominio

    yield make
    for client in stack:
        client.__exit__(None, None, None)


class ServerProcess:
    def __init__(self, proc: subprocess.Popen, port: int):
        self.proc = proc
        self.port = port
        self.lines: list[str] = []
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        for line in self.proc.stderr:
            self.lines.append(line.rstrip("\r\n"))

    def wait_for_line(self, fragment: str, timeout: float = 20.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if any(fragment in line for line in self.lines):
                return True
            if self.proc.poll() is not None:
                time.sleep(0.2)
                return any(fragment in line for line in self.lines)
            time.sleep(0.05)
        return False

    def wait_for_log_count(self, count: int, timeout: float = 10.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len([ln for ln in self.lines if ln.startswith("mcp ")]) >= count:
                return
            time.sleep(0.05)

    def stop(self) -> int | None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self._thread.join(timeout=5)
        return self.proc.returncode

    def wait_exit(self, timeout: float = 20.0) -> int:
        return self.proc.wait(timeout=timeout)


@pytest.fixture
def start_server():
    started: list[ServerProcess] = []

    def start(*, port: int | None = None, env: dict | None = None, cwd=None, wait_banner=True):
        port = port if port is not None else free_port()
        full_env = {**os.environ, "REQUEST_STATE_SECRET": secrets.token_hex(32)}
        full_env.pop("MCP_PORT", None)
        full_env.pop("MCP_HOST", None)
        full_env.pop("MCP_DADOS_DIR", None)
        full_env["MCP_PORT"] = str(port)
        full_env.update(env or {})
        full_env = {k: v for k, v in full_env.items() if v is not None}
        proc = subprocess.Popen(
            [sys.executable, "-m", "servidor_mcp"],
            env=full_env,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        server = ServerProcess(proc, port)
        started.append(server)
        if wait_banner:
            server.wait_for_line("ouvindo em")
        return server

    yield start
    for server in started:
        server.stop()
