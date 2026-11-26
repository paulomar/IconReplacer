"""Capture validation screenshots of the UI into docs/screenshots/.

Usage: uv run python tools/screenshots.py
Runs on the real display (not offscreen). Nothing on the system is modified:
- the system icon libraries are only read, and their index cache goes to a temporary home;
- target folders are demo paths and every folder action goes to a simulated service;
- Explorer registration uses an in-memory registry backend;
- settings live in memory only.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from iconreplacer.cli import CliOptions
from iconreplacer.core.contracts import InMemorySettingsStore
from iconreplacer.core.models import ActionResult
from iconreplacer.services.mock_folder_service import MockFolderIconService
from iconreplacer.ui.theme import ThemeMode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
DEMO_FOLDERS = (Path(r"D:\Projects\alpha"), Path(r"D:\Projects\beta"), Path(r"D:\Projects\gamma"))


class DemoService(MockFolderIconService):
    """Simulated service; ``fail_next`` makes the next apply report one refused folder."""

    fail_next = False

    def apply(self, folders, entry, options):
        if not self.fail_next:
            return super().apply(folders, entry, options)
        self.fail_next = False
        *ok, bad = folders
        return ActionResult(
            False,
            f"Applied to {len(ok)} of {len(folders)} folders. Failed: "
            f"{bad.name}: The folder cannot be written.",
            tuple(ok),
            simulated=True,
        )


def main() -> int:
    home = tempfile.mkdtemp(prefix="iconreplacer-shots-")
    os.environ["ICONREPLACER_HOME"] = home  # system index cache goes to a throwaway home
    os.environ.pop("ICONREPLACER_DEMO", None)

    from iconreplacer.app import MemoryRegistryBackend, build_registry, create_window
    from iconreplacer.shell.registration import COMMAND_KEY, VERB_KEY, ShellRegistration

    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    # batch confirmations are answered automatically (the simulated service writes nothing)
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

    backend = MemoryRegistryBackend()
    moved = r"E:\Old\IconReplacer\IconReplacer.exe"
    backend.write_values(VERB_KEY, {"": "Replace Icon", "MUIVerb": "Replace Icon", "Icon": moved})
    backend.write_values(COMMAND_KEY, {"": f'"{moved}" --folder "%1"'})
    settings = InMemorySettingsStore({"network.allowed": True})
    registry = build_registry(settings)
    service = DemoService()
    w = create_window(
        CliOptions(folders=DEMO_FOLDERS),
        app,
        settings,
        registry=registry,
        service=service,
        registration=ShellRegistration(backend),
    )
    w.resize(1440, 900)
    w.show()

    def settle(ms: int = 300) -> None:
        end = QTimer()
        end.setSingleShot(True)
        end.start(ms)
        while end.isActive():
            app.processEvents()

    def shot(name: str, widget=None) -> None:
        settle()
        (widget or w).grab().save(str(OUT / f"{name}.png"))
        print("saved", name)

    def wait_idle() -> None:
        while w.runner.busy:
            app.processEvents()
        settle(100)

    w.resize(1040, 760)
    w.theme.apply(ThemeMode.DARK)
    shot("stale-banner-dark")
    w.hide_banner()

    for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
        w.theme.apply(mode)
        w.tabs.setCurrentIndex(0)
        w.size_slider.setValue(64)
        w.grid.select_row(5)
        shot(f"main-{mode.value}")

    w.set_sources_visible(True)
    w.sidebar.select_source("shell32.dll")
    w.grid.select_row(3)
    shot("sources-panel-dark")
    w.sidebar.select_source("imageres.dll")
    w.set_sources_visible(False)
    w.search.setText("music")
    w.grid.select_row(0)
    w.preview.compose.setChecked(True)
    w.preview.set_tint("#3D8BFD")
    w.header.expand.setChecked(True)
    shot("preview-compose-batch-source-indicator-dark")
    w.header.expand.setChecked(False)
    w.search.clear()
    w.source_pill.close_btn.click()

    w.chips.select("Network")
    w.search.setText("network")
    w.size_slider.setValue(96)
    shot("search-filter-dark")
    w.search.clear()
    w.chips.select(None)
    w.size_slider.setValue(64)

    w.grid.select_row(2)
    w.header.apply_btn.click()
    wait_idle()
    shot("apply-result-dark")

    service.fail_next = True
    w.header.apply_btn.click()
    wait_idle()
    shot("failure-details-dark", w.details_dialog)
    w.details_dialog.close()
    w.hide_banner()

    w.tabs.setCurrentIndex(1)
    w.settings_view.network.setChecked(False)
    shot("settings-network-off-dark")
    w.settings_view.network.setChecked(True)
    w.tabs.setCurrentIndex(0)

    w.resize(800, 560)
    shot("minimum-size-dark")

    about = w.show_about()
    settle(300)
    shot("about-dark", about)
    about.close()
    w.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
