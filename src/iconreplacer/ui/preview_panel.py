"""Preview of the selected icon at multiple sizes, metadata and composition options."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from iconreplacer.core.models import ApplyOptions, IconEntry, IconKind
from iconreplacer.ui.folder_base import DEFAULT_TINT, compose_on_folder
from iconreplacer.ui.strings import category_label
from iconreplacer.ui.theme import monospace_font

PREVIEW_SIZES: tuple[int, ...] = (16, 24, 32, 48, 64)
HERO_SIZE = PREVIEW_SIZES[-1]
ZWSP = chr(0x200B)  # zero-width space: allows line breaks inside long paths
TINT_PRESETS = ("#F2C14E", "#3D8BFD", "#34C38F", "#F46A6A", "#A66CFF", "#8B939E", "#2B2F36")

Renderer = Callable[[IconEntry, int], QImage]


class PreviewPanel(QFrame):
    options_changed = Signal(object)  # ApplyOptions

    def __init__(self, renderer: Renderer, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setMinimumWidth(250)
        self._renderer = renderer
        self._entry: IconEntry | None = None
        self._tint = DEFAULT_TINT
        self.rendered: dict[int, QImage] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll)
        content = QWidget()
        content.setObjectName("previewContent")
        content.setStyleSheet("#previewContent { background: transparent; }")
        self.scroll.setWidget(content)
        self.scroll.viewport().setAutoFillBackground(False)

        root = QVBoxLayout(content)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        title = QLabel(self.tr("Preview"))
        title.setObjectName("h2")
        root.addWidget(title)

        # all folder-relevant sizes side by side on a "stage", 64 being the largest
        self.size_labels: dict[int, QLabel] = {}
        self.stage = QFrame()
        self.stage.setObjectName("stage")
        stage_lay = QHBoxLayout(self.stage)
        stage_lay.setContentsMargins(12, 14, 12, 8)
        stage_lay.setSpacing(12)
        stage_lay.addStretch(1)
        for s in PREVIEW_SIZES:
            stage_lay.addLayout(self._size_cell(s, box=HERO_SIZE))
        stage_lay.addStretch(1)
        root.addWidget(self.stage)

        opts = QHBoxLayout()
        self.compose = QCheckBox(self.tr("Compose on folder base"))
        self.compose.toggled.connect(self._on_options)
        opts.addWidget(self.compose)
        opts.addStretch(1)
        root.addLayout(opts)

        tints = QHBoxLayout()
        tints.setSpacing(4)
        tints.addWidget(QLabel(self.tr("Tint")))
        self.tint_buttons: list[QToolButton] = []
        for hexcolor in TINT_PRESETS:
            b = QToolButton()
            b.setFixedSize(20, 20)
            b.setToolTip(hexcolor)
            b.setStyleSheet(
                f"background:{hexcolor}; border-radius:10px; border:1px solid rgba(0,0,0,0.25);"
            )
            b.clicked.connect(lambda _=False, c=hexcolor: self.set_tint(c))
            tints.addWidget(b)
            self.tint_buttons.append(b)
        self.custom_tint = QToolButton()
        self.custom_tint.setText("…")
        self.custom_tint.setToolTip(self.tr("Custom color"))
        self.custom_tint.clicked.connect(self._pick_color)
        tints.addWidget(self.custom_tint)
        tints.addStretch(1)
        root.addLayout(tints)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("muted")
        root.addWidget(line)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        mono = monospace_font()
        self.name_label = QLabel("—")
        self.name_label.setWordWrap(True)
        self.source_label = QLabel("—")
        self.ref_label = QLabel("—")
        self.ref_label.setFont(mono)
        self.ref_label.setWordWrap(True)
        self.ref_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.cat_label = QLabel("—")
        self.cat_label.setWordWrap(True)
        self.license_label = QLabel("—")
        self.license_label.setWordWrap(True)
        form.addRow(self.tr("Name"), self.name_label)
        form.addRow(self.tr("Source"), self.source_label)
        form.addRow(self.tr("Identifier"), self.ref_label)
        form.addRow(self.tr("Categories"), self.cat_label)
        form.addRow(self.tr("License"), self.license_label)
        root.addLayout(form)
        root.addStretch(1)

        self.placeholder = QLabel(self.tr("Select an icon to preview it"))
        self.placeholder.setObjectName("muted")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.insertWidget(1, self.placeholder)
        self._set_enabled(False)

    # -- public API -------------------------------------------------------
    @property
    def entry(self) -> IconEntry | None:
        return self._entry

    @property
    def tint(self) -> str:
        return self._tint

    def options(self) -> ApplyOptions:
        return ApplyOptions(compose_on_folder_base=self.compose.isChecked(), tint=self._tint)

    def set_entry(self, entry: IconEntry | None, source_name: str = "") -> None:
        self._entry = entry
        if entry is None:
            self._set_enabled(False)
            for lbl in self.size_labels.values():
                lbl.clear()
            self.rendered.clear()
            for lbl in (
                self.name_label,
                self.source_label,
                self.ref_label,
                self.cat_label,
                self.license_label,
            ):
                lbl.setText("—")
            return
        self._set_enabled(True)
        # glyph-style icons default to folder composition (product decision)
        self.compose.blockSignals(True)
        self.compose.setChecked(entry.kind is IconKind.GLYPH)
        self.compose.blockSignals(False)
        self.name_label.setText(entry.name)
        self.source_label.setText(source_name or entry.source_id)
        rid = f",-{entry.ref.resource_id}" if entry.ref.resource_id is not None else ""
        ref = f"{entry.ref.location}{rid}"
        # zero-width spaces after separators let long paths wrap inside the panel
        self.ref_label.setText(ref.replace("\\", "\\" + ZWSP).replace("/", "/" + ZWSP))
        self.ref_label.setToolTip(ref)
        self.cat_label.setText(", ".join(category_label(c) for c in sorted(entry.categories)))
        self.license_label.setText(entry.license)
        self._render()

    def set_tint(self, color: str) -> None:
        self._tint = QColor(color).name()
        self._on_options()

    # -- internals ----------------------------------------------------------
    def _size_cell(self, s: int, box: int | None = None) -> QVBoxLayout:
        cell = QVBoxLayout()
        cell.setSpacing(2)
        img = QLabel()
        img.setFixedSize(s, box or s)  # common box height keeps captions aligned
        img.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        cap = QLabel(f"{s}")
        cap.setObjectName("muted")
        cap.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cell.addWidget(img, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        cell.addWidget(cap, 0, Qt.AlignmentFlag.AlignHCenter)
        self.size_labels[s] = img
        return cell

    def _set_enabled(self, on: bool) -> None:
        self.placeholder.setVisible(not on)
        self.stage.setVisible(on)
        for w in (self.compose, self.custom_tint, *self.tint_buttons):
            w.setEnabled(on)

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self._tint), self, self.tr("Folder tint"))
        if c.isValid():
            self.set_tint(c.name())

    def _on_options(self, *_args) -> None:
        self._render()
        self.options_changed.emit(self.options())

    def _render(self) -> None:
        if self._entry is None:
            return
        self.rendered.clear()
        for s, lbl in self.size_labels.items():
            img = self._renderer(self._entry, s)
            if self.compose.isChecked():
                img = compose_on_folder(img, s, self._tint)
            self.rendered[s] = img
            lbl.setPixmap(QPixmap.fromImage(img))
