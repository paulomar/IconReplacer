from __future__ import annotations

import struct

import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QImageReader

from converter_fixtures import SVG_COLOR, SVG_GLYPH, photo_like, shape_png, solid
from iconreplacer.converter import STANDARD_SIZES, build_ico, convert_to_ico
from iconreplacer.core.models import ICO_MAGIC


@pytest.fixture(autouse=True)
def _app(qapp):
    return qapp


def directory(ico: bytes):
    _, kind, count = struct.unpack_from("<HHH", ico, 0)
    assert kind == 1
    return [struct.unpack_from("<BBBBHHII", ico, 6 + 16 * i) for i in range(count)]


def read_frames(ico: bytes):
    buf = QBuffer()
    buf.setData(QByteArray(ico))
    buf.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buf, b"ico")
    frames = []
    for i in range(reader.imageCount()):
        assert reader.jumpToImage(i)
        img = reader.read()
        assert not img.isNull()
        frames.append(img)
    return frames


@pytest.mark.parametrize("data", [SVG_GLYPH, SVG_COLOR, shape_png(), photo_like()])
def test_round_trip_every_size(data):
    res = convert_to_ico(data)
    assert res.ico.startswith(ICO_MAGIC)
    assert res.sizes == STANDARD_SIZES
    frames = read_frames(res.ico)
    assert sorted(f.width() for f in frames) == list(STANDARD_SIZES)
    assert all(f.width() == f.height() for f in frames)


def test_directory_structure_and_encodings():
    ico = convert_to_ico(SVG_GLYPH).ico
    entries = directory(ico)
    assert [(e[0] or 256) for e in entries] == list(STANDARD_SIZES)
    end = len(ico)
    prev_end = 6 + 16 * len(entries)
    for width, height, _, _, planes, bpp, nbytes, off in entries:
        assert (planes, bpp) == (1, 32) and width == height
        assert off == prev_end  # contiguous, correct offsets
        prev_end = off + nbytes
        blob = ico[off : off + nbytes]
        if width == 0:  # 256
            assert blob.startswith(b"\x89PNG\r\n\x1a\n")
        else:
            hdr = struct.unpack_from("<IiiHHI", blob, 0)
            assert hdr[0] == 40 and hdr[1] == width and hdr[2] == 2 * width
            assert hdr[4] == 32 and hdr[5] == 0
            stride = ((width + 31) // 32) * 4
            assert nbytes == 40 + width * width * 4 + stride * width
    assert prev_end == end


def test_and_mask_marks_transparent_pixels():
    ico = build_ico({16: solid(16, "red")})
    (_, _, _, _, _, _, nbytes, off) = directory(ico)[0]
    mask = ico[off + 40 + 16 * 16 * 4 : off + nbytes]
    # bottom-up: last image row is first mask row; corner pixel (0,0) is transparent
    assert mask[0] & 0x80 == 0x80  # row 15, x=0 transparent
    assert len(mask) == 4 * 16
    # the disc centre (x=8) of the middle row is opaque
    assert mask[8 * 4 + 1] & 0x80 == 0


def test_build_ico_sorts_and_validates():
    ico = build_ico({48: solid(48, "blue"), 16: solid(16, "red")})
    assert [(e[0]) for e in directory(ico)] == [16, 48]
    with pytest.raises(ValueError):
        build_ico({})
    with pytest.raises(ValueError):
        build_ico({32: solid(16, "red")})
    with pytest.raises(ValueError):
        build_ico({512: solid(512, "red")})


def test_compose_differs_from_plain_and_has_folder_colour():
    plain = convert_to_ico(SVG_GLYPH, compose_on_folder=False)
    composed = convert_to_ico(SVG_GLYPH, compose_on_folder=True, tint="#F2C14E")
    assert plain.ico != composed.ico
    assert plain.is_glyph and composed.is_glyph
    big = max(read_frames(composed.ico), key=lambda f: f.width())
    folder = QColor("#F2C14E")
    near = [
        big.pixelColor(x, y)
        for x in range(0, 256, 8)
        for y in range(0, 256, 8)
        if big.pixelColor(x, y).alpha() == 255
    ]
    assert any(
        abs(c.red() - folder.red()) < 40 and abs(c.green() - folder.green()) < 40 for c in near
    )
    assert all(f.width() in STANDARD_SIZES for f in read_frames(composed.ico))


def test_compose_full_colour_keeps_colours_and_warns():
    res = convert_to_ico(SVG_COLOR, compose_on_folder=True)
    assert not res.is_glyph and res.warnings
    big = max(read_frames(res.ico), key=lambda f: f.width())
    blue = QColor("#1e88e5")
    assert any(
        abs(big.pixelColor(x, 128).blue() - blue.blue()) < 25
        and abs(big.pixelColor(x, 128).red() - blue.red()) < 25
        for x in range(256)
    )
