"""Process entry point and startup sequence."""

from __future__ import annotations

import asyncio
import sys

import uvicorn

from servidor_mcp import mensagens
from servidor_mcp.app import build_app
from servidor_mcp.config import ConfigError, load_settings
from servidor_mcp.loader import DataLoadError, PolicyVersionMissingError, load_dominio
from servidor_mcp.network import BindError, PortInUseError, bind_listening_socket
from servidor_mcp.paths import resolve_dados_dir
from servidor_mcp.seguranca import SegredoInvalidoError, politica_de_estado, validar_segredo
from servidor_mcp.server import build_server


def _fail(message: str) -> int:
    print(message, file=sys.stderr, flush=True)
    return 1


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        return _fail(str(exc))

    try:
        politica = politica_de_estado(validar_segredo(settings.request_state_secret))
    except SegredoInvalidoError as exc:
        return _fail(str(exc))

    try:
        dominio = load_dominio(resolve_dados_dir(settings.dados_dir))
    except (DataLoadError, PolicyVersionMissingError) as exc:
        return _fail(str(exc))

    server = build_server(dominio, request_state_security=politica)
    app = build_app(server, settings)

    try:
        sock = bind_listening_socket(settings.host, settings.port)
    except PortInUseError as exc:
        return _fail(mensagens.PORTA_EM_USO.format(port=exc.port))
    except BindError as exc:
        return _fail(mensagens.FALHA_ABRIR.format(host=exc.host, port=exc.port, motivo=exc.motivo))

    for line in (
        mensagens.BANNER_OUVINDO.format(host=settings.host, port=settings.port),
        mensagens.BANNER_SALAS.format(n=len(dominio.catalogo)),
        mensagens.BANNER_RESERVAS.format(n=len(dominio.reservas)),
        mensagens.BANNER_POLITICA.format(versao=dominio.politica.versao),
    ):
        print(line, file=sys.stderr, flush=True)

    config = uvicorn.Config(app, lifespan="on", log_level="warning", access_log=False)
    uvicorn_server = uvicorn.Server(config)
    try:
        asyncio.run(uvicorn_server.serve(sockets=[sock]))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
