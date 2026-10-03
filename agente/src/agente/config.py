"""Environment configuration.

F06 extends Settings with `mcp_url` (MCP_URL).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from agente import mensagens

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7300


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    public_url: str


def _parse_port(raw: str) -> int:
    if raw.isascii() and raw.isdigit() and 1 <= int(raw) <= 65535:
        return int(raw)
    raise ConfigError(mensagens.AGENT_PORT_INVALIDA.format(valor=raw))


def _parse_public_url(raw: str) -> str:
    try:
        parts = urlsplit(raw)
        valid = parts.scheme in ("http", "https") and bool(parts.hostname)
        parts.port  # noqa: B018 - raises ValueError on a malformed port
    except ValueError:
        valid = False
    if not valid:
        raise ConfigError(mensagens.AGENT_PUBLIC_URL_INVALIDA.format(valor=raw))
    return raw[:-1] if raw.endswith("/") else raw


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    raw_port = env.get("AGENT_PORT")
    port = DEFAULT_PORT if raw_port is None else _parse_port(raw_port)
    raw_url = env.get("AGENT_PUBLIC_URL")
    public_url = f"http://localhost:{port}" if raw_url is None else _parse_public_url(raw_url)
    return Settings(host=env.get("AGENT_HOST", DEFAULT_HOST), port=port, public_url=public_url)
