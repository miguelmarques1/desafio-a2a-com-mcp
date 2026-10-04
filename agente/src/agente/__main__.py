"""Process entry point and startup sequence."""

from __future__ import annotations

import asyncio
import sys

import uvicorn

from agente import mensagens
from agente.agent_card import build_agent_card
from agente.app import build_app
from agente.config import ConfigError, load_settings
from agente.network import BindError, PortInUseError, bind_listening_socket
from agente.skills import build_handlers


def _fail(message: str) -> int:
    print(message, file=sys.stderr, flush=True)
    return 1


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        return _fail(str(exc))

    build_agent_card(settings.public_url)  # fail fast if the card cannot be built
    handlers = build_handlers(settings)
    app = build_app(settings, handlers=handlers)

    try:
        sock = bind_listening_socket(settings.host, settings.port)
    except PortInUseError as exc:
        return _fail(mensagens.PORTA_EM_USO.format(port=exc.port))
    except BindError as exc:
        return _fail(mensagens.FALHA_ABRIR.format(host=exc.host, port=exc.port, motivo=exc.motivo))

    for line in (
        mensagens.BANNER_OUVINDO.format(host=settings.host, port=settings.port),
        mensagens.BANNER_CARD.format(host=settings.host, port=settings.port),
        mensagens.BANNER_ENDPOINT.format(public_url=settings.public_url),
    ):
        print(line, file=sys.stderr, flush=True)

    config = uvicorn.Config(app, lifespan="on", log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    try:
        asyncio.run(server.serve(sockets=[sock]))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
