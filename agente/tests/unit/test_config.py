import pytest

from agente.config import ConfigError, load_settings


def test_defaults_when_env_empty():
    s = load_settings({})
    assert (s.host, s.port, s.public_url) == ("127.0.0.1", 7300, "http://localhost:7300")


def test_reads_agent_port_and_agent_host():
    s = load_settings({"AGENT_PORT": "7400", "AGENT_HOST": "0.0.0.0"})
    assert (s.host, s.port) == ("0.0.0.0", 7400)
    assert isinstance(s.port, int)


def test_public_url_default_follows_agent_port():
    assert load_settings({"AGENT_PORT": "7400"}).public_url == "http://localhost:7400"


def test_public_url_override_strips_trailing_slash():
    s = load_settings({"AGENT_PUBLIC_URL": "http://127.0.0.1:7300/"})
    assert s.public_url == "http://127.0.0.1:7300"


@pytest.mark.parametrize("raw", ["abc", "0", "70000", "", "-1", " 7"])
def test_invalid_agent_port_raises_config_error(raw):
    with pytest.raises(ConfigError) as info:
        load_settings({"AGENT_PORT": raw})
    assert str(info.value) == f"AGENT_PORT invalida: {raw}"


@pytest.mark.parametrize("raw", ["localhost:7300", "ftp://x", "http://", "", "http://h:abc"])
def test_invalid_public_url_raises_config_error(raw):
    with pytest.raises(ConfigError) as info:
        load_settings({"AGENT_PUBLIC_URL": raw})
    assert str(info.value) == f"AGENT_PUBLIC_URL invalida: {raw}"
