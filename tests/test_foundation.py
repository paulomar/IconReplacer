import os
from pathlib import Path

import pytest

from iconreplacer.core import paths
from iconreplacer.core.contracts import IconMaterializer
from iconreplacer.core.models import ApplyOptions, IconEntry, IconPayload, PayloadKind

ICO = b"\x00\x00\x01\x00" + b"\x00" * 18


@pytest.fixture(autouse=True)
def _fresh_paths(monkeypatch):
    monkeypatch.delenv(paths.ENV_HOME, raising=False)
    paths.reset_cache()
    yield
    paths.reset_cache()


def test_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path / "home"))
    assert paths.data_root() == tmp_path / "home"
    assert not (tmp_path / "home").exists()  # nothing created until needed
    assert paths.settings_path() == tmp_path / "home" / "settings.json"
    assert paths.cache_dir("iconify") == tmp_path / "home" / "cache" / "iconify"
    assert (tmp_path / "home" / "cache" / "iconify").is_dir()


def test_portable_when_app_dir_writable(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "app_dir", lambda: tmp_path)
    assert paths.data_root() == tmp_path / "data"
    assert sorted(os.listdir(tmp_path)) == []  # probe file removed


def test_localappdata_when_read_only(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "app_dir", lambda: tmp_path / "app")
    (tmp_path / "app").mkdir()
    monkeypatch.setattr(paths, "_is_writable", lambda d: False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert paths.data_root() == tmp_path / "local" / "IconReplacer"
    assert paths.cache_dir() == tmp_path / "local" / "IconReplacer" / "cache"


@pytest.mark.parametrize("bad", ["", "..", "a/b", r"a\b", "c:"])
def test_cache_name_validation(monkeypatch, tmp_path, bad):
    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path))
    with pytest.raises(ValueError):
        paths.cache_dir(bad)


def test_dev_app_dir_is_repo_root():
    assert (paths.app_dir() / "pyproject.toml").is_file()


def test_payload_validation():
    r = IconPayload.resource(r"%SystemRoot%\System32\imageres.dll", 3)
    assert r.kind is PayloadKind.RESOURCE
    assert IconPayload.from_ico(ICO).kind is PayloadKind.ICO
    with pytest.raises(ValueError):
        IconPayload.resource("x.dll", 0)
    with pytest.raises(ValueError):
        IconPayload.from_ico(b"")
    with pytest.raises(ValueError):
        IconPayload.from_ico(b"\x89PNG....")
    with pytest.raises(ValueError):
        IconPayload(PayloadKind.RESOURCE, location="x.dll", resource_id=1, ico=ICO)


def test_materializer_protocol():
    class Stub:
        def materialize(self, entry: IconEntry, options: ApplyOptions) -> IconPayload:
            return IconPayload.from_ico(ICO)

    assert isinstance(Stub(), IconMaterializer)


def test_gitignore_covers_data_and_worktrees():
    text = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "data/" in text and ".worktrees/" in text
