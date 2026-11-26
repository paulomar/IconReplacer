import struct
import sys
from pathlib import Path

import pytest

from iconreplacer.catalog import pe_icons
from iconreplacer.catalog.pe_icons import GroupImage, PeIconError, build_ico, parse_group
from iconreplacer.core.models import ICO_MAGIC

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="needs Windows system DLLs")


def _system32(name: str) -> Path:
    from iconreplacer.catalog.system_source import system_root

    return system_root() / "System32" / name


def test_parse_group_and_build_ico_roundtrip():
    grp = struct.pack("<HHH", 0, 1, 2)
    grp += struct.pack("<BBBBHHIH", 16, 16, 0, 0, 1, 32, 4, 7)
    grp += struct.pack("<BBBBHHIH", 0, 0, 0, 0, 1, 32, 8, 9)
    images = parse_group(grp)
    assert [(i.width, i.icon_id) for i in images] == [(16, 7), (256, 9)]

    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", 256, 256)
    ico = build_ico([(images[0], b"abcd"), (images[1], png)])
    assert ico.startswith(ICO_MAGIC)
    assert struct.unpack_from("<H", ico, 4)[0] == 2
    w, h, _c, _r, _p, _b, size, offset = struct.unpack_from("<BBBBHHII", ico, 6 + 16)
    assert (w, h) == (0, 0)  # 256 encoded as 0
    assert ico[offset : offset + size] == png


def test_parse_group_rejects_garbage():
    with pytest.raises(PeIconError):
        parse_group(b"\x00")
    with pytest.raises(PeIconError):
        parse_group(struct.pack("<HHH", 0, 2, 0))


@windows_only
@pytest.mark.parametrize("lib", ["imageres.dll", "shell32.dll"])
def test_enumerates_integer_group_ids(lib):
    with pe_icons.PeModule(str(_system32(lib))) as mod:
        ids, _skipped = mod.group_icon_ids()
        assert len(ids) > 300
        assert all(i > 0 for i in ids)
        assert len(ids) == len(set(ids))
        data = mod.ico_bytes(ids[0])
    assert data.startswith(ICO_MAGIC)


@windows_only
def test_ico_bytes_decode_with_qt(qapp):
    from PySide6.QtGui import QImage

    with pe_icons.PeModule(str(_system32("shell32.dll"))) as mod:
        data = mod.ico_bytes(4)
    img = QImage.fromData(data, "ICO")
    assert not img.isNull()


@windows_only
def test_closed_module_raises():
    mod = pe_icons.PeModule(str(_system32("imageres.dll")))
    mod.close()
    mod.close()  # idempotent
    assert mod.closed
    with pytest.raises(PeIconError):
        mod.resource(pe_icons.RT_GROUP_ICON, 3)


@windows_only
def test_missing_file_raises(tmp_path):
    with pytest.raises(OSError):
        pe_icons.PeModule(str(tmp_path / "missing.dll"))


def test_group_image_is_frozen():
    img = GroupImage(16, 16, 32, 10, 1)
    with pytest.raises(AttributeError):
        img.width = 32  # type: ignore[misc]
