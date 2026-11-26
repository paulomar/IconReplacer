import json
import logging
import os

import pytest

from iconreplacer.core import paths
from iconreplacer.core.contracts import SettingsStore
from iconreplacer.settings import SPECS, JsonSettingsStore


@pytest.fixture
def file(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path))
    paths.reset_cache()
    yield tmp_path / "settings.json"
    paths.reset_cache()


def test_default_path_and_protocol(file):
    store = JsonSettingsStore()
    assert store.path == file
    assert isinstance(store, SettingsStore)


def test_defaults(file):
    s = JsonSettingsStore(file)
    assert s.get("network.allowed") is True
    assert s.get("ui.theme") == "system"
    assert s.get("ui.language") == ""
    assert s.get("ui.sources_visible") is False
    assert s.get("ui.window_geometry") is None
    assert s.get("ui.thumb_size") == 48
    assert s.get("sources.disabled") == []
    assert s.get("sources.local_folders") == []
    assert s.get("nope", 7) == 7
    assert not file.exists()
    s.get("sources.disabled").append("x")
    assert s.get("sources.disabled") == []  # defaults are not shared


def test_round_trip(file):
    s = JsonSettingsStore(file)
    s.set("ui.theme", "dark")
    s.set("ui.thumb_size", 96)
    s.set("sources.disabled", ["a", "b"])
    s.set("ui.window_geometry", "AAEC")
    doc = json.loads(file.read_text(encoding="utf-8"))
    assert doc["version"] == 1
    again = JsonSettingsStore(file)
    assert again.get("ui.theme") == "dark"
    assert again.get("ui.thumb_size") == 96
    assert again.get("sources.disabled") == ["a", "b"]
    assert again.get("ui.window_geometry") == "AAEC"


def test_invalid_stored_values_fall_back(file, caplog):
    bad = {
        "ui.thumb_size": 9999,
        "ui.theme": "purple",
        "network.allowed": "yes",
        "ui.window_geometry": "!!notbase64",
        "sources.local_folders": ["relative/path"],
    }
    file.write_text(json.dumps({"version": 1, "values": bad}), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        s = JsonSettingsStore(file)
    for key in bad:
        assert s.get(key) == SPECS[key].default
    assert len(caplog.records) >= len(bad)


def test_invalid_set_rejected(file, caplog):
    s = JsonSettingsStore(file)
    with caplog.at_level(logging.WARNING):
        s.set("ui.thumb_size", 5)
    assert s.get("ui.thumb_size") == 48
    assert caplog.records


def test_unknown_keys_preserved(file):
    file.write_text(
        json.dumps({"version": 1, "values": {"future.key": {"a": 1}}}), encoding="utf-8"
    )
    s = JsonSettingsStore(file)
    s.set("ui.theme", "light")
    doc = json.loads(file.read_text(encoding="utf-8"))
    assert doc["values"]["future.key"] == {"a": 1}
    assert doc["values"]["ui.theme"] == "light"


def test_atomic_write_failure_keeps_old_file(file, monkeypatch, caplog):
    s = JsonSettingsStore(file)
    s.set("ui.theme", "dark")
    before = file.read_text(encoding="utf-8")

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with caplog.at_level(logging.WARNING):
        s.set("ui.theme", "light")  # must not raise
    monkeypatch.undo()
    assert file.read_text(encoding="utf-8") == before
    assert json.loads(before)["values"]["ui.theme"] == "dark"
    assert [p.name for p in file.parent.iterdir()] == ["settings.json"]  # no temp leftovers


@pytest.mark.parametrize("content", [b"{not json", b"[]", b'{"version":1,"values":3}', b"\xff\xfe"])
def test_corrupt_file_recovery(file, content):
    file.write_bytes(content)
    s = JsonSettingsStore(file)
    assert s.get("ui.theme") == "system"
    assert not file.exists()
    backups = list(file.parent.glob("settings.json.corrupt-*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == content
    s.set("ui.theme", "dark")
    assert JsonSettingsStore(file).get("ui.theme") == "dark"
