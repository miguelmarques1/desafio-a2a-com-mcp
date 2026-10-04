"""Environment configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from servidor_mcp import mensagens

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7301


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    dados_dir: str | None
    request_state_secret: str | None  # read raw; validated in seguranca.py


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    raw_port = env.get("MCP_PORT")
    port = DEFAULT_PORT
    if raw_port is not None:
        try:
            port = int(raw_port)
        except ValueError:
            raise ConfigError(mensagens.MCP_PORT_INVALIDA.format(valor=raw_port)) from None
        if not 1 <= port <= 65535:
            raise ConfigError(mensagens.MCP_PORT_INVALIDA.format(valor=raw_port))
    return Settings(
        host=env.get("MCP_HOST", DEFAULT_HOST),
        port=port,
        dados_dir=env.get("MCP_DADOS_DIR"),
        request_state_secret=env.get("REQUEST_STATE_SECRET"),
    )
