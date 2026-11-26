"""Single-instance aggregation over a per-user local socket.

Wire format: 4-byte big-endian length + UTF-8 JSON list of absolute directory paths.
Received data is only ever validated and handed to a signal; it is never executed.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import struct
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from iconreplacer.version import PRODUCT_NAME

MAX_MESSAGE_BYTES = 64 * 1024
CONNECT_TIMEOUT_MS = 300
ACK_TIMEOUT_MS = 1000
_ACK = b"\x01"
CONN_LIFETIME_MS = 3000
STARTUP_WINDOW_MS = 400
_HEADER = struct.Struct(">I")


def server_name() -> str:
    """Per-user name: app name + hash of user identity (not world-shared)."""
    ident = f"{os.environ.get('USERDOMAIN', '')}\\{getpass.getuser()}|{Path.home()}".lower()
    return f"{PRODUCT_NAME}-{hashlib.sha1(ident.encode()).hexdigest()[:16]}"


def validate_folders(payload: object) -> list[Path]:
    """Keep only absolute, existing directories from a decoded JSON payload."""
    if not isinstance(payload, list):
        return []
    out: list[Path] = []
    for item in payload:
        if not isinstance(item, str) or not item or "\0" in item:
            continue
        p = Path(item)
        if p.is_absolute() and p.is_dir():
            out.append(p)
    return out


def encode_message(folders: Sequence[Path | str]) -> bytes:
    body = json.dumps([str(f) for f in folders]).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        raise ValueError("message too large")
    return _HEADER.pack(len(body)) + body


def decode_message(data: bytes) -> list[Path] | None:
    """Decode one complete message; ``None`` if malformed or oversized."""
    if len(data) < _HEADER.size:
        return None
    (length,) = _HEADER.unpack_from(data)
    body = data[_HEADER.size :]
    if length > MAX_MESSAGE_BYTES or len(body) != length:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(payload, list):
        return None
    return validate_folders(payload)


def send_folders(folders: Sequence[Path | str], name: str | None = None) -> bool:
    """Send folders to a running instance. ``False`` if none could be reached."""
    sock = QLocalSocket()
    sock.connectToServer(name or server_name())
    if not sock.waitForConnected(CONNECT_TIMEOUT_MS):
        return False
    try:
        data = encode_message(folders)
    except ValueError:
        sock.abort()
        return False
    sock.write(data)
    sock.waitForBytesWritten(CONNECT_TIMEOUT_MS)  # may return False if already flushed
    ok = sock.bytesToWrite() == 0 and sock.state() == QLocalSocket.LocalSocketState.ConnectedState
    if ok:
        sock.waitForReadyRead(ACK_TIMEOUT_MS)  # best-effort ack so the server has read it
    sock.disconnectFromServer()
    if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        sock.waitForDisconnected(CONNECT_TIMEOUT_MS)
    return ok


class SingleInstanceServer(QObject):
    """Receives folder lists from later instances; emits ``folders_received``."""

    folders_received = Signal(list)  # list[Path]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._on_connection)
        self._buffers: dict[QLocalSocket, bytearray] = {}

    @property
    def listening(self) -> bool:
        return self._server.isListening()

    def listen(self, name: str | None = None) -> bool:
        name = name or server_name()
        if self._server.listen(name):
            return True
        # Nobody answered a client probe, so a leftover socket name is stale.
        QLocalServer.removeServer(name)
        return self._server.listen(name)

    def close(self) -> None:
        self._server.close()

    def _on_connection(self) -> None:
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            self._buffers[sock] = bytearray()
            sock.readyRead.connect(lambda s=sock: self._on_ready(s))
            sock.disconnected.connect(lambda s=sock: self._drop(s))
            QTimer.singleShot(CONN_LIFETIME_MS, sock, sock.abort)

    def _drop(self, sock: QLocalSocket) -> None:
        self._buffers.pop(sock, None)
        sock.deleteLater()

    def _on_ready(self, sock: QLocalSocket) -> None:
        buf = self._buffers.get(sock)
        if buf is None:
            return
        buf += bytes(sock.readAll())
        if len(buf) >= _HEADER.size:
            (length,) = _HEADER.unpack_from(buf)
            if length > MAX_MESSAGE_BYTES:
                self._reject(sock)
                return
            if len(buf) < _HEADER.size + length:
                return
            if len(buf) > _HEADER.size + length:
                self._reject(sock)
                return
            folders = decode_message(bytes(buf))
            self._buffers[sock] = bytearray()
            if folders is not None:
                sock.write(_ACK)
            sock.disconnectFromServer()
            if folders:
                self.folders_received.emit(folders)

    def _reject(self, sock: QLocalSocket) -> None:
        self._buffers.pop(sock, None)
        sock.abort()


def acquire(folders: Sequence[Path | str], name: str | None = None) -> SingleInstanceServer | None:
    """Become the first instance, or forward ``folders`` and return ``None``.

    If a server cannot be started either, an idle server object is returned so the
    app simply runs on its own.
    """
    if send_folders(folders, name):
        return None
    server = SingleInstanceServer()
    if not server.listen(name) and send_folders(folders, name):
        # Lost a startup race against a sibling that began listening just before us.
        return None
    return server


def collect_startup_folders(
    server: SingleInstanceServer | None,
    initial: Sequence[Path],
    window_ms: int = STARTUP_WINDOW_MS,
) -> list[Path]:
    """Wait ``window_ms`` for sibling launches (multi-select) and merge their folders."""
    merged: dict[str, Path] = {}

    def add(folders: Sequence[Path]) -> None:
        for p in folders:
            merged.setdefault(str(p).lower(), p)

    add(initial)
    if server is None or not server.listening or not initial:
        return list(merged.values())

    loop = QEventLoop()
    server.folders_received.connect(add)
    QTimer.singleShot(window_ms, loop.quit)
    loop.exec()
    server.folders_received.disconnect(add)
    return list(merged.values())
