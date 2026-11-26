"""Main IconReplacer window."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.core.contracts import (
    DynamicIconSource,
    FolderIconService,
    IconSource,
    SearchableIconSource,
    SettingsStore,
)
from iconreplacer.core.models import ActionResult, IconEntry, IconKind
from iconreplacer.services.apply_worker import ActionRunner
from iconreplacer.ui.about_dialog import AboutDialog
from iconreplacer.ui.folder_base import recolor
from iconreplacer.ui.icon_grid import DEFAULT_THUMB, MAX_THUMB, MIN_THUMB, IconGrid
from iconreplacer.ui.preview_panel import PreviewPanel
from iconreplacer.ui.result_dialog import FailureDetailsDialog, failed_folders
from iconreplacer.ui.settings_view import SettingsView
from iconreplacer.ui.sidebar import CategoryChips, SourceSidebar
from iconreplacer.ui.source_pill import SourcePill
from iconreplacer.ui.target_header import TargetHeader
from iconreplacer.ui.theme import ThemeManager, ThemeMode
from iconreplacer.version import PRODUCT_NAME

if TYPE_CHECKING:
    from iconreplacer.shell.registration import RegistrationStatus, ShellRegistration

log = logging.getLogger(__name__)

MIN_W, MIN_H = 800, 560
DEFAULT_W, DEFAULT_H = 1040, 760
DEFAULT_SIDEBAR_W = 250
MIN_VISIBLE_W, MIN_VISIBLE_H = 120, 60
SEARCH_DEBOUNCE_MS = 400
DYNAMIC_COALESCE_MS = 50
BANNER_MS = 8000
CONFIRM_LIST_LIMIT = 15

LocalSourceFactory = Callable[[Path], IconSource]


def geometry_fits(frame: QRect, screens: Sequence[QRect]) -> bool:
    """True if enough of the window frame lies on some screen to be reachable."""
    for screen in screens:
        inter = frame.intersected(screen)
        if inter.width() >= MIN_VISIBLE_W and inter.height() >= MIN_VISIBLE_H:
            return True
    return False


class MainWindow(QMainWindow):
    def __init__(
        self,
        registry: SourceRegistry,
        service: FolderIconService,
        settings: SettingsStore,
        theme: ThemeManager | None = None,
        folders: Sequence[Path] = (),
        *,
        registration: ShellRegistration | None = None,
        local_source_factory: LocalSourceFactory | None = None,
    ) -> None:
        super().__init__()
        self.registry = registry
        self.service = service
        self.settings = settings
        self.theme = theme
        self.local_source_factory = local_source_factory
        self.setWindowTitle(PRODUCT_NAME)
        self.setMinimumSize(MIN_W, MIN_H)
        self.resize(DEFAULT_W, DEFAULT_H)
        self._sidebar_width = DEFAULT_SIDEBAR_W
        self._grown_by = 0
        self._source_id: str | None = None
        self._unsubscribers: list[Callable[[], None]] = []
        self._dirty_sources: set[str] = set()
        self._entry_ids: dict[str, tuple[str, ...]] = {}
        self._searched: tuple[str, str] | None = None  # (source id, query) last sent remotely
        self._action_folders: tuple[Path, ...] = ()
        self._banner_kind = ""
        self._applied_name = ""
        self.last_result: ActionResult | None = None
        self.details_dialog: FailureDetailsDialog | None = None

        # restore persisted source state before the views are built from the registry
        for folder in settings.get("sources.local_folders", []) or []:
            self._register_local(Path(folder))
        for sid in settings.get("sources.disabled", []) or []:
            if sid in {s.info.id for s in registry.sources()}:
                registry.set_enabled(sid, False)

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
        banner_lay.setContentsMargins(10, 4, 4, 4)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        banner_lay.addWidget(self.banner_text, 1)
        self.banner_action = QPushButton()
        self.banner_action.setVisible(False)
        self.banner_action.clicked.connect(self._on_banner_action)
        banner_lay.addWidget(self.banner_action)
        self.banner_close = QToolButton()
        self.banner_close.setText("✕")
        self.banner_close.setAutoRaise(True)
        self.banner_close.setToolTip(self.tr("Dismiss"))
        self.banner_close.clicked.connect(self.hide_banner)
        banner_lay.addWidget(self.banner_close)
        self._banner_callback: Callable[[], None] | None = None
        self.banner.setVisible(False)
        bl.addWidget(self.banner)
        self._banner_timer = QTimer(self)
        self._banner_timer.setSingleShot(True)
        self._banner_timer.timeout.connect(self.hide_banner)

        self.tabs.addTab(browse, self.tr("Browse"))

        # ---------------- Settings tab
        self.settings_view = SettingsView(
            registry,
            settings,
            registration=registration,
            local_folders_supported=local_source_factory is not None,
        )
        self.tabs.addTab(self.settings_view, self.tr("Settings"))

        about_btn = QToolButton()
        about_btn.setText(self.tr("About"))
        about_btn.clicked.connect(self.show_about)
        self.tabs.setCornerWidget(about_btn, Qt.Corner.TopRightCorner)

        # ---------------- workers and timers
        self.runner = ActionRunner(self)
        self.runner.started.connect(lambda _a: self.header.set_busy(True))
        self.runner.finished.connect(self._on_action_done)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._run_remote_search)
        self._dynamic_timer = QTimer(self)
        self._dynamic_timer.setSingleShot(True)
        self._dynamic_timer.setInterval(DYNAMIC_COALESCE_MS)
        self._dynamic_timer.timeout.connect(self._flush_dynamic)

        # ---------------- wiring
        self.search.textChanged.connect(self._on_search_text)
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
        self.settings_view.network_changed.connect(self._on_network)
        self.settings_view.sources_changed.connect(self._on_sources_changed)
        self.settings_view.theme_changed.connect(self._on_theme)
        self.settings_view.add_local_folder.connect(self.add_local_folder)
        self.settings_view.registration_changed.connect(self._on_registration_changed)

        if theme is not None:
            theme.changed.connect(self._on_theme_applied)
        self.grid.set_entries(registry.all_entries())
        self._enabled_dynamic = self._enabled_dynamic_ids()
        self._connect_dynamic_sources()
        self._refresh_availability()
        self._update_status()
        self._restore_view_state()
        self._check_registration()
        QTimer.singleShot(0, self._refresh_dynamic_sources)

    # -- persisted view state ----------------------------------------------------
    def _restore_view_state(self) -> None:
        thumb = int(self.settings.get("ui.thumb_size", DEFAULT_THUMB) or DEFAULT_THUMB)
        self.size_slider.setValue(max(MIN_THUMB, min(MAX_THUMB, thumb)))
        restored = self._restore_geometry()
        if self.settings.get("ui.sources_visible", False):
            self.set_sources_visible(True, resize=not restored)

    def _restore_geometry(self) -> bool:
        encoded = self.settings.get("ui.window_geometry")
        if not encoded:
            return False
        try:
            data = QByteArray.fromBase64(str(encoded).encode("ascii"))
        except (UnicodeEncodeError, ValueError):
            return False
        default = self.geometry()
        if self.restoreGeometry(data):
            screens = [s.availableGeometry() for s in QGuiApplication.screens()]
            if (
                self.isMaximized()
                or self.isFullScreen()
                or geometry_fits(self.frameGeometry(), screens)
            ):
                return True
        self.setWindowState(Qt.WindowState.WindowNoState)
        self.setGeometry(default)
        return False

    def closeEvent(self, event) -> None:
        encoded = bytes(self.saveGeometry().toBase64().data()).decode("ascii")
        self.settings.set("ui.window_geometry", encoded)
        self.settings.set("ui.sources_visible", self.sources_visible())
        self._disconnect_dynamic_sources()
        self.runner.wait()  # let a running folder action finish its writes
        super().closeEvent(event)

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

    def set_sources_visible(self, on: bool, resize: bool = True) -> None:
        """Show/hide the sources sidebar, growing/shrinking a normal window to fit it.

        With resize=False (restoring a saved geometry that already includes the sidebar)
        the window keeps its size.
        """
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
            if not resize:
                self._grown_by = (
                    self._sidebar_width + self.splitter.handleWidth() if resizable else 0
                )
            elif resizable:
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
        self.settings.set("ui.sources_visible", on)
        self._update_pill()

    def _on_source(self, source_id: str | None) -> None:
        previous = self._searched
        if previous is not None and previous[0] != source_id:
            self._send_search(previous[0], "")  # restore the left source's default listing
        self._source_id = source_id
        self.grid.proxy.set_source(source_id)
        self._update_search_exempt()
        self._update_pill()
        if self._remote_search_source() is not None and self.search.text().strip():
            self._search_timer.start()

    def _update_pill(self) -> None:
        if self._source_id is None or self.sources_visible():
            self.source_pill.setVisible(False)
        else:
            self.source_pill.show_source(self.registry.info(self._source_id).name)

    # -- remote search -----------------------------------------------------------
    def _remote_search_source(self) -> SearchableIconSource | None:
        """The selected source when it can run remote queries and is available now."""
        sid = self._source_id
        if sid is None:
            return None
        src = self.registry.get(sid)
        if not isinstance(src, SearchableIconSource):
            return None
        if not self.registry.is_available(sid, self.settings_view.network_allowed()):
            return None
        return src

    def _update_search_exempt(self) -> None:
        exempt = frozenset({self._source_id}) if self._remote_search_source() else frozenset()
        self.grid.proxy.set_search_exempt(exempt)

    def _on_search_text(self, text: str) -> None:
        self.grid.proxy.set_search(text)
        if self._remote_search_source() is not None:
            self._search_timer.start()  # restart: debounce

    def _send_search(self, source_id: str, query: str) -> None:
        src = self.registry.get(source_id)
        if isinstance(src, SearchableIconSource):
            try:
                src.search(query)
            except Exception:  # a misbehaving source must not break typing
                log.exception("search failed for %s", source_id)
        self._searched = (source_id, query) if query else None

    def _run_remote_search(self) -> None:
        if self._remote_search_source() is None or self._source_id is None:
            return
        query = self.search.text().strip()
        if self._searched == (self._source_id, query) or (not query and self._searched is None):
            return
        self._send_search(self._source_id, query)

    # -- dynamic sources ---------------------------------------------------------
    def _dynamic_sources(self) -> list[DynamicIconSource]:
        return [s for s in self.registry.sources() if isinstance(s, DynamicIconSource)]

    def _enabled_dynamic_ids(self) -> set[str]:
        return {s.info.id for s in self._dynamic_sources() if self.registry.is_enabled(s.info.id)}

    def _connect_dynamic_sources(self) -> None:
        allowed = self.settings_view.network_allowed()
        for src in self._dynamic_sources():
            sid = src.info.id
            if sid in self._entry_ids:
                continue
            self._entry_ids[sid] = tuple(e.id for e in src.entries())
            try:
                src.set_network_allowed(allowed)
                self._unsubscribers.append(src.subscribe(partial(self._on_source_changed, sid)))
            except Exception:
                log.exception("cannot connect dynamic source %s", sid)

    def _disconnect_dynamic_sources(self) -> None:
        for unsubscribe in self._unsubscribers:
            try:
                unsubscribe()
            except Exception:
                log.exception("unsubscribe failed")
        self._unsubscribers.clear()

    def _refresh_dynamic_sources(self, only: set[str] | None = None) -> None:
        for src in self._dynamic_sources():
            sid = src.info.id
            if not self.registry.is_enabled(sid) or (only is not None and sid not in only):
                continue
            try:
                src.refresh()
            except Exception:
                log.exception("refresh failed for %s", sid)

    def _on_source_changed(self, source_id: str) -> None:
        """Subscriber callback (GUI thread): coalesce bursts of updates."""
        self._dirty_sources.add(source_id)
        self._dynamic_timer.start()

    def _flush_dynamic(self) -> None:
        dirty, self._dirty_sources = self._dirty_sources, set()
        if not dirty:
            return
        changed = False
        for sid in dirty:
            ids = tuple(e.id for e in self.registry.get(sid).entries())
            if ids != self._entry_ids.get(sid):
                self._entry_ids[sid] = ids
                changed = True
        if changed:
            self._reload_entries()
        self.grid.delegate.clear_cache(dirty)
        self.grid.view.viewport().update()
        self.sidebar.refresh_sources(dirty)
        entry = self.preview.entry
        if entry is not None and entry.source_id in dirty:
            self.preview.set_entry(entry, self.preview.source_label.text())
        self._update_status()

    def _reload_entries(self) -> None:
        current = self.grid.current_entry()
        self.grid.set_entries(self.registry.all_entries())
        if current is None or not self.grid.select_entry_id(current.id):
            self._on_entry(None)

    # -- slots -----------------------------------------------------------------
    def _on_size(self, value: int) -> None:
        self.grid.set_thumb_size(value)
        self.size_value.setText(f"{value}px")
        self.settings.set("ui.thumb_size", value)

    def _on_entry(self, entry: IconEntry | None) -> None:
        name = self.registry.info(entry.source_id).name if entry else ""
        self.preview.set_entry(entry, name)
        self.header.set_has_selection(entry is not None)

    def _on_theme(self, mode: str) -> None:
        if self.theme is not None:
            self.theme.apply(ThemeMode(mode))

    def _on_network(self, allowed: bool) -> None:
        for src in self._dynamic_sources():
            try:
                src.set_network_allowed(allowed)
            except Exception:
                log.exception("set_network_allowed failed for %s", src.info.id)
        if allowed:
            self._refresh_dynamic_sources()
        self._refresh_availability()
        self.sidebar.refresh_sources()

    def _on_sources_changed(self) -> None:
        enabled = self._enabled_dynamic_ids()
        newly = enabled - self._enabled_dynamic
        self._enabled_dynamic = enabled
        if newly:
            self._refresh_dynamic_sources(newly)
        self._refresh_availability()

    def _refresh_availability(self) -> None:
        allowed = self.settings_view.network_allowed()
        available = {
            s.info.id
            for s in self.registry.sources()
            if self.registry.is_available(s.info.id, allowed)
        }
        self.sidebar.set_available(available)
        self.grid.proxy.set_available_sources(frozenset(available))
        self._update_search_exempt()
        self._update_status()

    def _update_status(self, *_args) -> None:
        self.statusBar().showMessage(self.tr("%n icon(s) shown", "", self.grid.visible_count()))

    # -- banner ----------------------------------------------------------------
    def show_banner(
        self,
        text: str,
        *,
        action_text: str | None = None,
        action: Callable[[], None] | None = None,
        timeout: int = BANNER_MS,
        kind: str = "info",
    ) -> None:
        """Show a notification; ``timeout`` 0 keeps it until dismissed or replaced."""
        self._banner_kind = kind
        self.banner_text.setText(text)
        self._banner_callback = action
        self.banner_action.setVisible(bool(action_text and action))
        self.banner_action.setText(action_text or "")
        self.banner.setVisible(True)
        if timeout:
            self._banner_timer.start(timeout)
        else:
            self._banner_timer.stop()

    def hide_banner(self) -> None:
        self._banner_timer.stop()
        self._banner_kind = ""
        self.banner.setVisible(False)

    def banner_kind(self) -> str:
        return self._banner_kind if not self.banner.isHidden() else ""

    def _on_banner_action(self) -> None:
        if self._banner_callback is not None:
            self._banner_callback()

    # -- Explorer integration ------------------------------------------------------
    def _check_registration(self) -> None:
        from iconreplacer.shell.registration import RegistrationState

        status = self.settings_view.registration_status
        if status is not None and status.state is RegistrationState.STALE:
            self.show_banner(
                self.tr("The Explorer “Replace Icon” menu points to another copy of IconReplacer."),
                action_text=self.tr("Fix Explorer integration"),
                action=self.settings_view.register_verb,
                timeout=0,
                kind="stale",
            )

    def _on_registration_changed(self, status: RegistrationStatus | None) -> None:
        from iconreplacer.shell.registration import RegistrationState

        if self.banner_kind() == "stale" and (
            status is None or status.state is not RegistrationState.STALE
        ):
            self.hide_banner()

    # -- folder actions ----------------------------------------------------------
    def _folders_text(self, n: int) -> str:
        return self.tr("%n folder(s)", "", n)

    def _confirm_batch(self, question: str, folders: Sequence[Path]) -> bool:
        shown = [str(f) for f in folders[:CONFIRM_LIST_LIMIT]]
        if len(folders) > CONFIRM_LIST_LIMIT:
            shown.append(
                self.tr("…and %1 more").replace("%1", str(len(folders) - CONFIRM_LIST_LIMIT))
            )
        answer = QMessageBox.question(
            self,
            PRODUCT_NAME,
            question + "\n\n" + "\n".join(shown),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _start(
        self, action: str, question: str, fn: Callable[[Sequence[Path]], ActionResult]
    ) -> bool:
        folders = self.header.folders
        if not folders or self.runner.busy:
            return False
        if len(folders) > 1 and not self._confirm_batch(question, folders):
            return False
        self._action_folders = tuple(folders)
        self.header.set_busy(True)
        self.runner.submit(action, lambda: fn(folders))
        return True

    def _apply(self) -> None:
        entry = self.preview.entry
        if entry is None:
            return
        opts = self.preview.options()
        n = len(self.header.folders)
        question = (
            self.tr("Apply “%1” to %2?")
            .replace("%1", entry.name)
            .replace("%2", self._folders_text(n))
        )
        self._applied_name = entry.name
        self._start("apply", question, lambda fs: self.service.apply(fs, entry, opts))

    def _undo(self) -> None:
        n = len(self.header.folders)
        question = self.tr("Undo the last change on %1?").replace("%1", self._folders_text(n))
        self._start("undo", question, self.service.undo)

    def _restore(self) -> None:
        n = len(self.header.folders)
        question = self.tr("Restore the default icon on %1?").replace("%1", self._folders_text(n))
        self._start("restore", question, self.service.restore_default)

    def _success_text(self, action: str, n: int) -> str:
        folders = self._folders_text(n)
        if action == "apply":
            return (
                self.tr("“%1” applied to %2.")
                .replace("%1", self._applied_name)
                .replace("%2", folders)
            )
        if action == "undo":
            return self.tr("Last change undone on %1.").replace("%1", folders)
        return self.tr("Default icon restored on %1.").replace("%1", folders)

    def _on_action_done(self, action: str, result: ActionResult) -> None:
        self.header.set_busy(self.runner.busy)
        self.last_result = result
        folders = self._action_folders
        failures = failed_folders(folders, result) if not result.ok else []
        if not result.ok and not failures:  # reported failure without a folder to blame
            failures = [(f, result.message) for f in folders]
        done = len(folders) - len(failures)
        if not failures:
            text = self._success_text(action, done)
            if result.simulated:
                text = self.tr("Simulation: %1 Nothing was changed.").replace("%1", text)
            self.show_banner(text, kind="success")
            return
        text = (
            self.tr("%1 of %2 changed.")
            .replace("%1", str(done))
            .replace("%2", self._folders_text(len(folders)))
        )
        self.show_banner(
            text,
            action_text=self.tr("Details…"),
            action=partial(self.show_failure_details, failures),
            timeout=0,
            kind="failure",
        )
        self.show_failure_details(failures)

    def show_failure_details(self, failures: Sequence[tuple[Path, str]]) -> FailureDetailsDialog:
        if self.details_dialog is not None:
            self.details_dialog.close()
        self.details_dialog = FailureDetailsDialog(failures, self)
        self.details_dialog.open()
        return self.details_dialog

    def show_about(self) -> AboutDialog:
        dlg = AboutDialog(self)
        dlg.open()
        return dlg

    # -- local folder sources ----------------------------------------------------
    def _register_local(self, path: Path) -> bool:
        """Create a local source for ``path`` through the factory. False if not added."""
        if self.local_source_factory is None:
            return False
        try:
            source = self.local_source_factory(path)
        except (OSError, ValueError) as exc:
            log.warning("cannot add local folder %s: %s", path, exc)
            return False
        if source.info.id in {s.info.id for s in self.registry.sources()}:
            return False
        self.registry.add(source)
        return True

    def add_local_folder(self, path: Path) -> None:
        if not self._register_local(path):
            return
        folders = list(self.settings.get("sources.local_folders", []) or [])
        if str(path) not in folders:
            self.settings.set("sources.local_folders", [*folders, str(path)])
        self.sidebar.rebuild()  # selects "All"
        self._on_source(None)
        self.settings_view.rebuild_sources()
        self.grid.set_entries(self.registry.all_entries())
        known = set(self._entry_ids)
        self._connect_dynamic_sources()
        self._enabled_dynamic = self._enabled_dynamic_ids()
        self._refresh_availability()
        new = set(self._entry_ids) - known
        if new:
            self._refresh_dynamic_sources(new)
