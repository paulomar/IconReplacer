import dataclasses
from pathlib import Path

import pytest

from iconreplacer.catalog.mock_source import SYSTEM_LIBRARIES, build_mock_sources
from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.core.contracts import FolderIconService, IconSource, InMemorySettingsStore
from iconreplacer.core.models import (
    CATEGORIES,
    ApplyOptions,
    IconEntry,
    IconRef,
    RefKind,
    Section,
)
from iconreplacer.services.mock_folder_service import MockFolderIconService

REQUIRED_LIBS = {
    "imageres.dll",
    "shell32.dll",
    "ddores.dll",
    "wmploc.dll",
    "mmres.dll",
    "netshell.dll",
    "networkexplorer.dll",
    "pnidui.dll",
    "wpdshext.dll",
    "wiashext.dll",
    "setupapi.dll",
    "dmdskres.dll",
    "dsuiext.dll",
    "accessibilitycpl.dll",
    "sensorscpl.dll",
    "powercpl.dll",
    "mstscax.dll",
    "ieframe.dll",
    "mmcndmgr.dll",
    "compstui.dll",
    "pifmgr.dll",
    "moricons.dll",
}


def _entry(**kw):
    base = dict(
        id="x:1",
        name="Folder Blue",
        source_id="x",
        ref=IconRef(RefKind.RESOURCE, "lib.dll", 1234),
        tags=frozenset({"network"}),
    )
    base.update(kw)
    return IconEntry(**base)


def test_models_are_immutable_and_comparable():
    e = _entry()
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.name = "other"  # type: ignore[misc]
    assert e == _entry()
    assert hash(e) == hash(_entry())


def test_entry_matching_name_tag_and_id():
    e = _entry()
    assert e.matches("FOLDER")
    assert e.matches("netw")
    assert e.matches("1234")
    assert not e.matches("printer")
    assert e.matches("  ")


def test_mock_sources_cover_required_libraries():
    sources = build_mock_sources()
    names = {s.info.name.lower() for s in sources if s.info.section is Section.SYSTEM}
    assert names == REQUIRED_LIBS
    assert {s.info.section for s in sources} == {Section.SYSTEM, Section.ONLINE, Section.LOCAL}


def test_per_source_counts_and_categories_valid():
    reg = SourceRegistry(build_mock_sources())
    spec = {lib.file.lower(): lib.count for lib in SYSTEM_LIBRARIES}
    for sid, count in spec.items():
        assert reg.count(sid) == count
    for e in reg.all_entries():
        assert e.categories, e.id
        assert e.categories <= set(CATEGORIES), e.categories
    ids = [e.id for e in reg.all_entries()]
    assert len(ids) == len(set(ids))


def test_scaled_catalog_reaches_10k():
    reg = SourceRegistry(build_mock_sources(scale=4.0))
    assert len(reg.all_entries()) >= 10_000


def test_registry_rejects_duplicates_and_network_gating():
    sources = build_mock_sources()
    reg = SourceRegistry(sources)
    with pytest.raises(ValueError):
        reg.add(sources[0])
    assert reg.is_available("iconify", network_allowed=True)
    assert not reg.is_available("iconify", network_allowed=False)
    assert reg.is_available("imageres.dll", network_allowed=False)
    reg.set_enabled("imageres.dll", False)
    assert not reg.is_available("imageres.dll", network_allowed=True)


def test_contracts_are_satisfied():
    assert isinstance(build_mock_sources()[0], IconSource)
    assert isinstance(MockFolderIconService(), FolderIconService)
    s = InMemorySettingsStore({"a": 1})
    s.set("b", 2)
    assert (s.get("a"), s.get("b"), s.get("c", 3)) == (1, 2, 3)


def _snapshot(root: Path):
    return {
        p: (p.stat().st_mtime_ns, p.stat().st_size, p.stat().st_file_attributes)
        for p in [root, *root.rglob("*")]
    }


def test_mock_service_is_descriptive_and_touches_nothing(tmp_path):
    folders = [tmp_path / "A", tmp_path / "B"]
    for f in folders:
        f.mkdir()
        (f / "file.txt").write_text("x")
    before = _snapshot(tmp_path)
    svc = MockFolderIconService()
    e = _entry()
    r = svc.apply(folders, e, ApplyOptions(compose_on_folder_base=True))
    assert r.ok and r.simulated and "2 folders" in r.message and e.name in r.message
    assert svc.undo(folders).ok
    assert svc.restore_default(folders).ok
    assert not svc.apply([], e, ApplyOptions()).ok
    assert [c.action for c in svc.calls] == ["apply", "undo", "restore"]
    assert _snapshot(tmp_path) == before
    assert not any(p.name.lower() == "desktop.ini" for p in tmp_path.rglob("*"))
