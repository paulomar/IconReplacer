"""Light/dark theming: Fusion + palettes + a small QSS, following the system by default."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication


class ThemeMode(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


ACCENT = "#3D8BFD"

_DARK = {
    "window": "#17191C",
    "base": "#1E2125",
    "alt": "#24282D",
    "panel": "#202327",
    "text": "#E4E7EB",
    "muted": "#8B939E",
    "border": "#2F343A",
    "button": "#262A30",
    "hover": "#2C3138",
}
_LIGHT = {
    "window": "#F3F4F6",
    "base": "#FFFFFF",
    "alt": "#F7F8FA",
    "panel": "#FAFBFC",
    "text": "#1C1F23",
    "muted": "#5F6873",
    "border": "#D9DDE2",
    "button": "#FFFFFF",
    "hover": "#EDF1F6",
}


def monospace_font(point_size: int | None = None) -> QFont:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    for family in ("Cascadia Mono", "Consolas"):
        if family in QFontDatabase.families():
            font = QFont(family)
            break
    if point_size:
        font.setPointSize(point_size)
    return font


def _palette(c: dict[str, str]) -> QPalette:
    p = QPalette()
    R = QPalette.ColorRole
    p.setColor(R.Window, QColor(c["window"]))
    p.setColor(R.WindowText, QColor(c["text"]))
    p.setColor(R.Base, QColor(c["base"]))
    p.setColor(R.AlternateBase, QColor(c["alt"]))
    p.setColor(R.Text, QColor(c["text"]))
    p.setColor(R.Button, QColor(c["button"]))
    p.setColor(R.ButtonText, QColor(c["text"]))
    p.setColor(R.ToolTipBase, QColor(c["panel"]))
    p.setColor(R.ToolTipText, QColor(c["text"]))
    p.setColor(R.PlaceholderText, QColor(c["muted"]))
    p.setColor(R.Highlight, QColor(ACCENT))
    p.setColor(R.HighlightedText, QColor("#FFFFFF"))
    p.setColor(R.Link, QColor(ACCENT))
    p.setColor(R.Mid, QColor(c["border"]))
    for role in (R.Text, R.WindowText, R.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["muted"]))
    return p


def _qss(c: dict[str, str]) -> str:
    return f"""
    QWidget {{ font-size: 9.5pt; }}
    QSplitter::handle {{ background: {c["border"]}; }}
    QTreeView, QListView, QLineEdit, QComboBox, QTextBrowser {{
        border: 1px solid {c["border"]}; border-radius: 4px; background: {c["base"]};
    }}
    QLineEdit {{ padding: 5px 8px; }}
    QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
    QTreeView::item {{ padding: 3px 2px; }}
    QTreeView::item:hover, QListView::item:hover {{ background: {c["hover"]}; }}
    QPushButton {{
        padding: 6px 14px; border: 1px solid {c["border"]}; border-radius: 4px;
        background: {c["button"]};
    }}
    QPushButton:hover {{ background: {c["hover"]}; }}
    QPushButton:disabled {{ color: {c["muted"]}; }}
    QPushButton#primary {{ background: {ACCENT}; color: white; border-color: {ACCENT}; }}
    QPushButton#primary:disabled {{ background: {c["border"]}; color: {c["muted"]}; }}
    QToolButton#chip {{
        padding: 3px 10px; border: 1px solid {c["border"]}; border-radius: 11px;
    }}
    QToolButton#chip:checked {{ background: {ACCENT}; color: white; border-color: {ACCENT}; }}
    QFrame#panel {{ background: {c["panel"]}; border: 1px solid {c["border"]}; border-radius: 6px; }}
    QFrame#banner {{ background: {c["alt"]}; border-left: 3px solid {ACCENT}; border-radius: 3px; }}
    QLabel#muted {{ color: {c["muted"]}; }}
    QLabel#h2 {{ font-size: 11pt; font-weight: 600; }}
    QLabel#mono {{ color: {c["muted"]}; }}
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{ padding: 7px 16px; border: none; border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ border-bottom-color: {ACCENT}; font-weight: 600; }}
    QGroupBox {{ border: 1px solid {c["border"]}; border-radius: 6px; margin-top: 14px; padding: 10px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
    """


class ThemeManager(QObject):
    """Applies light/dark appearance; in SYSTEM mode follows Windows at runtime."""

    changed = Signal(bool)  # is_dark

    def __init__(self, app: QApplication, mode: ThemeMode = ThemeMode.SYSTEM) -> None:
        super().__init__(app)
        self._app = app
        self._mode = mode
        app.setStyle("Fusion")
        app.styleHints().colorSchemeChanged.connect(self._on_system_changed)
        self.apply(mode)

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @staticmethod
    def system_is_dark() -> bool:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def is_dark(self) -> bool:
        if self._mode is ThemeMode.SYSTEM:
            return self.system_is_dark()
        return self._mode is ThemeMode.DARK

    def apply(self, mode: ThemeMode) -> None:
        self._mode = ThemeMode(mode)
        colors = _DARK if self.is_dark() else _LIGHT
        self._app.setPalette(_palette(colors))
        self._app.setStyleSheet(_qss(colors))
        self.changed.emit(self.is_dark())

    def _on_system_changed(self, _scheme) -> None:
        if self._mode is ThemeMode.SYSTEM:
            self.apply(ThemeMode.SYSTEM)
