"""Header showing the target folder(s) and the folder actions."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from iconreplacer.ui.theme import monospace_font


class TargetHeader(QFrame):
    apply_clicked = Signal()
    undo_clicked = Signal()
    restore_clicked = Signal()
    folders_changed = Signal()

    def __init__(self, folders: Sequence[Path] = (), parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self._folders: tuple[Path, ...] = ()
        self._has_selection = False
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        row = QHBoxLayout()
        caption = QLabel(self.tr("Target"))
        caption.setObjectName("muted")
        row.addWidget(caption)
        self.summary = QLabel()
        self.summary.setFont(monospace_font())
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.summary, 1)
        self.expand = QToolButton()
        self.expand.setCheckable(True)
        self.expand.setArrowType(Qt.ArrowType.DownArrow)
        self.expand.setToolTip(self.tr("Show all target folders"))
        self.expand.toggled.connect(self._toggle_list)
        row.addWidget(self.expand)
        self.choose_btn = QPushButton(self.tr("Choose folders…"))
        self.choose_btn.setToolTip(self.tr("Add a target folder (pick again to add more)"))
        self.choose_btn.clicked.connect(self.choose_folder)
        row.addWidget(self.choose_btn)
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)  # indeterminate
        self.busy_bar.setFixedWidth(90)
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setToolTip(self.tr("Working…"))
        self.busy_bar.setVisible(False)
        row.addWidget(self.busy_bar)

        self.restore_btn = QPushButton(self.tr("Restore default"))
        self.undo_btn = QPushButton(self.tr("Undo"))
        self.apply_btn = QPushButton(self.tr("Apply"))
        self.apply_btn.setObjectName("primary")
        self.apply_btn.setDefault(True)
        self.restore_btn.clicked.connect(self.restore_clicked)
        self.undo_btn.clicked.connect(self.undo_clicked)
        self.apply_btn.clicked.connect(self.apply_clicked)
        for b in (self.restore_btn, self.undo_btn, self.apply_btn):
            row.addWidget(b)
        root.addLayout(row)

        self.list = QListWidget()
        self.list.setFont(monospace_font())
        self.list.setMaximumHeight(110)
        self.list.setVisible(False)
        root.addWidget(self.list)
        self.set_folders(folders)

    @property
    def folders(self) -> tuple[Path, ...]:
        return self._folders

    def set_folders(self, folders: Sequence[Path]) -> None:
        self._folders = tuple(folders)
        self.list.clear()
        self.list.addItems([str(f) for f in self._folders])
        n = len(self._folders)
        if n == 0:
            self.summary.setText(self.tr("No target folder"))
        elif n == 1:
            self.summary.setText(str(self._folders[0]))
        else:
            self.summary.setText(self.tr("%n folders", "", n))
        self.expand.setVisible(n > 1)
        if n <= 1:
            self.expand.setChecked(False)
        self._update_buttons()
        self.folders_changed.emit()

    def add_folders(self, folders: Sequence[Path]) -> bool:
        """Append folders that are not targets yet (case-insensitive). True if any was added."""
        known = {str(p).lower() for p in self._folders}
        extra: list[Path] = []
        for f in folders:
            key = str(f).lower()
            if key not in known:
                known.add(key)
                extra.append(Path(f))
        if extra:
            self.set_folders([*self._folders, *extra])
        return bool(extra)

    def choose_folder(self) -> None:
        start = str(self._folders[-1].parent) if self._folders else ""
        path = QFileDialog.getExistingDirectory(self, self.tr("Choose a target folder"), start)
        if path:
            self.add_folders([Path(path)])

    @property
    def busy(self) -> bool:
        return self._busy

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.busy_bar.setVisible(busy)
        self._update_buttons()

    def set_has_selection(self, has: bool) -> None:
        self._has_selection = has
        self._update_buttons()

    def _update_buttons(self) -> None:
        idle = not self._busy
        has_target = bool(self._folders) and idle
        self.apply_btn.setEnabled(has_target and self._has_selection)
        self.undo_btn.setEnabled(has_target)
        self.restore_btn.setEnabled(has_target)
        self.choose_btn.setEnabled(idle)

    def _toggle_list(self, on: bool) -> None:
        self.list.setVisible(on)
        self.expand.setArrowType(Qt.ArrowType.UpArrow if on else Qt.ArrowType.DownArrow)
