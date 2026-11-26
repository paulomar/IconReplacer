"""Original Win11-*style* folder base drawn with QPainterPath (no Microsoft artwork).

Pure functions returning QImage, shared by the UI and the icon converter.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath

DEFAULT_TINT = "#F2C14E"
GLYPH_SCALE = 0.55


def _blank(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    return img


def front_panel_rect(size: int) -> QRectF:
    s = float(size)
    return QRectF(s * 0.06, s * 0.30, s * 0.88, s * 0.58)


def draw_folder(painter: QPainter, size: int, tint: QColor) -> None:
    s = float(size)
    r = max(1.0, s * 0.06)
    back = QColor(tint).darker(125)
    # back panel with tab
    path = QPainterPath()
    path.moveTo(s * 0.06 + r, s * 0.16)
    path.lineTo(s * 0.38, s * 0.16)
    path.lineTo(s * 0.46, s * 0.24)
    path.lineTo(s * 0.94 - r, s * 0.24)
    path.quadTo(QPointF(s * 0.94, s * 0.24), QPointF(s * 0.94, s * 0.24 + r))
    path.lineTo(s * 0.94, s * 0.80)
    path.lineTo(s * 0.06, s * 0.80)
    path.lineTo(s * 0.06, s * 0.16 + r)
    path.quadTo(QPointF(s * 0.06, s * 0.16), QPointF(s * 0.06 + r, s * 0.16))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(back)
    painter.drawPath(path)
    # front panel with gradient
    front = front_panel_rect(size)
    grad = QLinearGradient(front.topLeft(), front.bottomLeft())
    grad.setColorAt(0.0, QColor(tint).lighter(118))
    grad.setColorAt(1.0, QColor(tint))
    painter.setBrush(grad)
    painter.drawRoundedRect(front, r, r)
    # subtle top highlight
    if size >= 24:
        hl = QColor(255, 255, 255, 70)
        painter.setBrush(hl)
        painter.drawRect(
            QRectF(front.left() + r, front.top(), front.width() - 2 * r, max(1.0, s * 0.015))
        )


def recolor(image: QImage, color: QColor) -> QImage:
    """Return a copy of ``image`` with every opaque pixel painted ``color`` (alpha kept)."""
    out = _blank(image.width())
    p = QPainter(out)
    p.drawImage(0, 0, image)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(out.rect(), QColor(color))
    p.end()
    return out


def compose_on_folder(glyph: QImage, size: int, tint: str | QColor = DEFAULT_TINT) -> QImage:
    """Draw ``glyph`` centered on the front panel of a tinted folder of ``size`` px."""
    color = QColor(tint)
    img = _blank(size)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    draw_folder(p, size, color)
    front = front_panel_rect(size)
    g = max(1, round(size * GLYPH_SCALE * 0.72))
    target = QRectF(front.center().x() - g / 2, front.center().y() - g / 2, g, g)
    # recolor glyph to a contrasting tone so it reads at small sizes
    ink = QColor(color).darker(260) if color.lightness() > 110 else QColor(255, 255, 255)
    p.drawImage(target, recolor(glyph, ink))
    p.end()
    return img
