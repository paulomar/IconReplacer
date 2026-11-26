"""Procedural vector symbols used by the mock catalog (prototype only)."""

from __future__ import annotations

import hashlib
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen

from iconreplacer.core.models import IconEntry, IconKind
from iconreplacer.ui.folder_base import draw_folder


def _hue(seed_text: str) -> int:
    return int.from_bytes(hashlib.blake2s(seed_text.encode(), digest_size=2).digest(), "big") % 360


def _symbol_path(category: str, r: QRectF) -> QPainterPath:
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx, cy = r.center().x(), r.center().y()
    p = QPainterPath()
    if category == "Drives & Storage":
        p.addRoundedRect(QRectF(x, y + h * 0.25, w, h * 0.5), w * 0.08, w * 0.08)
        p.addEllipse(QPointF(x + w * 0.8, cy), w * 0.05, w * 0.05)
        p.moveTo(x + w * 0.12, cy)
        p.lineTo(x + w * 0.55, cy)
    elif category == "Devices":
        p.addRoundedRect(QRectF(x, y + h * 0.1, w, h * 0.6), w * 0.05, w * 0.05)
        p.moveTo(cx, y + h * 0.7)
        p.lineTo(cx, y + h * 0.88)
        p.moveTo(x + w * 0.28, y + h * 0.9)
        p.lineTo(x + w * 0.72, y + h * 0.9)
    elif category == "Media":
        p.addEllipse(QRectF(x + w * 0.12, y + h * 0.6, w * 0.3, h * 0.3))
        p.moveTo(x + w * 0.42, y + h * 0.75)
        p.lineTo(x + w * 0.42, y + h * 0.1)
        p.lineTo(x + w * 0.85, y + h * 0.22)
        p.lineTo(x + w * 0.85, y + h * 0.4)
        p.lineTo(x + w * 0.42, y + h * 0.3)
    elif category in ("Network", "Web"):
        p.addEllipse(r)
        p.addEllipse(QRectF(cx - w * 0.2, y, w * 0.4, h))
        p.moveTo(x, cy)
        p.lineTo(x + w, cy)
        if category == "Web":
            p.moveTo(x + w * 0.1, y + h * 0.28)
            p.lineTo(x + w * 0.9, y + h * 0.28)
    elif category == "Security":
        p.moveTo(cx, y)
        p.lineTo(x + w * 0.92, y + h * 0.16)
        p.quadTo(QPointF(x + w * 0.92, y + h * 0.78), QPointF(cx, y + h))
        p.quadTo(QPointF(x + w * 0.08, y + h * 0.78), QPointF(x + w * 0.08, y + h * 0.16))
        p.closeSubpath()
        p.moveTo(x + w * 0.32, cy)
        p.lineTo(x + w * 0.46, y + h * 0.64)
        p.lineTo(x + w * 0.7, y + h * 0.36)
    elif category == "System":
        teeth = 8
        for i in range(teeth * 2):
            a = math.pi * i / teeth
            rad = (w * 0.5) if i % 2 == 0 else (w * 0.38)
            pt = QPointF(cx + rad * math.cos(a), cy + rad * math.sin(a))
            p.moveTo(pt) if i == 0 else p.lineTo(pt)
        p.closeSubpath()
        p.addEllipse(QPointF(cx, cy), w * 0.15, w * 0.15)
    elif category in ("Users", "Accessibility"):
        p.addEllipse(QPointF(cx, y + h * 0.27), w * 0.2, w * 0.2)
        p.moveTo(x + w * 0.1, y + h)
        p.quadTo(QPointF(x + w * 0.1, y + h * 0.52), QPointF(cx, y + h * 0.52))
        p.quadTo(QPointF(x + w * 0.9, y + h * 0.52), QPointF(x + w * 0.9, y + h))
        if category == "Accessibility":
            p.moveTo(x, y + h * 0.62)
            p.lineTo(x + w, y + h * 0.62)
    elif category == "Power":
        p.addRoundedRect(QRectF(x, y + h * 0.28, w * 0.88, h * 0.44), w * 0.06, w * 0.06)
        p.addRect(QRectF(x + w * 0.88, y + h * 0.4, w * 0.12, h * 0.2))
        p.moveTo(x + w * 0.5, y + h * 0.32)
        p.lineTo(x + w * 0.36, cy)
        p.lineTo(x + w * 0.52, cy)
        p.lineTo(x + w * 0.38, y + h * 0.68)
    elif category == "Documents":
        p.moveTo(x + w * 0.15, y)
        p.lineTo(x + w * 0.62, y)
        p.lineTo(x + w * 0.85, y + h * 0.24)
        p.lineTo(x + w * 0.85, y + h)
        p.lineTo(x + w * 0.15, y + h)
        p.closeSubpath()
        for k in (0.45, 0.6, 0.75):
            p.moveTo(x + w * 0.3, y + h * k)
            p.lineTo(x + w * 0.7, y + h * k)
    elif category == "Legacy":
        p.addRoundedRect(r, w * 0.06, w * 0.06)
        p.addRect(QRectF(x + w * 0.25, y, w * 0.5, h * 0.32))
        p.addRect(QRectF(x + w * 0.18, y + h * 0.55, w * 0.64, h * 0.45))
    else:  # Folders and fallback
        p.moveTo(x, y + h * 0.15)
        p.lineTo(x + w * 0.38, y + h * 0.15)
        p.lineTo(x + w * 0.48, y + h * 0.27)
        p.lineTo(x + w, y + h * 0.27)
        p.lineTo(x + w, y + h * 0.88)
        p.lineTo(x, y + h * 0.88)
        p.closeSubpath()
    return p


def _primary_category(entry: IconEntry) -> str:
    return sorted(entry.categories)[0] if entry.categories else "Folders"


def render_glyph(category: str, size: int, color: QColor) -> QImage:
    """Monochrome line glyph on transparent background."""
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    m = size * 0.14
    pen = QPen(color, max(1.0, size * 0.07))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(_symbol_path(category, QRectF(m, m, size - 2 * m, size - 2 * m)))
    p.end()
    return img


def render_mock_glyph(entry: IconEntry, size: int) -> QImage:
    category = _primary_category(entry)
    if entry.kind is IconKind.GLYPH:
        return render_glyph(category, size, QColor("#000000"))  # UI recolors per theme
    hue = _hue(entry.id)
    base = QColor.fromHsv(hue, 150, 225)
    if category == "Folders":
        img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_folder(p, size, base)
        p.end()
        return img
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    m = size * 0.08
    tile = QRectF(m, m, size - 2 * m, size - 2 * m)
    grad = QLinearGradient(tile.topLeft(), tile.bottomRight())
    grad.setColorAt(0, base.lighter(115))
    grad.setColorAt(1, base.darker(130))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(tile, size * 0.18, size * 0.18)
    p.drawImage(0, 0, render_glyph(category, size, QColor(255, 255, 255, 235)))
    p.end()
    return img
