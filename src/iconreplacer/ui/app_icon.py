"""The original IconReplacer application icon (folder + sparkles), drawn with QPainter.

Single source of the design: used for the window icon and by packaging/make_app_icon.py.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

ICON_SIZES: tuple[int, ...] = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def _sparkle(cx: float, cy: float, r: float) -> QPainterPath:
    """Four-pointed star with concave sides."""
    path = QPainterPath()
    path.moveTo(cx, cy - r)
    path.quadTo(cx, cy, cx + r, cy)
    path.quadTo(cx, cy, cx, cy + r)
    path.quadTo(cx, cy, cx - r, cy)
    path.quadTo(cx, cy, cx, cy - r)
    return path


def render(size: int) -> QImage:
    """Render the icon at ``size`` x ``size`` pixels (designed on a 256 grid)."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 256.0, size / 256.0)

    # Folder back with tab.
    back = QPainterPath()
    back.moveTo(24, 70)
    back.lineTo(24, 58)
    back.quadTo(24, 44, 38, 44)
    back.lineTo(92, 44)
    back.quadTo(100, 44, 106, 52)
    back.lineTo(116, 66)
    back.lineTo(214, 66)
    back.quadTo(232, 66, 232, 84)
    back.lineTo(232, 110)
    back.lineTo(24, 110)
    back.closeSubpath()
    back_grad = QLinearGradient(0, 44, 0, 120)
    back_grad.setColorAt(0, QColor("#1D6FD6"))
    back_grad.setColorAt(1, QColor("#1555A8"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(back_grad)
    p.drawPath(back)

    # Folder front panel.
    front = QRectF(20, 88, 216, 138)
    grad = QLinearGradient(0, front.top(), 0, front.bottom())
    grad.setColorAt(0, QColor("#4FA3FF"))
    grad.setColorAt(1, QColor("#2A7DE1"))
    p.setBrush(grad)
    p.drawRoundedRect(front, 18, 18)
    p.setBrush(QColor(255, 255, 255, 45))
    p.drawRoundedRect(QRectF(20, 88, 216, 22), 18, 18)

    # Sparkles (the "replace icon" motif).
    p.setBrush(QColor("#FFD43B"))
    p.setPen(
        QPen(
            QColor("#E8A800"),
            3,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    p.drawPath(_sparkle(138, 156, 54))
    p.setBrush(QColor("#FFFFFF"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPath(_sparkle(196, 112, 22))
    p.drawPath(_sparkle(82, 190, 16))
    p.end()
    return image


def app_icon() -> QIcon:
    """Multi-resolution QIcon for windows and the taskbar."""
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(render(size)))
    return icon
