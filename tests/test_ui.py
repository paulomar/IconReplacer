import time
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from iconreplacer.catalog.mock_source import build_mock_sources
from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.core.contracts import InMemorySettingsStore
from iconreplacer.core.models import IconKind
from iconreplacer.services.mock_folder_service import MockFolderIconService
from iconreplacer.ui.about_dialog import AboutDialog
from iconreplacer.ui.folder_base import compose_on_folder
from iconreplacer.ui.glyphs import render_glyph
from iconreplacer.ui.icon_grid import ENTRY_ROLE, IconGrid
from iconreplacer.ui.main_window import MIN_H, MIN_W, MainWindow
from iconreplacer.ui.preview_panel import PREVIEW_SIZES
from iconreplacer.ui.theme import ThemeManager, ThemeMode
from iconreplacer.version import BUILD, SHORT_VERSION


@pytest.fixture
def window(qtbot):
    def make(folders=(), scale=1.0):
        app = QApplication.instance()
        settings = InMemorySettingsStore({"network.allowed": True})
        theme = ThemeManager(app, ThemeMode.LIGHT)
        reg = SourceRegistry(build_mock_sources(scale))
        svc = MockFolderIconService()
        w = MainWindow(reg, svc, settings, theme, [Path(f) for f in folders])
        qtbot.addWidget(w)
        w.resize(1200, 780)
        w.show()
        qtbot.waitExposed(w)
        return w

    return make


# 4.1 theme + composition -------------------------------------------------------
def test_theme_override_changes_palette(qtbot):
    app = QApplication.instance()
    tm = ThemeManager(app, ThemeMode.LIGHT)
    light = app.palette().color(QPalette.ColorRole.Window)
    tm.apply(ThemeMode.DARK)
    dark = app.palette().color(QPalette.ColorRole.Window)
    assert light != dark
    assert dark.lightness() < light.lightness()
    assert tm.is_dark()


def test_compose_on_folder_returns_requested_size(qtbot):
    for s in (16, 48, 256):
        img = compose_on_folder(render_glyph("Media", s, QColor("white")), s, "#3D8BFD")
        assert (img.width(), img.height()) == (s, s)
        assert not img.isNull()


# 4.2 grid --------------------------------------------------------------------------
def test_combined_filters_and_empty_state(window):
    w = window()
    proxy = w.grid.proxy
    w.sidebar.select_source("shell32.dll")
    w.chips.select("Folders")
    assert proxy.rowCount() > 0
    for r in range(proxy.rowCount()):
        e = proxy.index(r, 0).data(ENTRY_ROLE)
        assert e.source_id == "shell32.dll" and "Folders" in e.categories
    w.search.setText("zzzz-no-match")
    assert proxy.rowCount() == 0
    assert w.grid.is_empty_state()
    w.search.clear()
    assert not w.grid.is_empty_state()


def test_search_matches_tags_case_insensitive(window):
    w = window()
    w.search.setText("NETWORK")
    proxy = w.grid.proxy
    assert proxy.rowCount() > 0
    for r in range(proxy.rowCount()):
        e = proxy.index(r, 0).data(ENTRY_ROLE)
        assert e.matches("network")


def test_thumbnail_size_slider(window):
    w = window()
    w.size_slider.setValue(96)
    assert w.grid.delegate.thumb_size == 96
    assert w.grid.view.iconSize().width() == 96


def test_10k_items_filter_under_300ms(qtbot):
    reg = SourceRegistry(build_mock_sources(scale=4.0))
    grid = IconGrid(lambda e, s: reg.get(e.source_id).render(e, s))
    qtbot.addWidget(grid)
    grid.set_entries(reg.all_entries())
    assert grid.model.rowCount() >= 10_000
    t0 = time.perf_counter()
    grid.proxy.set_search("printer")
    elapsed = time.perf_counter() - t0
    assert grid.visible_count() > 0
    assert elapsed < 0.3, elapsed


# 4.3 sidebar ---------------------------------------------------------------------
def test_sidebar_count_matches_grid(window):
    w = window()
    w.sidebar.select_source("imageres.dll")
    assert w.grid.visible_count() == w.sidebar.count_shown("imageres.dll")


# 4.4 preview -----------------------------------------------------------------------
def test_preview_renders_all_sizes_and_toggle_changes_image(window):
    w = window()
    w.sidebar.select_source("imageres.dll")
    w.grid.select_row(3)
    assert w.preview.entry is not None
    assert sorted(w.preview.rendered) == list(PREVIEW_SIZES)
    for s, img in w.preview.rendered.items():
        assert img.width() == s
    before = w.preview.rendered[64].copy()
    w.preview.compose.setChecked(not w.preview.compose.isChecked())
    assert w.preview.rendered[64] != before
    w.preview.compose.setChecked(True)
    w.preview.set_tint("#34C38F")
    assert w.preview.options().tint == "#34c38f"
    assert w.preview.options().compose_on_folder_base


def test_glyph_icons_default_to_composition(window):
    w = window()
    w.sidebar.select_source("phosphor")
    w.grid.select_row(0)
    assert w.preview.entry.kind is IconKind.GLYPH
    assert w.preview.compose.isChecked()


# 4.5 target header + mocked actions ----------------------------------------------
def test_batch_header_and_simulated_apply(window, tmp_path):
    folders = [tmp_path / n for n in "ABC"]
    for f in folders:
        f.mkdir()
    w = window(folders)
    assert w.header.summary.text() == "3 folders"
    w.header.expand.setChecked(True)
    assert w.header.list.count() == 3
    assert not w.header.apply_btn.isEnabled()  # no selection yet
    w.grid.select_row(0)
    assert w.header.apply_btn.isEnabled()
    w.header.apply_btn.click()
    assert w.banner.isVisibleTo(w)
    assert "Nothing was changed" in w.banner_text.text()
    assert w.service.calls[-1].action == "apply"
    assert sorted(p.name for p in tmp_path.rglob("*")) == ["A", "B", "C"]


def test_no_target_disables_apply(window):
    w = window()
    w.grid.select_row(0)
    assert w.header.summary.text() == "No target folder"
    assert not w.header.apply_btn.isEnabled()


# 4.6 settings + about ------------------------------------------------------------
def test_network_off_greys_online_sources(window):
    w = window()
    w.settings_view.network.setChecked(False)
    assert w.settings_view.source_item("iconify").isDisabled()
    assert w.sidebar._items["iconify"].isDisabled()
    w.sidebar.select_source(None)
    for r in range(w.grid.proxy.rowCount()):
        assert w.grid.proxy.index(r, 0).data(ENTRY_ROLE).source_id not in {
            "iconify",
            "phosphor",
            "gh-windowsicons",
            "gh-folder-icons",
        }


def test_theme_selector_switches_immediately(window):
    w = window()
    app = QApplication.instance()
    before = app.palette().color(QPalette.ColorRole.Window)
    w.settings_view.theme.setCurrentIndex(w.settings_view.theme.findData("dark"))
    assert app.palette().color(QPalette.ColorRole.Window) != before


def test_about_shows_version_and_notices(qtbot):
    dlg = AboutDialog()
    qtbot.addWidget(dlg)
    assert dlg.version_label.text() == f"Version {SHORT_VERSION} (build {BUILD})"
    assert "MIT License" in dlg.license_label.text()
    assert "PySide6" in dlg.notices_text() and "LGPL" in dlg.notices_text()


# 4.7 main window -------------------------------------------------------------------
def test_minimum_size_and_reflow(window, qtbot):
    w = window()
    assert w.minimumSize().width() <= MIN_W and w.minimumSize().height() <= MIN_H
    assert (MIN_W, MIN_H) <= (800, 560)
    w.resize(MIN_W, MIN_H)
    qtbot.wait(50)
    for widget in (w.sidebar, w.grid, w.preview, w.search, w.header.apply_btn):
        assert widget.isVisible() and widget.width() > 0
    narrow = w.grid.columns()
    w.resize(1800, 900)
    qtbot.wait(50)
    assert w.grid.columns() > narrow


# regressions found during visual validation -----------------------------------------
def test_category_chip_shows_literal_ampersand(window):
    w = window()
    assert w.chips.buttons["Drives & Storage"].text() == "Drives && Storage"


def test_glyphs_follow_theme_ink(window):
    w = window()
    w.sidebar.select_source("phosphor")
    entry = w.grid.proxy.index(0, 0).data(ENTRY_ROLE)
    for mode in (ThemeMode.DARK, ThemeMode.LIGHT):
        w.theme.apply(mode)
        img = w._render(entry, 64)
        ink = w.palette().color(QPalette.ColorRole.WindowText)
        opaque = [
            img.pixelColor(x, y)
            for x in range(0, 64, 2)
            for y in range(0, 64, 2)
            if img.pixelColor(x, y).alpha() > 200
        ]
        assert opaque, "glyph has visible pixels"
        assert all(abs(c.lightness() - ink.lightness()) < 30 for c in opaque)


def test_preview_fits_minimum_size_with_scroll(window, qtbot):
    w = window()
    w.resize(MIN_W, MIN_H)
    w.grid.select_row(0)
    qtbot.wait(50)
    big = w.preview.size_labels[256].geometry()
    s128 = w.preview.size_labels[128].mapTo(
        w.preview.scroll.widget(), w.preview.size_labels[128].rect().topLeft()
    )
    assert s128.y() >= big.bottom(), "128 preview must not overlap the 256 preview"
