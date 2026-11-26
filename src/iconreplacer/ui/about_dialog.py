"""About dialog: product, version/build, license and third-party notices."""

from __future__ import annotations

import platform

import PySide6
from PySide6.QtCore import Qt, qVersion
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout

from iconreplacer import version

THIRD_PARTY: tuple[tuple[str, str, str], ...] = (
    ("PySide6 / Qt for Python", PySide6.__version__, "LGPL-3.0"),
    ("Qt", qVersion(), "LGPL-3.0"),
    ("Python", platform.python_version(), "PSF License"),
)


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("About IconReplacer"))
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        name = QLabel(version.PRODUCT_NAME)
        name.setObjectName("h2")
        f = name.font()
        f.setPointSizeF(f.pointSizeF() + 6)
        name.setFont(f)
        lay.addWidget(name)
        self.version_label = QLabel(
            self.tr("Version %1 (build %2)")
            .replace("%1", version.SHORT_VERSION)
            .replace("%2", str(version.BUILD))
        )
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.version_label)
        tagline = QLabel(self.tr("A modern folder icon picker for Windows Explorer."))
        tagline.setObjectName("muted")
        lay.addWidget(tagline)
        self.license_label = QLabel(self.tr("MIT License"))
        lay.addWidget(self.license_label)

        notices = QLabel(self.tr("Third-party components"))
        notices.setObjectName("h2")
        lay.addWidget(notices)
        self.notices = QTextBrowser()
        rows = "".join(
            f"<tr><td>{n}</td><td>{v}</td><td>{lic}</td></tr>" for n, v, lic in THIRD_PARTY
        )
        disclaimer = self.tr(
            "Windows system icons are referenced in place from your Windows installation "
            "and are not redistributed."
        )
        converter = self.tr(
            "The icon converter (SVG, PNG, JPEG, BMP, WebP, ICO and ICNS to ICO) is part of "
            "IconReplacer (MIT License) and uses only Qt."
        )
        system_data = self.tr(
            "The names, categories and tags of system icons are curated by IconReplacer "
            "(MIT License); the icon artwork stays in your Windows installation."
        )
        sources = self.tr("Third-party icon sources keep their own licenses.")
        paragraphs = "".join(f"<p>{t}</p>" for t in (disclaimer, converter, system_data, sources))
        self.notices.setHtml(f"<table cellpadding='3'>{rows}</table>{paragraphs}")
        self.notices.setMinimumHeight(190)
        lay.addWidget(self.notices)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def notices_text(self) -> str:
        return self.notices.toPlainText()
