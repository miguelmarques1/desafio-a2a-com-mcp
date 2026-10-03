import pytest

from servidor_mcp.config import ConfigError, load_settings


def test_defaults_when_env_empty():
    s = load_settings({})
    assert (s.host, s.port, s.dados_dir, s.request_state_secret) == ("127.0.0.1", 7301, None, None)


def test_reads_mcp_port_and_mcp_host():
    s = load_settings({"MCP_PORT": "8123", "MCP_HOST": "localhost"})
    assert s.port == 8123 and isinstance(s.port, int)
    assert s.host == "localhost"


@pytest.mark.parametrize("valor", ["abc", "0", "70000", ""])
def test_invalid_mcp_port_raises_config_error(valor):
    with pytest.raises(ConfigError) as exc:
        load_settings({"MCP_PORT": valor})
    assert str(exc.value) == f"MCP_PORT invalida: {valor}"


def test_request_state_secret_is_read_raw():
    assert load_settings({"REQUEST_STATE_SECRET": "abc"}).request_state_secret == "abc"


def test_mcp_dados_dir_override_is_read():
    assert load_settings({"MCP_DADOS_DIR": "/x/dados"}).dados_dir == "/x/dados"
