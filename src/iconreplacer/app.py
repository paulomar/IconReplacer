"""QApplication bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from iconreplacer.catalog.mock_source import build_mock_sources
from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.cli import CliOptions
from iconreplacer.core.contracts import SettingsStore
from iconreplacer.services.mock_folder_service import MockFolderIconService
from iconreplacer.settings import JsonSettingsStore
from iconreplacer.ui.main_window import MainWindow
from iconreplacer.ui.settings_view import I18N_DIR
from iconreplacer.ui.theme import ThemeManager, ThemeMode
from iconreplacer.version import FULL_VERSION, PRODUCT_NAME


def resolve_language(setting: str = "", i18n_dir: Path = I18N_DIR) -> str:
    """Language code to load. Empty setting follows the system locale if a .qm exists."""
    if setting:
        return setting
    system = QLocale.system().name().split("_")[0]
    if system and (i18n_dir / f"iconreplacer_{system}.qm").is_file():
        return system
    return "en"


def install_translator(
    app: QApplication, language: str | None = None, i18n_dir: Path = I18N_DIR
) -> QTranslator | None:
    """Load a compiled translation if available. English is built in (source strings)."""
    lang = resolve_language(language or "", i18n_dir)
    if lang == "en":
        return None
    tr = QTranslator(app)
    if tr.load(str(i18n_dir / f"iconreplacer_{lang}.qm")):
        app.installTranslator(tr)
        return tr
    return None


def create_window(
    options: CliOptions, app: QApplication, settings: SettingsStore | None = None
) -> MainWindow:
    if settings is None:
        settings = JsonSettingsStore()
    theme = ThemeManager(app, ThemeMode(settings.get("ui.theme", ThemeMode.SYSTEM.value)))
    registry = SourceRegistry(build_mock_sources())
    return MainWindow(registry, MockFolderIconService(), settings, theme, options.folders)


def run(options: CliOptions) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(PRODUCT_NAME)
    app.setApplicationVersion(FULL_VERSION)
    settings = JsonSettingsStore()
    install_translator(app, settings.get("ui.language", ""))
    window = create_window(options, app, settings)
    app.aboutToQuit.connect(settings.save)
    window.show()
    return app.exec()
