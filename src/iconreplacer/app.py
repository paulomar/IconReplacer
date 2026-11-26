"""QApplication bootstrap."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from iconreplacer.catalog.mock_source import build_mock_sources
from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.cli import CliOptions
from iconreplacer.core.contracts import InMemorySettingsStore
from iconreplacer.services.mock_folder_service import MockFolderIconService
from iconreplacer.shell.ipc import acquire, collect_startup_folders
from iconreplacer.ui.main_window import MainWindow
from iconreplacer.ui.settings_view import I18N_DIR
from iconreplacer.ui.theme import ThemeManager, ThemeMode
from iconreplacer.version import FULL_VERSION, PRODUCT_NAME


def install_translator(app: QApplication, language: str | None = None) -> QTranslator | None:
    """Load a compiled translation if available. English is built in (source strings)."""
    lang = language or QLocale.system().name().split("_")[0]
    if lang == "en":
        return None
    tr = QTranslator(app)
    if tr.load(str(I18N_DIR / f"iconreplacer_{lang}.qm")):
        app.installTranslator(tr)
        return tr
    return None


def create_window(options: CliOptions, app: QApplication) -> MainWindow:
    settings = InMemorySettingsStore({"network.allowed": True, "ui.theme": ThemeMode.SYSTEM.value})
    theme = ThemeManager(app, ThemeMode(settings.get("ui.theme")))
    registry = SourceRegistry(build_mock_sources())
    return MainWindow(registry, MockFolderIconService(), settings, theme, options.folders)


def append_folders(window: MainWindow, new: list[Path]) -> None:
    """Add folders received from later launches to the target list (no duplicates)."""
    known = {str(p).lower() for p in window.header.folders}
    extra = [p for p in new if str(p).lower() not in known]
    if extra:
        window.header.set_folders([*window.header.folders, *extra])
    window.raise_()
    window.activateWindow()


def run(options: CliOptions) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(PRODUCT_NAME)
    app.setApplicationVersion(FULL_VERSION)
    install_translator(app)
    server = acquire(options.folders)  # single instance: forward folders to a running one
    if server is None:
        return 0
    options = replace(options, folders=tuple(collect_startup_folders(server, options.folders)))
    window = create_window(options, app)
    server.folders_received.connect(lambda new: append_folders(window, new))
    window.show()
    return app.exec()
