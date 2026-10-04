import secrets

import pytest
from mcp.server.request_state import AESGCMRequestStateCodec

from servidor_mcp import mensagens
from servidor_mcp.seguranca import SegredoInvalidoError, politica_de_estado, validar_segredo

PRD_MESSAGE = (
    "REQUEST_STATE_SECRET ausente ou com menos de 32 bytes: "
    'gere com python3 -c "import secrets; print(secrets.token_hex(32))"'
)


def test_valid_secret_from_token_hex():
    segredo = secrets.token_hex(32)
    assert validar_segredo(segredo) == segredo


@pytest.mark.parametrize("segredo", ["a1" * 48, "b" * 65])
def test_longer_hex_secret_accepted(segredo):
    assert validar_segredo(segredo) == segredo


def test_uppercase_hex_accepted():
    assert validar_segredo("A" * 64) == "A" * 64


@pytest.mark.parametrize("valor", [None, ""])
def test_missing_secret_rejected(valor):
    with pytest.raises(SegredoInvalidoError) as exc:
        validar_segredo(valor)
    assert str(exc.value) == mensagens.SEGREDO_INVALIDO


def test_short_secret_rejected():
    with pytest.raises(SegredoInvalidoError):
        validar_segredo("a" * 63)


@pytest.mark.parametrize("valor", ["a" * 63 + "g", "a" * 64 + " ", " " + "a" * 64, "a" * 64 + "\n"])
def test_non_hex_secret_rejected(valor):
    with pytest.raises(SegredoInvalidoError):
        validar_segredo(valor)


def test_policy_uses_ttl_600_and_codec():
    politica = politica_de_estado(secrets.token_hex(32))
    assert politica.ttl == 600
    assert isinstance(politica.codec, AESGCMRequestStateCodec)
    assert politica.audience is None


def test_message_text_is_exact():
    assert mensagens.SEGREDO_INVALIDO == PRD_MESSAGE
