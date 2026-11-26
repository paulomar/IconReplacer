"""Image fixtures generated in code for the converter tests."""

from __future__ import annotations

import struct
import zlib

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter

SVG_GLYPH = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    b'<circle cx="50" cy="50" r="30" fill="currentColor"/></svg>'
)

SVG_COLOR = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    b'<rect x="10" y="10" width="40" height="80" fill="#e53935"/>'
    b'<rect x="50" y="10" width="40" height="80" fill="#1e88e5"/>'
    b'<circle cx="50" cy="50" r="20" fill="#43a047"/></svg>'
)


def encode(img: QImage, fmt: str) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    assert img.save(buf, fmt)
    buf.close()
    return bytes(ba.data())


def canvas(w: int, h: int, opaque: bool = False) -> QImage:
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("white") if opaque else Qt.GlobalColor.transparent)
    return img


def shape_png(canvas_w: int = 400, canvas_h: int = 400, box=(150, 150, 100, 100)) -> bytes:
    """A flat black rectangle on a larger transparent canvas."""
    img = canvas(canvas_w, canvas_h)
    p = QPainter(img)
    p.fillRect(*box, QColor("black"))
    p.end()
    return encode(img, "PNG")


def glyph_png() -> bytes:
    """A flat black disc on a larger transparent canvas."""
    img = canvas(400, 400)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("black"))
    p.drawEllipse(100, 150, 200, 100)
    p.end()
    return encode(img, "PNG")


def photo_like(size: int = 128, fmt: str = "PNG") -> bytes:
    """Opaque multi-colour gradient picture."""
    img = canvas(size, size, opaque=True)
    p = QPainter(img)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0.0, QColor("#ff3d00"))
    g.setColorAt(0.35, QColor("#ffee58"))
    g.setColorAt(0.7, QColor("#26c6da"))
    g.setColorAt(1.0, QColor("#5e35b1"))
    p.fillRect(0, 0, size, size, g)
    p.end()
    return encode(img, fmt)


def colour_icon_png(size: int = 256) -> bytes:
    """Transparent background with several flat colours."""
    img = canvas(size, size)
    p = QPainter(img)
    p.fillRect(0, 0, size // 2, size, QColor("#e53935"))
    p.fillRect(size // 2, 0, size // 2, size, QColor("#1e88e5"))
    p.end()
    return encode(img, "PNG")


def solid(size: int, color: str) -> QImage:
    img = canvas(size, size)
    p = QPainter(img)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return img


def png_with_declared_size(w: int, h: int) -> bytes:
    """A PNG whose header declares w x h pixels but carries almost no data."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        )

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00"))
        + chunk(b"IEND", b"")
    )


def icns_with_png(png: bytes, kind: bytes = b"ic07") -> bytes:
    """Minimal ICNS holding one PNG-compressed entry (ic07 = 128x128)."""
    entry = kind + struct.pack(">I", len(png) + 8) + png
    return b"icns" + struct.pack(">I", len(entry) + 8) + entry
