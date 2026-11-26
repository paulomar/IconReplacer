from __future__ import annotations

import base64

import pytest

from converter_fixtures import (
    SVG_GLYPH,
    encode,
    icns_with_png,
    photo_like,
    png_with_declared_size,
    shape_png,
    solid,
)
from iconreplacer.converter import ConversionError, build_ico, load_image


@pytest.fixture(autouse=True)
def _app(qapp):
    return qapp


def test_png_detected_by_content_not_hint():
    src = load_image(shape_png(), "photo.svg")
    assert src.format == "png" and not src.is_vector
    assert (src.width, src.height) == (400, 400)


@pytest.mark.parametrize("fmt", ["JPEG", "BMP", "WEBP"])
def test_other_rasters(fmt):
    src = load_image(photo_like(64, fmt), "x.png")
    assert src.format == fmt.lower()
    assert src.raster is not None and src.raster.width() == 64


def test_svg_detected_and_vector():
    src = load_image(SVG_GLYPH, "x.png")
    assert src.is_vector and src.format == "svg"
    assert (src.width, src.height) == (100, 100)


def test_ico_uses_largest_frame():
    ico = build_ico({16: solid(16, "red"), 48: solid(48, "blue"), 32: solid(32, "green")})
    src = load_image(ico)
    assert src.format == "ico"
    assert src.raster is not None and src.raster.width() == 48


def test_icns_largest_frame():
    png = encode(solid(128, "purple"), "PNG")
    src = load_image(icns_with_png(png))
    assert src.format == "icns"
    assert src.raster is not None and src.raster.width() == 128


def test_garbage_and_empty_rejected():
    with pytest.raises(ConversionError):
        load_image(b"\x01\x02random bytes that are not an image" * 4)
    with pytest.raises(ConversionError):
        load_image(b"")


def test_truncated_png_rejected():
    with pytest.raises(ConversionError):
        load_image(shape_png()[:40])


def _svg(body: str, extra: str = "") -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 10 10" {extra}>{body}</svg>'
    ).encode()


@pytest.mark.parametrize(
    "data",
    [
        b'<!DOCTYPE svg [<!ENTITY a "b">]><svg xmlns="http://www.w3.org/2000/svg"/>',
        b'<!ENTITY x SYSTEM "file:///c:/windows/win.ini">',
        _svg("<script>alert(1)</script>"),
        _svg("<foreignObject><div/></foreignObject>"),
        _svg('<rect width="5" height="5" onload="evil()"/>'),
        _svg('<image href="http://example.com/a.png" width="5" height="5"/>'),
        _svg('<image xlink:href="file:///c:/secret.png" width="5" height="5"/>'),
        _svg('<image href="data:image/svg+xml;base64,PHN2Zy8+" width="5" height="5"/>'),
        _svg('<rect style="fill:url(http://evil/x)" width="5" height="5"/>'),
        b"<svg" + b" " * (2 * 1024 * 1024) + b' xmlns="http://www.w3.org/2000/svg"/>',
    ],
    ids=[
        "doctype",
        "entity",
        "script",
        "foreignobject",
        "event-handler",
        "http-href",
        "file-xlink-href",
        "svg-data-uri",
        "css-url",
        "oversize",
    ],
)
def test_malicious_svg_rejected(data):
    with pytest.raises(ConversionError):
        load_image(data)


def test_safe_svg_references_allowed():
    png = base64.b64encode(encode(solid(8, "red"), "PNG")).decode()
    data = _svg(
        '<defs><linearGradient id="g"><stop offset="0" stop-color="#000"/></linearGradient>'
        '<rect id="r" width="4" height="4"/></defs>'
        '<use href="#r" fill="url(#g)"/>'
        f'<image href="data:image/png;base64,{png}" x="5" y="5" width="4" height="4"/>'
    )
    assert load_image(data).is_vector


def test_decompression_bomb_rejected_before_decoding():
    with pytest.raises(ConversionError, match="exceed"):
        load_image(png_with_declared_size(10000, 10000))
    with pytest.raises(ConversionError, match="exceed"):
        load_image(png_with_declared_size(4097, 16))


def test_large_raster_data_rejected():
    with pytest.raises(ConversionError, match="larger"):
        load_image(b"\x89PNG\r\n\x1a\n" + b"\0" * (20 * 1024 * 1024 + 1))
