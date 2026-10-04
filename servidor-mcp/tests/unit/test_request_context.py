from types import SimpleNamespace

import pytest
from mcp_types import ClientCapabilities

from servidor_mcp.request_context import client_capabilities, declares_form_elicitation


def ctx(caps):
    return SimpleNamespace(client_capabilities=caps)


def test_client_capabilities_returns_request_value():
    caps = ClientCapabilities.model_validate({"elicitation": {"form": {}}})
    assert client_capabilities(ctx(caps)) is caps


def test_declares_form_elicitation_true_for_form():
    assert declares_form_elicitation(ctx(ClientCapabilities.model_validate({"elicitation": {"form": {}}}))) is True


def test_declares_form_elicitation_false_for_empty_capabilities():
    assert declares_form_elicitation(ctx(ClientCapabilities.model_validate({}))) is False


@pytest.mark.parametrize("raw", [{"elicitation": {}}, {"elicitation": {"url": {}}}])
def test_declares_form_elicitation_false_without_form_mode(raw):
    assert declares_form_elicitation(ctx(ClientCapabilities.model_validate(raw))) is False


def test_declares_form_elicitation_false_when_capabilities_absent():
    assert declares_form_elicitation(ctx(None)) is False
