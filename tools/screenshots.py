"""Capture validation screenshots of the UI prototype into docs/screenshots/.

Usage: uv run python tools/screenshots.py
Runs on the real display (not offscreen). Nothing on the system is modified.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from iconreplacer.cli import CliOptions
from iconreplacer.ui.theme import ThemeMode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
DEMO_FOLDERS = (Path(r"D:\Projects\alpha"), Path(r"D:\Projects\beta"), Path(r"D:\Projects\gamma"))


def main() -> int:
    from iconreplacer.app import create_window

    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    w = create_window(CliOptions(folders=DEMO_FOLDERS), app)
    w.resize(1440, 900)
    w.show()

    def settle(ms: int = 250) -> None:
        end = QTimer()
        end.setSingleShot(True)
        end.start(ms)
        while end.isActive():
            app.processEvents()

    def shot(name: str, widget=None) -> None:
        settle()
        (widget or w).grab().save(str(OUT / f"{name}.png"))
        print("saved", name)

    w.resize(1040, 760)
    for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
        w.theme.apply(mode)
        w.tabs.setCurrentIndex(0)
        w.size_slider.setValue(64)
        w.grid.select_row(5)
        shot(f"main-{mode.value}")

    w.set_sources_visible(True)
    w.sidebar.select_source("imageres.dll")
    w.grid.select_row(5)
    shot("sources-panel-dark")
    w.sidebar.select_source("phosphor")
    w.set_sources_visible(False)
    w.grid.select_row(2)
    w.preview.set_tint("#3D8BFD")
    w.header.expand.setChecked(True)
    shot("preview-compose-batch-source-indicator-dark")
    w.header.expand.setChecked(False)
    w.source_pill.close_btn.click()

    w.chips.select("Network")
    w.search.setText("wifi")
    w.size_slider.setValue(96)
    shot("search-filter-dark")
    w.search.clear()
    w.chips.select(None)

    w.grid.select_row(0)
    w.header.apply_btn.click()
    shot("simulated-apply-dark")

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
