"""Settings tab: sources, network kill switch, language and theme."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.core.contracts import SettingsStore
from iconreplacer.core.models import Section
from iconreplacer.ui.strings import section_label
from iconreplacer.ui.theme import ThemeMode

I18N_DIR = Path(__file__).resolve().parents[1] / "i18n"
SOURCE_ROLE = Qt.ItemDataRole.UserRole + 20


def available_languages(i18n_dir: Path = I18N_DIR) -> list[tuple[str, str]]:
    """(code, display name) pairs: built-in English plus compiled .qm translations."""
    from PySide6.QtCore import QLocale

    langs = [("en", "English")]
    if i18n_dir.is_dir():
        for qm in sorted(i18n_dir.glob("iconreplacer_*.qm")):
            code = qm.stem.split("_", 1)[1]
            if code == "en":
                continue
            loc = QLocale(code)
            langs.append((code, loc.nativeLanguageName() or code))
    return langs


class SettingsView(QWidget):
    network_changed = Signal(bool)
    sources_changed = Signal()
    theme_changed = Signal(str)
    language_changed = Signal(str)
    add_local_folder = Signal(Path)

    def __init__(self, registry: SourceRegistry, settings: SettingsStore, parent=None) -> None:
        super().__init__(parent)
        self._registry = registry
        self._settings = settings
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Sources --------------------------------------------------------
        src_box = QGroupBox(self.tr("Icon sources"))
        src_lay = QVBoxLayout(src_box)
        self.sources = QTreeWidget()
        self.sources.setHeaderLabels(
            [self.tr("Source"), self.tr("Description"), self.tr("License")]
        )
        self.sources.setRootIsDecorated(False)
        self.sources.itemChanged.connect(self._on_source_toggled)
        src_lay.addWidget(self.sources)
        btns = QHBoxLayout()
        self.add_folder_btn = QPushButton(self.tr("Add local folder…"))
        self.add_folder_btn.clicked.connect(self._pick_folder)
        btns.addWidget(self.add_folder_btn)
        btns.addStretch(1)
        src_lay.addLayout(btns)
        root.addWidget(src_box, 1)

        # Network -----------------------------------------------------------
        net_box = QGroupBox(self.tr("Network"))
        net_lay = QVBoxLayout(net_box)
        self.network = QCheckBox(self.tr("Allow network access"))
        self.network.setChecked(bool(settings.get("network.allowed", True)))
        self.network.toggled.connect(self._on_network)
        net_lay.addWidget(self.network)
        hint = QLabel(
            self.tr("When off, online sources are unavailable and nothing is downloaded.")
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        net_lay.addWidget(hint)
        root.addWidget(net_box)

        # Appearance ---------------------------------------------------------
        ui_box = QGroupBox(self.tr("Appearance"))
        form = QFormLayout(ui_box)
        self.language = QComboBox()
        for code, name in available_languages():
            self.language.addItem(name, code)
        self.language.currentIndexChanged.connect(
            lambda _i: self.language_changed.emit(self.language.currentData())
        )
        self.theme = QComboBox()
        self.theme.addItem(self.tr("System"), ThemeMode.SYSTEM.value)
        self.theme.addItem(self.tr("Light"), ThemeMode.LIGHT.value)
        self.theme.addItem(self.tr("Dark"), ThemeMode.DARK.value)
        current = settings.get("ui.theme", ThemeMode.SYSTEM.value)
        self.theme.setCurrentIndex(max(0, self.theme.findData(current)))
        self.theme.currentIndexChanged.connect(self._on_theme)
        form.addRow(self.tr("Language"), self.language)
        form.addRow(self.tr("Theme"), self.theme)
        root.addWidget(ui_box)

        self.rebuild_sources()

    # -- public ----------------------------------------------------------------
    def network_allowed(self) -> bool:
        return self.network.isChecked()

    def source_item(self, source_id: str) -> QTreeWidgetItem:
        for i in range(self.sources.topLevelItemCount()):
            header = self.sources.topLevelItem(i)
            for j in range(header.childCount()):
                child = header.child(j)
                if child.data(0, SOURCE_ROLE) == source_id:
                    return child
        raise KeyError(source_id)

    def rebuild_sources(self) -> None:
        self.sources.blockSignals(True)
        self.sources.clear()
        for section in (Section.SYSTEM, Section.ONLINE, Section.LOCAL):
            header = QTreeWidgetItem([section_label(section)])
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            f = header.font(0)
            f.setBold(True)
            header.setFont(0, f)
            self.sources.addTopLevelItem(header)
            for src in self._registry.sources(section):
                info = src.info
                item = QTreeWidgetItem(header, [info.name, info.description, info.license])
                item.setData(0, SOURCE_ROLE, info.id)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    0,
                    Qt.CheckState.Checked
                    if self._registry.is_enabled(info.id)
                    else Qt.CheckState.Unchecked,
                )
            header.setExpanded(True)
        hdr = self.sources.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(2, 260)
        self.sources.blockSignals(False)
        self._apply_network_state()

    # -- internals -------------------------------------------------------------
    def _apply_network_state(self) -> None:
        allowed = self.network.isChecked()
        for src in self._registry.sources(Section.ONLINE):
            item = self.source_item(src.info.id)
            item.setDisabled(not allowed)
            tip = "" if allowed else self.tr("Unavailable: network access is off")
            item.setToolTip(0, tip)

    def _on_network(self, on: bool) -> None:
        self._settings.set("network.allowed", on)
        self._apply_network_state()
        self.network_changed.emit(on)

    def _on_source_toggled(self, item: QTreeWidgetItem, column: int) -> None:
        sid = item.data(0, SOURCE_ROLE)
        if sid is None or column != 0:
            return
        self._registry.set_enabled(sid, item.checkState(0) == Qt.CheckState.Checked)
        self.sources_changed.emit()

    def _on_theme(self, _i: int) -> None:
        mode = self.theme.currentData()
        self._settings.set("ui.theme", mode)
        self.theme_changed.emit(mode)

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.tr("Choose an icon folder"))
        if path:
            self.add_local_folder.emit(Path(path))
