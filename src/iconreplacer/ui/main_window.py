"""Main IconReplacer window."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QSlider,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from iconreplacer.catalog.mock_source import MockIconSource
from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.core.contracts import FolderIconService, SettingsStore
from iconreplacer.core.models import ActionResult, IconEntry, IconKind, Section, SourceInfo
from iconreplacer.ui.about_dialog import AboutDialog
from iconreplacer.ui.folder_base import recolor
from iconreplacer.ui.icon_grid import DEFAULT_THUMB, MAX_THUMB, MIN_THUMB, IconGrid
from iconreplacer.ui.preview_panel import PreviewPanel
from iconreplacer.ui.settings_view import SettingsView
from iconreplacer.ui.sidebar import CategoryChips, SourceSidebar
from iconreplacer.ui.source_pill import SourcePill
from iconreplacer.ui.target_header import TargetHeader
from iconreplacer.ui.theme import ThemeManager, ThemeMode
from iconreplacer.version import PRODUCT_NAME

MIN_W, MIN_H = 800, 560
DEFAULT_W, DEFAULT_H = 1040, 760
DEFAULT_SIDEBAR_W = 250


class MainWindow(QMainWindow):
    def __init__(
        self,
        registry: SourceRegistry,
        service: FolderIconService,
        settings: SettingsStore,
        theme: ThemeManager | None = None,
        folders: Sequence[Path] = (),
    ) -> None:
        super().__init__()
        self.registry = registry
        self.service = service
        self.settings = settings
        self.theme = theme
        self.setWindowTitle(PRODUCT_NAME)
        self.setMinimumSize(MIN_W, MIN_H)
        self.resize(DEFAULT_W, DEFAULT_H)
        self._sidebar_width = DEFAULT_SIDEBAR_W
        self._grown_by = 0
        self._source_id: str | None = None

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        # ---------------- Browse tab
        browse = QWidget()
        bl = QVBoxLayout(browse)
        bl.setContentsMargins(10, 10, 10, 6)
        bl.setSpacing(8)

        self.header = TargetHeader(folders)
        bl.addWidget(self.header)

        bar = QHBoxLayout()
        self.sources_btn = QToolButton()
        self.sources_btn.setText(self.tr("Sources"))
        self.sources_btn.setCheckable(True)
        self.sources_btn.setShortcut(QKeySequence("Ctrl+B"))
        self.sources_btn.setToolTip(self.tr("Show or hide the sources panel (Ctrl+B)"))
        self.sources_btn.toggled.connect(self.set_sources_visible)
        bar.addWidget(self.sources_btn)
        self.source_pill = SourcePill()
        self.source_pill.dismissed.connect(lambda: self.sidebar.select_source(None))
        bar.addWidget(self.source_pill)
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr("Search name, tag or resource ID…"))
        self.search.setClearButtonEnabled(True)
        bar.addWidget(self.search, 1)
        size_caption = QLabel(self.tr("Size"))
        size_caption.setObjectName("muted")
        bar.addWidget(size_caption)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(MIN_THUMB, MAX_THUMB)
        self.size_slider.setValue(DEFAULT_THUMB)
        self.size_slider.setFixedWidth(160)
        bar.addWidget(self.size_slider)
        self.size_value = QLabel(f"{DEFAULT_THUMB}px")
        self.size_value.setMinimumWidth(44)
        bar.addWidget(self.size_value)
        bl.addLayout(bar)

        self.chips = CategoryChips()
        bl.addWidget(self.chips)

        self.sidebar = SourceSidebar(registry)
        self.grid = IconGrid(self._render)
        self.preview = PreviewPanel(self._render)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        for w in (self.sidebar, self.grid, self.preview):
            self.splitter.addWidget(w)
            self.splitter.setCollapsible(self.splitter.indexOf(w), False)
        self.grid.setMinimumWidth(240)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([DEFAULT_SIDEBAR_W, 740, 280])
        self.sidebar.setVisible(False)
        bl.addWidget(self.splitter, 1)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        banner_lay = QHBoxLayout(self.banner)
        banner_lay.setContentsMargins(10, 6, 10, 6)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        banner_lay.addWidget(self.banner_text, 1)
        self.banner.setVisible(False)
        bl.addWidget(self.banner)
        self._banner_timer = QTimer(self)
        self._banner_timer.setSingleShot(True)
        self._banner_timer.timeout.connect(lambda: self.banner.setVisible(False))

        self.tabs.addTab(browse, self.tr("Browse"))

        # ---------------- Settings tab
        self.settings_view = SettingsView(registry, settings)
        self.tabs.addTab(self.settings_view, self.tr("Settings"))

        about_btn = QToolButton()
        about_btn.setText(self.tr("About"))
        about_btn.clicked.connect(self.show_about)
        self.tabs.setCornerWidget(about_btn, Qt.Corner.TopRightCorner)

        # ---------------- wiring
        self.search.textChanged.connect(self.grid.proxy.set_search)
        self.size_slider.valueChanged.connect(self._on_size)
        self.chips.category_selected.connect(self.grid.proxy.set_category)
        self.sidebar.source_selected.connect(self._on_source)
        self.grid.entry_selected.connect(self._on_entry)
        for sig in (
            self.grid.proxy.modelReset,
            self.grid.proxy.rowsInserted,
            self.grid.proxy.rowsRemoved,
            self.grid.proxy.layoutChanged,
        ):
            sig.connect(self._update_status)
        self.header.apply_clicked.connect(self._apply)
        self.header.undo_clicked.connect(self._undo)
        self.header.restore_clicked.connect(self._restore)
        self.settings_view.network_changed.connect(lambda _on: self._refresh_availability())
        self.settings_view.sources_changed.connect(self._refresh_availability)
        self.settings_view.theme_changed.connect(self._on_theme)
        self.settings_view.add_local_folder.connect(self.add_local_folder)

        if theme is not None:
            theme.changed.connect(self._on_theme_applied)
        self.grid.set_entries(registry.all_entries())
        self._refresh_availability()
        self._update_status()

    # -- rendering -------------------------------------------------------------
    def _render(self, entry: IconEntry, size: int):
        img = self.registry.get(entry.source_id).render(entry, size)
        if entry.kind is IconKind.GLYPH:
            # monochrome glyphs follow the theme's text color so they read in light and dark
            ink = self.palette().color(QPalette.ColorRole.WindowText)
            img = recolor(img, ink)
        return img

    def _on_theme_applied(self, _is_dark: bool) -> None:
        self.grid.delegate.clear_cache()
        self.grid.view.viewport().update()
        self.preview.set_entry(self.preview.entry, self.preview.source_label.text())

    # -- sources panel ---------------------------------------------------------
    def _available_geometry(self) -> QRect:
        screen = self.screen() or QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def sources_visible(self) -> bool:
        return not self.sidebar.isHidden()

    def set_sources_visible(self, on: bool) -> None:
        """Show/hide the sources sidebar, growing/shrinking a normal window to fit it."""
        if on == self.sources_visible():
            return
        if self.sources_btn.isChecked() != on:
            self.sources_btn.blockSignals(True)
            self.sources_btn.setChecked(on)
            self.sources_btn.blockSignals(False)
        resizable = not (self.isMaximized() or self.isFullScreen())
        if on:
            sizes = self.splitter.sizes()
            grid_w, preview_w = sizes[1], sizes[2]
            if resizable:
                avail = self._available_geometry()
                geo = self.geometry()
                extra = self._sidebar_width + self.splitter.handleWidth()
                target = min(geo.width() + extra, avail.width())
                self._grown_by = max(0, target - geo.width())
                x = min(geo.x(), avail.x() + avail.width() - target)
                self.setGeometry(max(avail.x(), x), geo.y(), target, geo.height())
            else:
                self._grown_by = 0
            self.sidebar.setVisible(True)
            self.splitter.setSizes([self._sidebar_width, grid_w, preview_w])
        else:
            self._sidebar_width = max(self.sidebar.minimumWidth(), self.splitter.sizes()[0])
            self.sidebar.setVisible(False)
            if resizable and self._grown_by:
                geo = self.geometry()
                self.resize(max(self.minimumWidth(), geo.width() - self._grown_by), geo.height())
            self._grown_by = 0
        self._update_pill()

    def _on_source(self, source_id: str | None) -> None:
        self._source_id = source_id
        self.grid.proxy.set_source(source_id)
        self._update_pill()

    def _update_pill(self) -> None:
        if self._source_id is None or self.sources_visible():
            self.source_pill.setVisible(False)
        else:
            self.source_pill.show_source(self.registry.info(self._source_id).name)

    # -- slots -----------------------------------------------------------------
    def _on_size(self, value: int) -> None:
        self.grid.set_thumb_size(value)
        self.size_value.setText(f"{value}px")

    def _on_entry(self, entry: IconEntry | None) -> None:
        name = self.registry.info(entry.source_id).name if entry else ""
        self.preview.set_entry(entry, name)
        self.header.set_has_selection(entry is not None)

    def _on_theme(self, mode: str) -> None:
        if self.theme is not None:
            self.theme.apply(ThemeMode(mode))

    def _refresh_availability(self) -> None:
        allowed = self.settings_view.network_allowed()
        available = {
            s.info.id
            for s in self.registry.sources()
            if self.registry.is_available(s.info.id, allowed)
        }
        self.sidebar.set_available(available)
        self.grid.proxy.set_available_sources(frozenset(available))
        self._update_status()

    def _update_status(self, *_args) -> None:
        self.statusBar().showMessage(self.tr("%n icon(s) shown", "", self.grid.visible_count()))

    def _folders_text(self, n: int) -> str:
        return self.tr("%n folder(s)", "", n)

    def _notify(self, result: ActionResult, text: str) -> None:
        self.banner_text.setText(text if result.ok else self.tr("No target folder."))
        self.banner.setVisible(True)
        self._banner_timer.start(8000)

    def _apply(self) -> None:
        entry = self.preview.entry
        folders = self.header.folders
        if entry is None or not folders:
            return
        opts = self.preview.options()
        result = self.service.apply(folders, entry, opts)
        mode = (
            self.tr("composed on folder base") if opts.compose_on_folder_base else self.tr("as-is")
        )
        text = (
            self.tr("Simulation: “%1” would be applied (%2) to %3. Nothing was changed.")
            .replace("%1", entry.name)
            .replace("%2", mode)
            .replace("%3", self._folders_text(len(folders)))
        )
        self._notify(result, text)

    def _undo(self) -> None:
        folders = self.header.folders
        result = self.service.undo(folders)
        self._notify(
            result,
            self.tr("Simulation: the last change would be undone on %1.").replace(
                "%1", self._folders_text(len(folders))
            ),
        )

    def _restore(self) -> None:
        folders = self.header.folders
        result = self.service.restore_default(folders)
        self._notify(
            result,
            self.tr("Simulation: the default icon would be restored on %1.").replace(
                "%1", self._folders_text(len(folders))
            ),
        )

    def show_about(self) -> AboutDialog:
        dlg = AboutDialog(self)
        dlg.open()
        return dlg

    def add_local_folder(self, path: Path) -> None:
        """Prototype: registers a mock local source for the chosen folder."""
        sid = "local-" + hashlib.blake2s(str(path).lower().encode(), digest_size=4).hexdigest()
        if sid in {s.info.id for s in self.registry.sources()}:
            return
        info = SourceInfo(sid, path.name or str(path), str(path), Section.LOCAL, "User provided")
        self.registry.add(
            MockIconSource(info, ("Folders", "Media", "Documents"), 24, IconKind.FULL, str(path))
        )
        self.sidebar.rebuild()
        self.settings_view.rebuild_sources()
        self.grid.set_entries(self.registry.all_entries())
        self._refresh_availability()
