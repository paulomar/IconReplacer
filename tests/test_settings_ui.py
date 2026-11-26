import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from iconreplacer.app import create_window, install_translator, resolve_language
from iconreplacer.cli import CliOptions
from iconreplacer.core import paths
from iconreplacer.settings import JsonSettingsStore
from iconreplacer.ui.main_window import geometry_fits

TS = Path(__file__).resolve().parents[1] / "src" / "iconreplacer" / "i18n" / "iconreplacer_en.ts"


@pytest.fixture
def store_path(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path))
    monkeypatch.setenv("ICONREPLACER_DEMO", "1")  # mock catalog, simulated service, fake registry
    paths.reset_cache()
    yield paths.settings_path()
    paths.reset_cache()


def _make(qtbot, store):
    w = create_window(CliOptions(), QApplication.instance(), store)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


def test_preferences_survive_restart(qtbot, store_path):
    store = JsonSettingsStore(store_path)
    w1 = _make(qtbot, store)
    w1.settings_view.theme.setCurrentIndex(w1.settings_view.theme.findData("dark"))
    w1.set_sources_visible(True)
    w1.size_slider.setValue(96)
    w1.settings_view.network.setChecked(False)
    item = w1.settings_view.source_item(w1.registry.sources()[0].info.id)
    item.setCheckState(0, item.checkState(0).Unchecked)
    disabled_id = w1.registry.sources()[0].info.id
    w1.close()

    store2 = JsonSettingsStore(store_path)  # a fresh process reads the file
    w2 = _make(qtbot, store2)
    assert w2.theme.is_dark()
    assert w2.settings_view.theme.currentData() == "dark"
    assert w2.sources_visible()
    assert w2.sources_btn.isChecked()
    assert w2.size_slider.value() == 96
    assert not w2.settings_view.network_allowed()
    assert not w2.registry.is_enabled(disabled_id)
    assert w2.settings_view.source_item(disabled_id).checkState(0).name == "Unchecked"
    assert store2.get("ui.window_geometry")


def test_geometry_restored_and_garbage_ignored(qtbot, store_path):
    store = JsonSettingsStore(store_path)
    w1 = _make(qtbot, store)
    w1.resize(820 - 20, 700)
    size = w1.size()
    w1.close()
    w2 = _make(qtbot, JsonSettingsStore(store_path))
    assert w2.size() == size

    bad = JsonSettingsStore(store_path)
    bad.set("ui.window_geometry", "AAECAwQF")  # valid base64, not a geometry blob
    w3 = _make(qtbot, bad)
    assert w3.width() >= 800 and w3.height() >= 560


def test_geometry_fits():
    screens = [QRect(0, 0, 1920, 1080)]
    assert geometry_fits(QRect(100, 100, 1000, 700), screens)
    assert geometry_fits(QRect(-800, 100, 1000, 700), screens)  # 200 px still visible
    assert not geometry_fits(QRect(5000, 5000, 1000, 700), screens)
    assert not geometry_fits(QRect(-900, 100, 1000, 700), screens)  # only 100 px visible


def test_local_folders_persisted(qtbot, store_path, tmp_path):
    store = JsonSettingsStore(store_path)
    w1 = _make(qtbot, store)
    folder = tmp_path / "icons"
    w1.add_local_folder(folder)
    w1.close()
    w2 = _make(qtbot, JsonSettingsStore(store_path))
    assert any(s.info.description == str(folder) for s in w2.registry.sources())


def test_language_change_shows_note_and_persists(qtbot, store_path):
    store = JsonSettingsStore(store_path)
    w = _make(qtbot, store)
    view = w.settings_view
    assert not view.language_note.isVisibleTo(view)
    assert view.language.itemData(0) == ""  # follow system
    view.language.addItem("Deutsch", "de")  # simulates an available translation
    view.language.setCurrentIndex(view.language.findData("de"))
    assert view.language_note.isVisibleTo(view)
    assert "Restart IconReplacer" in view.language_note.text()
    assert JsonSettingsStore(store_path).get("ui.language") == "de"
    view.language.setCurrentIndex(0)
    assert not view.language_note.isVisibleTo(view)


def test_resolve_language(tmp_path):
    assert resolve_language("de", tmp_path) == "de"
    assert resolve_language("", tmp_path) == "en"  # no .qm available
    from PySide6.QtCore import QLocale

    system = QLocale.system().name().split("_")[0]
    (tmp_path / f"iconreplacer_{system}.qm").write_bytes(b"")
    assert resolve_language("", tmp_path) == system
    assert install_translator(QApplication.instance(), "en", tmp_path) is None


def test_template_messages_non_empty_and_new_strings_present():
    root = ET.parse(TS).getroot()
    found: dict[str, set[str]] = {}
    for ctx in root.iter("context"):
        found[ctx.findtext("name")] = set()
        for m in ctx.iter("message"):
            src = m.findtext("source")
            assert src and src.strip()
            found[ctx.findtext("name")].add(src)
    assert "Restart IconReplacer to apply the language" in found["SettingsView"]
    assert "System default" in found["SettingsView"]
