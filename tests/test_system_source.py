import json
import sys
import time

import pytest

from iconreplacer.catalog.system_source import (
    LICENSE,
    LibraryInfo,
    SystemIconSource,
    build_system_sources,
    curated_icons,
    system_libraries,
)
from iconreplacer.core import paths
from iconreplacer.core.contracts import IconSource
from iconreplacer.core.models import CATEGORIES, ICO_MAGIC, IconPayload, RefKind, Section

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="needs Windows system DLLs")


@pytest.fixture(autouse=True)
def _home(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path / "home"))
    paths.reset_cache()
    yield tmp_path / "home"
    paths.reset_cache()


def _lib(name: str) -> LibraryInfo:
    return next(lib for lib in system_libraries() if lib.file == name)


@pytest.fixture
def imageres():
    with SystemIconSource(_lib("imageres.dll")) as src:
        yield src


def test_missing_library_has_no_entries(tmp_path):
    fake = LibraryInfo("nope.dll", "Not a library", ("System",), ("System",))
    src = SystemIconSource(fake, path=tmp_path / "nope.dll", mun_path=tmp_path / "nope.mun")
    assert isinstance(src, IconSource)
    assert not src.available
    assert src.entries() == ()
    assert build_system_sources([fake]) == []
    assert len(build_system_sources([fake], include_missing=True)) == 1


def test_source_info():
    src = SystemIconSource(_lib("shell32.dll"))
    assert src.info.id == "shell32.dll"
    assert src.info.name == "shell32.dll"
    assert src.info.section is Section.SYSTEM
    assert src.info.license == LICENSE


@windows_only
@pytest.mark.parametrize("lib", ["imageres.dll", "shell32.dll"])
def test_entries_reference_system32_by_positive_unique_id(lib):
    with SystemIconSource(_lib(lib)) as src:
        entries = src.entries()
    assert len(entries) > 300
    ids = [e.ref.resource_id for e in entries]
    assert all(isinstance(i, int) and i > 0 for i in ids)
    assert len(ids) == len(set(ids))
    for e in entries:
        assert e.ref.kind is RefKind.RESOURCE
        assert e.ref.location == f"%SystemRoot%\\System32\\{lib}"
        assert e.source_id == lib
        assert e.license == LICENSE
        assert e.categories and e.categories <= set(CATEGORIES)
        assert lib in e.tags and str(e.ref.resource_id) in e.tags
        IconPayload.resource(e.ref.location, e.ref.resource_id)  # valid for desktop.ini


@windows_only
def test_curated_and_default_classification(imageres):
    by_id = {e.ref.resource_id: e for e in imageres.entries()}
    curated = curated_icons()["imageres.dll"]
    hits = [rid for rid in curated if rid in by_id]
    assert len(hits) >= 100
    for rid in hits:
        assert by_id[rid].name == curated[rid].name
        assert by_id[rid].categories == frozenset(curated[rid].categories)
    assert "Folders" in by_id[3].categories

    with SystemIconSource(_lib("ddores.dll")) as dd:
        entry = dd.entries()[0]
    assert entry.name == f"ddores.dll #{entry.ref.resource_id}"
    assert entry.categories == {"Devices"}


@windows_only
def test_search_matches_curated_name(imageres):
    hits = [e for e in imageres.entries() if e.matches("recycle bin")]
    assert hits


@windows_only
@pytest.mark.parametrize("size", [16, 24, 32, 48, 64, 100, 256])
def test_render_exact_size(qapp, imageres, size):
    from PySide6.QtGui import QColor

    entry = next(e for e in imageres.entries() if e.ref.resource_id == 3)
    img = imageres.render(entry, size)
    assert not img.isNull()
    assert (img.width(), img.height()) == (size, size)
    centre = QColor(img.pixelColor(size // 2, size // 2))
    assert centre.alpha() > 0  # the folder covers the centre


@windows_only
def test_render_classic_bitmap_icon(qapp):
    # moricons.dll holds classic 16-colour BMP icons (no PNG payloads).
    with SystemIconSource(_lib("moricons.dll")) as src:
        entry = src.entries()[0]
        assert max(src.available_sizes(entry)) <= 48
        img = src.render(entry, 64)
    assert (img.width(), img.height()) == (64, 64)
    opaque = sum(img.pixelColor(x, y).alpha() > 0 for x in range(64) for y in range(64))
    assert opaque > 100


@windows_only
def test_render_foreign_entry_is_rejected(qapp, imageres):
    with SystemIconSource(_lib("shell32.dll")) as other:
        foreign = other.entries()[0]
    with pytest.raises(ValueError):
        imageres.extract_ico_bytes(foreign)


@windows_only
def test_extract_ico_bytes_parse_back(qapp):
    from PySide6.QtGui import QImage

    with SystemIconSource(_lib("shell32.dll")) as src:
        entry = next(e for e in src.entries() if e.ref.resource_id == 4)
        data = src.extract_ico_bytes(entry)
        assert src.extract_ico_bytes(entry) is data  # LRU hit
        sizes = src.available_sizes(entry)
        assert src.content_hash(entry)
    assert data.startswith(ICO_MAGIC)
    assert int.from_bytes(data[4:6], "little") >= len(sizes)
    assert not QImage.fromData(data, "ICO").isNull()


@windows_only
def test_close_then_render_reopens(qapp, imageres):
    entry = imageres.entries()[0]
    imageres.close()
    assert not imageres.render(entry, 32).isNull()


@windows_only
def test_cache_cold_warm_equivalent_and_fast(_home):
    lib = _lib("imageres.dll")
    t0 = time.perf_counter()
    with SystemIconSource(lib) as cold:
        cold_entries = cold.entries()
    cold_s = time.perf_counter() - t0
    assert not cold.loaded_from_cache
    assert cold_s < 1.5
    assert (_home / "cache" / "system" / "imageres.dll.json").is_file()

    t0 = time.perf_counter()
    with SystemIconSource(lib) as warm:
        warm_entries = warm.entries()
    warm_s = time.perf_counter() - t0
    assert warm.loaded_from_cache
    assert warm_entries == cold_entries
    assert warm_s < 0.1
    assert warm._module is None  # warm start does not even map the library


@windows_only
def test_stale_or_corrupt_cache_is_rebuilt(_home):
    lib = _lib("powercpl.dll")
    with SystemIconSource(lib) as src:
        reference = src.entries()
    cache_file = _home / "cache" / "system" / "powercpl.dll.json"

    raw = json.loads(cache_file.read_text("utf-8"))
    raw["key"]["file"][2] += 1  # pretend the DLL's mtime changed
    raw["items"] = []
    cache_file.write_text(json.dumps(raw), "utf-8")
    with SystemIconSource(lib) as src:
        assert src.entries() == reference
        assert not src.loaded_from_cache

    cache_file.write_text("{not json", "utf-8")
    with SystemIconSource(lib) as src:
        assert src.entries() == reference
        assert not src.loaded_from_cache
    with SystemIconSource(lib) as src:
        assert src.entries() == reference
        assert src.loaded_from_cache


@windows_only
def test_no_cache_mode_writes_nothing(_home):
    with SystemIconSource(_lib("powercpl.dll"), use_cache=False) as src:
        assert src.entries()
    assert not (_home / "cache" / "system" / "powercpl.dll.json").exists()


@windows_only
def test_build_system_sources_lists_present_libraries():
    sources = build_system_sources()
    names = {s.info.name for s in sources}
    assert {"imageres.dll", "shell32.dll", "moricons.dll"} <= names
    for s in sources:
        assert s.available
        assert len(s.entries()) > 0
        s.close()
