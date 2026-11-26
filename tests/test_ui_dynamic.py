"""Generic DynamicIconSource / SearchableIconSource support in the main window (stubs only)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from iconreplacer.catalog.mock_source import build_mock_sources
from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.core.contracts import (
    DynamicIconSource,
    InMemorySettingsStore,
    SearchableIconSource,
)
from iconreplacer.core.models import IconEntry, IconRef, RefKind, Section, SourceInfo, SourceState
from iconreplacer.services.mock_folder_service import MockFolderIconService
from iconreplacer.ui.icon_grid import ENTRY_ROLE
from iconreplacer.ui.main_window import SEARCH_DEBOUNCE_MS, MainWindow
from iconreplacer.ui.theme import ThemeManager, ThemeMode


class StubDynamic:
    """Dynamic + searchable source driven by the test."""

    def __init__(self, sid: str = "dyn", searchable: bool = True) -> None:
        self._info = SourceInfo(sid, sid.title(), "stub", Section.ONLINE, requires_network=True)
        self._entries: list[IconEntry] = []
        self._subs: list = []
        self._state = SourceState.LOADING
        self._error: str | None = None
        self.network_calls: list[bool] = []
        self.refreshes = 0
        self.searches: list[str] = []
        self.color = QColor("red")
        if not searchable:
            self.search = None  # type: ignore[assignment]

    @property
    def info(self) -> SourceInfo:
        return self._info

    def entries(self):
        return list(self._entries)

    def render(self, entry, size):
        img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(self.color)
        return img

    def state(self) -> SourceState:
        return self._state

    def last_error(self):
        return self._error

    def subscribe(self, callback):
        self._subs.append(callback)
        return lambda: self._subs.remove(callback)

    def refresh(self) -> None:
        self.refreshes += 1

    def set_network_allowed(self, allowed: bool) -> None:
        self.network_calls.append(allowed)

    def search(self, query: str) -> None:
        self.searches.append(query)

    # -- test helpers
    def publish(self, names, state=SourceState.READY, error=None) -> None:
        sid = self._info.id
        self._entries = [
            IconEntry(f"{sid}:{n}", n, sid, IconRef(RefKind.REMOTE, f"{sid}/{n}")) for n in names
        ]
        self._state, self._error = state, error
        for cb in list(self._subs):
            cb()


@pytest.fixture
def make(qtbot):
    def build(*dynamic, network=True):
        reg = SourceRegistry([*build_mock_sources(0.05), *dynamic])
        w = MainWindow(
            reg,
            MockFolderIconService(),
            InMemorySettingsStore({"network.allowed": network}),
            ThemeManager(QApplication.instance(), ThemeMode.LIGHT),
            [Path("C:/demo-does-not-exist")],
        )
        qtbot.addWidget(w)
        w.show()
        qtbot.waitExposed(w)
        return w

    return build


def ids_in_grid(w) -> set[str]:
    return {w.grid.proxy.index(r, 0).data(ENTRY_ROLE).id for r in range(w.grid.proxy.rowCount())}


def test_stub_matches_protocols():
    s = StubDynamic()
    assert isinstance(s, DynamicIconSource) and isinstance(s, SearchableIconSource)


def test_subscribe_updates_grid_counts_and_badges(qtbot, make):
    dyn = StubDynamic()
    w = make(dyn)
    assert dyn._subs, "window subscribed"
    qtbot.waitUntil(lambda: dyn.refreshes == 1)  # loaded when the window opens
    assert dyn.network_calls == [True]
    assert w.sidebar.badge("dyn") == "Loading…"
    total = w.grid.visible_count()

    dyn.publish(["alpha", "beta"])
    qtbot.waitUntil(lambda: "dyn:alpha" in ids_in_grid(w))
    assert w.grid.visible_count() == total + 2
    assert w.sidebar.count_shown("dyn") == 2
    assert w.sidebar.badge("dyn") == ""

    dyn.publish(["alpha", "beta"], SourceState.ERROR, "HTTP 503")
    qtbot.waitUntil(lambda: w.sidebar.badge("dyn") == "Error")
    assert "HTTP 503" in w.sidebar._items["dyn"].toolTip(0)

    dyn.publish(["alpha", "beta"], SourceState.OFFLINE)
    qtbot.waitUntil(lambda: w.sidebar.badge("dyn") == "Offline")
    w.close()
    assert dyn._subs == []  # unsubscribed on close


def test_thumbnail_refresh_keeps_selection(qtbot, make):
    dyn = StubDynamic()
    w = make(dyn)
    dyn.publish(["alpha"])
    qtbot.waitUntil(lambda: "dyn:alpha" in ids_in_grid(w))
    w.sidebar.select_source("dyn")
    w.grid.select_row(0)
    assert w.preview.entry.id == "dyn:alpha"
    before = w.preview.rendered[64].pixelColor(32, 32)
    dyn.color = QColor("blue")  # "pixels arrived"
    dyn.publish(["alpha", "gamma"])
    qtbot.waitUntil(lambda: w.sidebar.count_shown("dyn") == 2)
    assert w.preview.entry is not None and w.preview.entry.id == "dyn:alpha"
    assert w.preview.rendered[64].pixelColor(32, 32) != before
    pm = w.grid.delegate.pixmap(w.preview.entry, 48).toImage()
    assert pm.pixelColor(24, 24).blue() > 200


def test_network_switch_forwarded(qtbot, make):
    dyn = StubDynamic()
    w = make(dyn)
    qtbot.waitUntil(lambda: dyn.refreshes == 1)
    w.settings_view.network.setChecked(False)
    assert dyn.network_calls[-1] is False
    assert dyn.refreshes == 1
    w.settings_view.network.setChecked(True)
    assert dyn.network_calls[-1] is True
    assert dyn.refreshes == 2


def test_disabled_source_not_refreshed_until_enabled(qtbot, make):
    from PySide6.QtCore import Qt

    dyn = StubDynamic()
    w = make(dyn)
    qtbot.waitUntil(lambda: dyn.refreshes == 1)
    item = w.settings_view.source_item("dyn")
    item.setCheckState(0, Qt.CheckState.Unchecked)
    w.settings_view.network.setChecked(False)
    w.settings_view.network.setChecked(True)
    assert dyn.refreshes == 1  # disabled: not reloaded
    item.setCheckState(0, Qt.CheckState.Checked)
    assert dyn.refreshes == 2


def test_search_debounced_on_selected_searchable_source(qtbot, make):
    dyn = StubDynamic()
    w = make(dyn)
    dyn.publish(["alpha", "beta"])
    qtbot.waitUntil(lambda: "dyn:alpha" in ids_in_grid(w))
    w.sidebar.select_source("dyn")
    for text in ("a", "ar", "arr", "arro", "arrow"):
        w.search.setText(text)
    assert dyn.searches == []
    qtbot.wait(SEARCH_DEBOUNCE_MS // 2)
    assert dyn.searches == []
    qtbot.waitUntil(lambda: dyn.searches == ["arrow"], timeout=2000)
    # remote results are not filtered again by the local text match
    dyn.publish(["upward", "downward"])
    qtbot.waitUntil(lambda: ids_in_grid(w) == {"dyn:upward", "dyn:downward"})
    qtbot.wait(SEARCH_DEBOUNCE_MS + 100)
    assert dyn.searches == ["arrow"]  # no duplicate query
    # leaving the source restores its default listing
    w.sidebar.select_source(None)
    assert dyn.searches == ["arrow", ""]


def test_all_sources_never_query_remotely(qtbot, make):
    dyn = StubDynamic()
    w = make(dyn)
    dyn.publish(["alpha"])
    qtbot.waitUntil(lambda: "dyn:alpha" in ids_in_grid(w))
    w.search.setText("alp")
    qtbot.wait(SEARCH_DEBOUNCE_MS + 150)
    assert dyn.searches == []
    assert "dyn:alpha" in ids_in_grid(w)  # local filtering still applies
    w.search.setText("zzz")
    assert "dyn:alpha" not in ids_in_grid(w)


def test_unavailable_searchable_source_is_not_queried(qtbot, make):
    dyn = StubDynamic()
    w = make(dyn, network=False)
    w.sidebar.select_source("dyn")
    w.search.setText("arrow")
    qtbot.wait(SEARCH_DEBOUNCE_MS + 150)
    assert dyn.searches == []
