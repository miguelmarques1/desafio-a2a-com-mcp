"""Agent Card construction (shape and key order of exemplos/wire/07)."""

from __future__ import annotations

from typing import Any

from agente.jsonrpc import render

AGENT_CARD_PATH = "/.well-known/agent-card.json"
A2A_PATH = "/a2a"

AGENT_NAME = "Central de Salas"
AGENT_DESCRIPTION = "Reserva salas de reuniao da Hill Valley Tech."
PROVIDER_ORGANIZATION = "Hill Valley Tech"
PROVIDER_URL = "https://hillvalley.example"
AGENT_VERSION = "1.0.0"
SKILL_ID = "reservar-sala"
SKILL_NAME = "Reservar sala"
SKILL_DESCRIPTION = (
    "Reserva uma sala em um intervalo. Se houver conflito, pergunta qual alternativa usar."
)
SKILL_EXAMPLE = (
    "reservar sala=sala-garagem inicio=2026-11-03T14:00:00-03:00 "
    "fim=2026-11-03T15:00:00-03:00 responsavel=Marty"
)


def build_agent_card(public_url: str) -> dict[str, Any]:
    return {
        "name": AGENT_NAME,
        "description": AGENT_DESCRIPTION,
        "provider": {"organization": PROVIDER_ORGANIZATION, "url": PROVIDER_URL},
        "version": AGENT_VERSION,
        "supportedInterfaces": [
            {
                "url": f"{public_url}{A2A_PATH}",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": SKILL_ID,
                "name": SKILL_NAME,
                "description": SKILL_DESCRIPTION,
                "tags": ["salas", "agenda"],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain"],
                "examples": [SKILL_EXAMPLE],
            }
        ],
    }


def render_agent_card(public_url: str) -> bytes:
    return render(build_agent_card(public_url))
