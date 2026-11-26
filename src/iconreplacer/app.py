"""QApplication bootstrap and wiring of the real (or demo) components."""

from __future__ import annotations

import hashlib
import os
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.cli import CliOptions
from iconreplacer.core.contracts import FolderIconService, IconSource, SettingsStore
from iconreplacer.settings import JsonSettingsStore
from iconreplacer.shell.ipc import acquire, collect_startup_folders
from iconreplacer.shell.registration import ShellRegistration
from iconreplacer.ui.main_window import MainWindow
from iconreplacer.ui.settings_view import I18N_DIR
from iconreplacer.ui.theme import ThemeManager, ThemeMode
from iconreplacer.version import FULL_VERSION, PRODUCT_NAME

DEMO_ENV = "ICONREPLACER_DEMO"

ExtraSourcesFactory = Callable[[SettingsStore], list[IconSource]]
LocalSourceFactory = Callable[[Path], IconSource]


def no_extra_sources(_settings: SettingsStore) -> list[IconSource]:
    return []


# Integration hooks. A later change points them at the online/GitHub/local source factories.
extra_sources_factory: ExtraSourcesFactory = no_extra_sources
local_source_factory: LocalSourceFactory | None = None


def demo_mode() -> bool:
    return os.environ.get(DEMO_ENV, "") == "1"


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


# -- demo components (tests and screenshots only) -------------------------------------
class MemoryRegistryBackend:
    """In-memory registry backend: demo mode never touches the real registry."""

    def __init__(self) -> None:
        self.keys: dict[str, dict[str, str]] = {}

    def read_values(self, key: str) -> dict[str, str] | None:
        values = self.keys.get(key.lower())
        return None if values is None else dict(values)

    def write_values(self, key: str, values: dict[str, str]) -> None:
        self.keys.setdefault(key.lower(), {}).update(values)

    def delete_key(self, key: str) -> None:
        self.keys.pop(key.lower(), None)


def demo_local_source(path: Path) -> IconSource:
    from iconreplacer.catalog.mock_source import MockIconSource
    from iconreplacer.core.models import IconKind, Section, SourceInfo

    sid = "local-" + hashlib.blake2s(str(path).lower().encode(), digest_size=4).hexdigest()
    info = SourceInfo(sid, path.name or str(path), str(path), Section.LOCAL, "User provided")
    return MockIconSource(info, ("Folders", "Media", "Documents"), 24, IconKind.FULL, str(path))


# -- real components ---------------------------------------------------------------
def build_registry(
    settings: SettingsStore, extra: ExtraSourcesFactory | None = None
) -> SourceRegistry:
    """System libraries plus the sources supplied by ``extra`` (default: the module hook)."""
    from iconreplacer.catalog.system_source import build_system_sources

    registry = SourceRegistry(build_system_sources())
    for source in (extra or extra_sources_factory)(settings):
        registry.add(source)
    return registry


def build_service(registry: SourceRegistry) -> FolderIconService:
    from iconreplacer.services.folder_icon_service import WindowsFolderIconService
    from iconreplacer.services.materializer import CompositeMaterializer

    return WindowsFolderIconService(CompositeMaterializer(registry))


def create_window(
    options: CliOptions,
    app: QApplication,
    settings: SettingsStore | None = None,
    *,
    registry: SourceRegistry | None = None,
    service: FolderIconService | None = None,
    registration: ShellRegistration | None = None,
    extra_sources: ExtraSourcesFactory | None = None,
    local_factory: LocalSourceFactory | None = None,
) -> MainWindow:
    """Build the main window. Every component can be injected; the rest is real, or demo
    components when ``ICONREPLACER_DEMO=1``."""
    if settings is None:
        settings = JsonSettingsStore()
    theme = ThemeManager(app, ThemeMode(settings.get("ui.theme", ThemeMode.SYSTEM.value)))
    if demo_mode():
        from iconreplacer.catalog.mock_source import build_mock_sources
        from iconreplacer.services.mock_folder_service import MockFolderIconService

        registry = registry or SourceRegistry(build_mock_sources())
        service = service or MockFolderIconService()
        registration = registration or ShellRegistration(MemoryRegistryBackend())
        local_factory = local_factory or demo_local_source
    else:
        registry = registry or build_registry(settings, extra_sources)
        service = service or build_service(registry)
        registration = registration or ShellRegistration()
        local_factory = local_factory or local_source_factory
    return MainWindow(
        registry,
        service,
        settings,
        theme,
        options.folders,
        registration=registration,
        local_source_factory=local_factory,
    )


def append_folders(window: MainWindow, new: list[Path]) -> None:
    """Add folders received from later launches to the target list (no duplicates)."""
    window.header.add_folders(new)
    window.raise_()
    window.activateWindow()


def run(options: CliOptions) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(PRODUCT_NAME)
    app.setApplicationVersion(FULL_VERSION)
    server = acquire(options.folders)  # single instance: forward folders to a running one
    if server is None:
        return 0
    settings = JsonSettingsStore()
    install_translator(app, settings.get("ui.language", ""))
    options = replace(options, folders=tuple(collect_startup_folders(server, options.folders)))
    window = create_window(options, app, settings)
    server.folders_received.connect(lambda new: append_folders(window, new))
    app.aboutToQuit.connect(settings.save)
    window.show()
    return app.exec()
