"""Listening socket creation and port-in-use detection."""

from __future__ import annotations

import errno
import socket
import sys

_WSAEADDRINUSE = 10048
_WSAEACCES = 10013  # Windows reports an exclusive-bind conflict this way


class PortInUseError(Exception):
    def __init__(self, port: int):
        self.port = port
        super().__init__(f"port {port} in use")


class BindError(Exception):
    def __init__(self, host: str, port: int, motivo: str):
        self.host, self.port, self.motivo = host, port, motivo
        super().__init__(f"{host}:{port}: {motivo}")


def _is_in_use(exc: OSError) -> bool:
    if exc.errno == errno.EADDRINUSE:
        return True
    return getattr(exc, "winerror", None) in (_WSAEADDRINUSE, _WSAEACCES)


def bind_listening_socket(host: str, port: int) -> socket.socket:
    try:
        family = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0][0]
    except OSError as exc:
        raise BindError(host, port, exc.strerror or str(exc)) from exc
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        if sys.platform == "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(128)
        sock.setblocking(False)
    except OSError as exc:
        sock.close()
        if _is_in_use(exc):
            raise PortInUseError(port) from exc
        raise BindError(host, port, exc.strerror or str(exc)) from exc
    return sock
