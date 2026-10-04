import secrets

import pytest

from servidor_mcp import mensagens


def test_startup_without_secret_exits_1(start_server):
    server = start_server(env={"REQUEST_STATE_SECRET": None}, wait_banner=False)
    assert server.wait_exit() == 1
    server.stop()
    assert server.lines == [mensagens.SEGREDO_INVALIDO]


@pytest.mark.parametrize("segredo", ["a" * 63, "z" * 64])
def test_startup_with_short_or_non_hex_secret_exits_1(start_server, segredo):
    server = start_server(env={"REQUEST_STATE_SECRET": segredo}, wait_banner=False)
    assert server.wait_exit() == 1
    server.stop()
    assert server.lines == [mensagens.SEGREDO_INVALIDO]
    assert not any("ouvindo em" in line for line in server.lines)


def test_startup_with_valid_secret_prints_banner(start_server):
    server = start_server(env={"REQUEST_STATE_SECRET": secrets.token_hex(32)})
    assert any("ouvindo em" in line for line in server.lines)
