"""Smart adaptation of a loaded image for Windows icon sizes.

Trims transparent margins, centres content in a square with a small inner padding,
detects glyph-like (monochrome) artwork and renders each target size either from the
vector source or with high-quality step-down downscaling of the raster.
"""

from __future__ import annotations

import math
from collections import Counter

from PySide6.QtCore import QByteArray, QRect, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from iconreplacer.converter.loader import ConversionError, SourceImage, viewbox

PADDING = 0.06  # inner padding on each side, as a fraction of the icon size
SHARPEN_MAX_SIZE = 32  # sharpen lightly only at small sizes
ALPHA_THRESHOLD = 8
_REF_SIZE = 512  # vector reference render used to measure the content box
_SAMPLE = 64  # max edge of the image used for glyph analysis


def _argb(image: QImage) -> QImage:
    return image.convertToFormat(QImage.Format.Format_ARGB32)


def _blank(width: int, height: int | None = None) -> QImage:
    img = QImage(width, height or width, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    return img


def content_bbox(image: QImage, threshold: int = ALPHA_THRESHOLD) -> QRect | None:
    """Bounding box of pixels with alpha above ``threshold``; ``None`` if there are none."""
    img = _argb(image)
    w, h = img.width(), img.height()
    alpha = bytes(img.constBits())[3::4]
    rows = [y for y in range(h) if max(alpha[y * w : (y + 1) * w], default=0) > threshold]
    if not rows:
        return None
    cols = [x for x in range(w) if max(alpha[x::w], default=0) > threshold]
    return QRect(cols[0], rows[0], cols[-1] - cols[0] + 1, rows[-1] - rows[0] + 1)


def detect_glyph(image: QImage) -> bool:
    """True for alpha-only shapes / images with very low colour variance."""
    img = _argb(image)
    if max(img.width(), img.height()) > _SAMPLE:
        img = img.scaled(
            _SAMPLE,
            _SAMPLE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
    data = bytes(img.constBits())
    total = img.width() * img.height()
    colors: list[tuple[int, int, int]] = []
    for i in range(0, total * 4, 4):
        if data[i + 3] >= 128:
            colors.append((data[i + 2], data[i + 1], data[i]))
    if not colors:
        return False
    if 1.0 - len(colors) / total < 0.02:
        return False  # fully opaque picture: a rectangle, not a shape
    n = len(colors)
    var = 0.0
    for ch in range(3):
        mean = sum(c[ch] for c in colors) / n
        var += sum((c[ch] - mean) ** 2 for c in colors) / n
    if math.sqrt(var) < 24:
        return True
    quant = Counter((r >> 5, g >> 5, b >> 5) for r, g, b in colors)
    return sum(c for _, c in quant.most_common(2)) / n >= 0.97


def _resize(image: QImage, tw: int, th: int) -> QImage:
    """Step-down halving followed by a final smooth scale (high quality downscale)."""
    img = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    smooth = Qt.TransformationMode.SmoothTransformation
    ignore = Qt.AspectRatioMode.IgnoreAspectRatio
    while img.width() >= 2 * tw and img.height() >= 2 * th:
        img = img.scaled(img.width() // 2, img.height() // 2, ignore, smooth)
    return img.scaled(tw, th, ignore, smooth)


def sharpen(image: QImage, amount: float = 0.25) -> QImage:
    """Light alpha-weighted unsharp mask on RGB (alpha untouched)."""
    img = _argb(image)
    w, h = img.width(), img.height()
    src = bytes(img.constBits())
    out = bytearray(src)
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 4
            if src[i + 3] == 0:
                continue
            acc = [0.0, 0.0, 0.0]
            weight = 0.0
            for yy in range(max(0, y - 1), min(h, y + 2)):
                for xx in range(max(0, x - 1), min(w, x + 2)):
                    j = (yy * w + xx) * 4
                    a = src[j + 3]
                    weight += a
                    for c in range(3):
                        acc[c] += src[j + c] * a
            for c in range(3):
                blur = acc[c] / weight
                out[i + c] = max(0, min(255, round(src[i + c] + amount * (src[i + c] - blur))))
    return QImage(bytes(out), w, h, w * 4, QImage.Format.Format_ARGB32).copy()


class Adapter:
    """Renders a :class:`SourceImage` at any icon size, adapted for Windows."""

    def __init__(self, source: SourceImage) -> None:
        self.source = source
        self.warnings: list[str] = []
        self._renderer: QSvgRenderer | None = None
        self._cropped: QImage | None = None
        if source.is_vector:
            self._init_vector()
        else:
            self._init_raster()
        self.is_glyph = detect_glyph(self._sample)

    # -- setup

    def _init_raster(self) -> None:
        assert self.source.raster is not None
        bbox = content_bbox(self.source.raster)
        if bbox is None:
            raise ConversionError("image has no visible content")
        self._cropped = self.source.raster.copy(bbox)
        self._sample = self._cropped
        if max(bbox.width(), bbox.height()) < 128:
            self.warnings.append(
                f"low resolution source ({bbox.width()}x{bbox.height()}); large sizes are upscaled"
            )

    def _init_vector(self) -> None:
        assert self.source.svg is not None
        self._renderer = QSvgRenderer(QByteArray(self.source.svg))
        vb = viewbox(self._renderer)
        self._vb = vb
        r = _REF_SIZE / max(vb.width(), vb.height())
        ref = _blank(max(1, round(vb.width() * r)), max(1, round(vb.height() * r)))
        p = QPainter(ref)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._renderer.render(p, QRectF(0, 0, ref.width(), ref.height()))
        p.end()
        bbox = content_bbox(ref)
        if bbox is None:
            raise ConversionError("image has no visible content")
        kx, ky = ref.width() / vb.width(), ref.height() / vb.height()
        # content rectangle in SVG units, relative to the viewBox origin
        self._content = QRectF(bbox.x() / kx, bbox.y() / ky, bbox.width() / kx, bbox.height() / ky)
        self._sample = ref.copy(bbox)

    # -- rendering

    @property
    def is_vector(self) -> bool:
        return self._renderer is not None

    def render(self, size: int, padding: float = PADDING) -> QImage:
        """Square ARGB32 (premultiplied) image of ``size`` px, content centred and padded."""
        inner = max(1.0, size * (1.0 - 2.0 * padding))
        canvas = _blank(size)
        if self._renderer is not None:
            self._paint_vector(canvas, size, inner)
        else:
            self._paint_raster(canvas, size, inner)
        return canvas

    def _paint_vector(self, canvas: QImage, size: int, inner: float) -> None:
        assert self._renderer is not None
        c = self._content
        k = min(inner / c.width(), inner / c.height())
        bounds = QRectF(
            size / 2 - (c.x() + c.width() / 2) * k,
            size / 2 - (c.y() + c.height() / 2) * k,
            self._vb.width() * k,
            self._vb.height() * k,
        )
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._renderer.render(p, bounds)
        p.end()
        if size <= SHARPEN_MAX_SIZE:
            self._copy_into(canvas, sharpen(canvas, 0.15))

    def _paint_raster(self, canvas: QImage, size: int, inner: float) -> None:
        assert self._cropped is not None
        cw, ch = self._cropped.width(), self._cropped.height()
        k = min(inner / cw, inner / ch)
        tw, th = max(1, round(cw * k)), max(1, round(ch * k))
        scaled = _resize(self._cropped, tw, th)
        if size <= SHARPEN_MAX_SIZE:
            scaled = sharpen(scaled)
        p = QPainter(canvas)
        p.drawImage((size - tw) // 2, (size - th) // 2, scaled)
        p.end()

    @staticmethod
    def _copy_into(dst: QImage, src: QImage) -> None:
        dst.fill(Qt.GlobalColor.transparent)
        p = QPainter(dst)
        p.drawImage(0, 0, src)
        p.end()
