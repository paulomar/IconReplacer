"""IPC tests. Clients run as separate processes (like Explorer launches), while the
server lives in the test process and is pumped by the Qt event loop."""

import json
import struct
import subprocess
import sys
import uuid

import pytest
from PySide6.QtCore import QCoreApplication

from iconreplacer.shell import ipc

CLIENT_CODE = r"""
import sys
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalSocket
from iconreplacer.shell import ipc

app = QCoreApplication([])
mode, name = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
if mode == "send":
    sys.exit(0 if ipc.send_folders(args, name) else 1)
if mode == "acquire":
    srv = ipc.acquire(args, name)
    sys.exit(0 if srv is None else 3)
if mode == "raw":
    s = QLocalSocket()
    s.connectToServer(name)
    assert s.waitForConnected(1000)
    s.write(bytes.fromhex(args[0]))
    s.waitForBytesWritten(1000)
    s.waitForReadyRead(300)
    s.disconnectFromServer()
"""


def _client(mode, name, *args):
    return subprocess.Popen(
        [sys.executable, "-I", "-c", CLIENT_CODE, mode, name, *map(str, args)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _run(qtbot, mode, name, *args) -> int:
    p = _client(mode, name, *args)
    qtbot.waitUntil(lambda: p.poll() is not None, timeout=10000)
    return p.returncode


@pytest.fixture
def qapp_core():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def server(qapp_core):
    name = f"IconReplacerTest-{uuid.uuid4().hex}"
    srv = ipc.SingleInstanceServer()
    assert srv.listen(name)
    got: list = []
    srv.folders_received.connect(got.append)
    srv.name = name
    srv.got = got
    yield srv
    srv.close()


def test_server_name_is_per_user_and_stable():
    assert ipc.server_name() == ipc.server_name()
    assert ipc.server_name().startswith("IconReplacer-")


def test_codec_roundtrip_and_validation(tmp_path):
    d = tmp_path / "a b"
    d.mkdir()
    f = tmp_path / "file.txt"
    f.write_text("x")
    msg = ipc.encode_message([d, f, "relative", str(tmp_path / "missing"), 5])
    assert ipc.decode_message(msg) == [d]


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\x00\x00",
        struct.pack(">I", 5) + b"[1,2",  # length mismatch
        struct.pack(">I", 4) + b"nope",  # not JSON
        struct.pack(">I", 2) + b"{}",  # not a list
        struct.pack(">I", ipc.MAX_MESSAGE_BYTES + 1) + b"x",  # oversized
    ],
)
def test_decode_rejects_malformed(data):
    assert ipc.decode_message(data) is None


def test_encode_rejects_oversized():
    with pytest.raises(ValueError):
        ipc.encode_message(["x" * (ipc.MAX_MESSAGE_BYTES + 1)])


def test_client_sends_folders_to_server(qtbot, server, tmp_path):
    a, b = tmp_path / "A B", tmp_path / "B"
    a.mkdir()
    b.mkdir()
    assert _run(qtbot, "send", server.name, a, b) == 0
    qtbot.waitUntil(lambda: len(server.got) == 1, timeout=5000)
    assert server.got[0] == [a, b]


def test_send_fails_without_server(qapp_core):
    assert ipc.send_folders([], f"IconReplacerNone-{uuid.uuid4().hex}") is False


def test_malformed_and_oversized_messages_rejected(qtbot, server, tmp_path):
    good = tmp_path / "G"
    good.mkdir()
    bad = [
        b"\xff\xff\xff\xffgarbage",
        struct.pack(">I", 3) + b"[1]",
        struct.pack(">I", 2) + json.dumps({}).encode(),
        struct.pack(">I", ipc.MAX_MESSAGE_BYTES + 1) + b"x" * 100,
    ]
    for data in bad:
        _run(qtbot, "raw", server.name, data.hex())
    # A valid message afterwards still works and nothing earlier produced a signal.
    assert _run(qtbot, "send", server.name, good) == 0
    qtbot.waitUntil(lambda: len(server.got) >= 1, timeout=5000)
    assert server.got == [[good]]


def test_acquire_first_then_forward(qtbot, qapp_core, tmp_path):
    name = f"IconReplacerTest-{uuid.uuid4().hex}"
    d = tmp_path / "F"
    d.mkdir()
    first = ipc.acquire([d], name)
    assert first is not None and first.listening
    try:
        got: list = []
        first.folders_received.connect(got.append)
        # a second instance forwards and exits with code 0
        assert _run(qtbot, "acquire", name, d) == 0
        qtbot.waitUntil(lambda: len(got) == 1, timeout=5000)
    finally:
        first.close()


def test_acquire_starts_normally_when_unreachable(qapp_core):
    srv = ipc.acquire([], f"IconReplacerTest-{uuid.uuid4().hex}")
    assert srv is not None and srv.listening
    srv.close()


def test_startup_aggregation_merges_multi_select(qtbot, qapp_core, tmp_path):
    name = f"IconReplacerTest-{uuid.uuid4().hex}"
    dirs = []
    for n in "ABC":
        p = tmp_path / n
        p.mkdir()
        dirs.append(p)
    first = ipc.acquire([dirs[0]], name)
    assert first is not None
    siblings = [_client("send", name, dirs[1]), _client("send", name, dirs[2], dirs[0])]
    merged = ipc.collect_startup_folders(first, [dirs[0]], window_ms=3000)
    first.close()
    for s in siblings:
        s.wait(10)
    assert merged[0] == dirs[0]  # own folder first; sibling arrival order is not deterministic
    assert sorted(merged) == sorted(dirs)  # all three, de-duplicated


def test_collect_without_server_returns_initial(tmp_path):
    assert ipc.collect_startup_folders(None, [tmp_path, tmp_path]) == [tmp_path]
