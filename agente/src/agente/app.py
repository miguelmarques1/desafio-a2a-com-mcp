"""Starlette application assembly: card route, A2A route, shutdown hook."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from agente.agent_card import A2A_PATH, AGENT_CARD_PATH, render_agent_card
from agente.config import Settings
from agente.dispatcher import Dispatcher
from agente.handlers import Handlers
from agente.ids import IdFactory
from agente.request_log import RequestLogger
from agente.task_store import TaskStore

JSON = "application/json"

__all__ = ["A2A_PATH", "build_app"]


def build_app(
    settings: Settings,
    *,
    handlers: Handlers,
    store: TaskStore | None = None,
    ids: IdFactory | None = None,
    log_stream: Any = None,
) -> Starlette:
    store = store if store is not None else TaskStore(ids)
    dispatcher = Dispatcher(store, handlers, diag_stream=log_stream)
    logger = RequestLogger(log_stream)
    card_bytes = render_agent_card(settings.public_url)

    async def agent_card(request: Request) -> Response:
        return Response(card_bytes, 200, media_type=JSON)

    async def a2a(request: Request) -> Response:
        body = await request.body()
        outcome = await dispatcher.dispatch(
            body,
            a2a_version=request.headers.get("a2a-version"),
            traceparent=request.headers.get("traceparent"),
        )
        logger.log(outcome.log_fields)
        return Response(outcome.body, 200, media_type=JSON)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if handlers.aclose is not None:
                await handlers.aclose()

    return Starlette(
        routes=[
            Route(AGENT_CARD_PATH, agent_card, methods=["GET"]),
            Route(A2A_PATH, a2a, methods=["POST"]),
        ],
        lifespan=lifespan,
    )
