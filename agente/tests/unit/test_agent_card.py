import json

from agente.agent_card import build_agent_card, render_agent_card


def test_card_equals_wire_07_for_same_public_url(wire):
    expected = wire("07-a2a-agent-card.json")["response"]["body"]
    assert json.dumps(build_agent_card("http://127.0.0.1:7300")) == json.dumps(expected)


def test_interface_url_uses_public_url_and_a2a_path():
    card = build_agent_card("http://agente.example:9000")
    assert card["supportedInterfaces"][0]["url"] == "http://agente.example:9000/a2a"


def test_card_has_no_v0_fields_and_no_security():
    card = build_agent_card("http://localhost:7300")
    for key in (
        "preferredTransport",
        "additionalInterfaces",
        "interfaces",
        "securitySchemes",
        "security",
        "url",
        "protocolVersion",
        "signatures",
    ):
        assert key not in card


def test_rendered_card_bytes_parse_to_card():
    rendered = render_agent_card("http://localhost:7300")
    assert json.loads(rendered) == build_agent_card("http://localhost:7300")
