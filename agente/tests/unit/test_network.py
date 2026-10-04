import socket

import pytest

from agente.network import BindError, PortInUseError, bind_listening_socket


def test_binds_free_port_and_listens(free_port):
    port = free_port()
    sock = bind_listening_socket("127.0.0.1", port)
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
    finally:
        sock.close()


def test_port_in_use_raises_port_in_use_error(free_port):
    port = free_port()
    holder = bind_listening_socket("127.0.0.1", port)
    try:
        with pytest.raises(PortInUseError) as info:
            bind_listening_socket("127.0.0.1", port)
        assert info.value.port == port
    finally:
        holder.close()


def test_unknown_host_raises_bind_error():
    with pytest.raises(BindError) as info:
        bind_listening_socket("nao-existe.invalid", 7300)
    assert (info.value.host, info.value.port) == ("nao-existe.invalid", 7300)
    assert info.value.motivo
