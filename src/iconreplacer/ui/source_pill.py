"""Removable indicator for the active source while the sidebar is hidden."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton


class SourcePill(QFrame):
    dismissed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("pill")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 2, 4, 2)
        lay.setSpacing(4)
        self.label = QLabel()
        lay.addWidget(self.label)
        self.close_btn = QToolButton()
        self.close_btn.setText("✕")
        self.close_btn.setAutoRaise(True)
        self.close_btn.setToolTip(self.tr("Show all sources"))
        self.close_btn.clicked.connect(self.dismissed)
        lay.addWidget(self.close_btn)
        self.setVisible(False)

    def show_source(self, name: str) -> None:
        self.label.setText(self.tr("Source: %1").replace("%1", name))
        self.setVisible(True)
