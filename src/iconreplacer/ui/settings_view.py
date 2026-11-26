"""Settings tab: sources, network kill switch, Explorer integration, language and theme."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from iconreplacer.shell.registration import RegistrationStatus, ShellRegistration

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
    registration_changed = Signal(object)  # RegistrationStatus | None

    def __init__(
        self,
        registry: SourceRegistry,
        settings: SettingsStore,
        parent=None,
        *,
        registration: ShellRegistration | None = None,
        local_folders_supported: bool = True,
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        self._settings = settings
        self._registration = registration
        self.registration_status: RegistrationStatus | None = None
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
        self.add_folder_btn.setVisible(local_folders_supported)
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

        # Explorer integration ---------------------------------------------
        self.explorer_box = QGroupBox(self.tr("Explorer integration"))
        ex_lay = QVBoxLayout(self.explorer_box)
        status_row = QHBoxLayout()
        status_caption = QLabel(self.tr("“Replace Icon” folder menu:"))
        status_row.addWidget(status_caption)
        self.registration_label = QLabel()
        self.registration_label.setWordWrap(True)
        self.registration_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        status_row.addWidget(self.registration_label, 1)
        self.register_btn = QPushButton(self.tr("Register"))
        self.register_btn.clicked.connect(self.register_verb)
        status_row.addWidget(self.register_btn)
        self.unregister_btn = QPushButton(self.tr("Unregister"))
        self.unregister_btn.clicked.connect(self.unregister_verb)
        status_row.addWidget(self.unregister_btn)
        ex_lay.addLayout(status_row)
        ex_hint = QLabel(
            self.tr(
                "Adds “Replace Icon” to the folder right-click menu for your account only. "
                "On Windows 11 it appears under “Show more options”."
            )
        )
        ex_hint.setObjectName("muted")
        ex_hint.setWordWrap(True)
        ex_lay.addWidget(ex_hint)
        root.addWidget(self.explorer_box)

        # Appearance ---------------------------------------------------------
        ui_box = QGroupBox(self.tr("Appearance"))
        form = QFormLayout(ui_box)
        self.language = QComboBox()
        self.language.addItem(self.tr("System default"), "")
        for code, name in available_languages():
            self.language.addItem(name, code)
        self._language_at_start = str(settings.get("ui.language", "") or "")
        self.language.setCurrentIndex(max(0, self.language.findData(self._language_at_start)))
        self.language.currentIndexChanged.connect(self._on_language)
        self.language_note = QLabel(self.tr("Restart IconReplacer to apply the language"))
        self.language_note.setObjectName("muted")
        self.language_note.setWordWrap(True)
        self.language_note.setVisible(False)
        self.theme = QComboBox()
        self.theme.addItem(self.tr("System"), ThemeMode.SYSTEM.value)
        self.theme.addItem(self.tr("Light"), ThemeMode.LIGHT.value)
        self.theme.addItem(self.tr("Dark"), ThemeMode.DARK.value)
        current = settings.get("ui.theme", ThemeMode.SYSTEM.value)
        self.theme.setCurrentIndex(max(0, self.theme.findData(current)))
        self.theme.currentIndexChanged.connect(self._on_theme)
        form.addRow(self.tr("Language"), self.language)
        form.addRow("", self.language_note)
        form.addRow(self.tr("Theme"), self.theme)
        root.addWidget(ui_box)

        self.rebuild_sources()
        self.refresh_registration()

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

    # -- Explorer integration --------------------------------------------------
    def refresh_registration(self) -> RegistrationStatus | None:
        from iconreplacer.shell.registration import RegistrationState

        if self._registration is None:
            self.registration_status = None
            self.registration_label.setText(self.tr("Not available"))
            self.register_btn.setEnabled(False)
            self.unregister_btn.setEnabled(False)
            return None
        try:
            status = self._registration.status()
        except OSError as exc:
            self.registration_status = None
            self.registration_label.setText(
                self.tr("Error: %1").replace("%1", str(exc.strerror or exc))
            )
            return None
        self.registration_status = status
        state = status.state
        if state is RegistrationState.REGISTERED:
            text = self.tr("Registered")
        elif state is RegistrationState.STALE:
            text = self.tr("Stale – points to another location")
            if status.path:
                text += "\n" + status.path
        else:
            text = self.tr("Not registered")
        self.registration_label.setText(text)
        self.register_btn.setText(
            self.tr("Register")
            if state is RegistrationState.NOT_REGISTERED
            else self.tr("Re-register")
        )
        self.register_btn.setEnabled(True)
        self.unregister_btn.setEnabled(state is not RegistrationState.NOT_REGISTERED)
        return status

    def _run_registration(self, op) -> None:
        try:
            op()
        except OSError as exc:
            self.refresh_registration()
            self.registration_label.setText(
                self.tr("Error: %1").replace("%1", str(exc.strerror or exc))
            )
            return
        self.registration_changed.emit(self.refresh_registration())

    def register_verb(self) -> None:
        if self._registration is not None:
            self._run_registration(self._registration.register)

    def unregister_verb(self) -> None:
        if self._registration is not None:
            self._run_registration(self._registration.unregister)

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
        known = {s.info.id for s in self._registry.sources()}
        # keep ids of sources that are not registered right now (e.g. a missing local folder)
        disabled = [d for d in self._settings.get("sources.disabled", []) if d not in known]
        disabled += [i for i in sorted(known) if not self._registry.is_enabled(i)]
        self._settings.set("sources.disabled", disabled)
        self.sources_changed.emit()

    def _on_language(self, _i: int) -> None:
        code = str(self.language.currentData() or "")
        self._settings.set("ui.language", code)
        self.language_note.setVisible(code != self._language_at_start)
        self.language_changed.emit(code)

    def _on_theme(self, _i: int) -> None:
        mode = self.theme.currentData()
        self._settings.set("ui.theme", mode)
        self.theme_changed.emit(mode)

    def _pick_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, self.tr("Choose an icon folder"))
        if path:
            self.add_local_folder.emit(Path(path))
