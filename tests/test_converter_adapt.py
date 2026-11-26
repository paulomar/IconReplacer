from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QPainter

from converter_fixtures import (
    SVG_COLOR,
    SVG_GLYPH,
    canvas,
    colour_icon_png,
    encode,
    glyph_png,
    photo_like,
    shape_png,
)
from iconreplacer.converter import Adapter, ConversionError, content_bbox, load_image


@pytest.fixture(autouse=True)
def _app(qapp):
    return qapp


def test_margins_trimmed_and_padded_square():
    a = Adapter(load_image(shape_png()))
    img = a.render(128)
    assert (img.width(), img.height()) == (128, 128)
    bbox = content_bbox(img)
    assert bbox is not None
    # content fills the inner box (~88%) and is centred
    assert 0.80 * 128 <= bbox.width() <= 0.92 * 128
    assert abs(bbox.center().x() - 64) <= 2 and abs(bbox.center().y() - 64) <= 2


def test_non_square_keeps_aspect_ratio():
    img = canvas(100, 50)
    p = QPainter(img)
    p.fillRect(0, 0, 100, 50, QColor("black"))
    p.end()
    out = Adapter(load_image(encode(img, "PNG"))).render(64)
    bbox = content_bbox(out)
    assert out.width() == out.height() == 64
    assert bbox is not None and abs(bbox.width() / bbox.height() - 2.0) < 0.15
    assert bbox.height() < bbox.width()


def test_vector_trimmed_and_rendered_per_size():
    a = Adapter(load_image(SVG_GLYPH))
    assert a.is_vector
    for size in (16, 48, 256):
        bbox = content_bbox(a.render(size))
        assert bbox is not None
        assert bbox.width() >= 0.85 * size * 0.88  # circle trimmed to fill inner box
        assert abs(bbox.center().x() - size / 2) <= 1.5


def test_currentcolor_renders_black():
    img = Adapter(load_image(SVG_GLYPH)).render(64)
    c = img.pixelColor(32, 32)
    assert (c.red(), c.green(), c.blue(), c.alpha()) == (0, 0, 0, 255)


def test_glyph_detection():
    assert Adapter(load_image(SVG_GLYPH)).is_glyph
    assert Adapter(load_image(glyph_png())).is_glyph
    # a fully opaque flat rectangle has no shape information: not a glyph
    assert not Adapter(load_image(shape_png())).is_glyph
    assert not Adapter(load_image(SVG_COLOR)).is_glyph
    assert not Adapter(load_image(photo_like())).is_glyph
    assert not Adapter(load_image(colour_icon_png())).is_glyph


def test_empty_image_rejected():
    with pytest.raises(ConversionError, match="no visible content"):
        Adapter(load_image(encode(canvas(32, 32), "PNG")))


def test_low_resolution_warns_and_small_sizes_nonempty():
    a = Adapter(load_image(shape_png(40, 40, (10, 10, 20, 20))))
    assert a.warnings
    for size in (16, 20, 24):
        assert content_bbox(a.render(size)) is not None
