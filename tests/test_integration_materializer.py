"""CompositeMaterializer: routes entries through their own source (no folder I/O)."""

from __future__ import annotations

import pytest

from converter_fixtures import SVG_GLYPH, solid
from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.converter import ConversionError
from iconreplacer.core import paths
from iconreplacer.core.contracts import IconBytesProvider, IconMaterializer
from iconreplacer.core.models import (
    ApplyOptions,
    IconEntry,
    IconKind,
    IconRef,
    PayloadKind,
    RefKind,
    Section,
    SourceInfo,
)
from iconreplacer.services.materializer import CompositeMaterializer

SHELL32 = "%SystemRoot%\\System32\\shell32.dll"


@pytest.fixture(autouse=True)
def _app(qapp):
    return qapp


class StubSource:
    def __init__(self, sid: str, kind: RefKind) -> None:
        self._info = SourceInfo(sid, sid, "stub", Section.ONLINE)
        ref = IconRef(kind, SHELL32, 4) if kind is RefKind.RESOURCE else IconRef(kind, "a.svg")
        self.entry = IconEntry(f"{sid}:1", "One", sid, ref, kind=IconKind.GLYPH)
        self.rendered: list[int] = []

    @property
    def info(self) -> SourceInfo:
        return self._info

    def entries(self):
        return [self.entry]

    def render(self, entry, size):
        self.rendered.append(size)
        return solid(size, "black")


class StubBytesSource(StubSource):
    def __init__(self, sid: str, data: bytes | Exception = SVG_GLYPH) -> None:
        super().__init__(sid, RefKind.REMOTE)
        self.data = data
        self.fetched = 0

    def fetch_bytes(self, entry) -> bytes:
        self.fetched += 1
        if isinstance(self.data, Exception):
            raise self.data
        return self.data


def test_contract_and_resource_in_place():
    src = StubSource("res", RefKind.RESOURCE)
    mat = CompositeMaterializer(SourceRegistry([src]))
    assert isinstance(mat, IconMaterializer)
    p = mat.materialize(src.entry, ApplyOptions())
    assert p.kind is PayloadKind.RESOURCE
    assert (p.location, p.resource_id) == (SHELL32, 4)
    assert src.rendered == []  # referenced in place, no pixels needed


def test_resource_composed_renders_through_source():
    src = StubSource("res", RefKind.RESOURCE)
    p = CompositeMaterializer(SourceRegistry([src])).materialize(
        src.entry, ApplyOptions(compose_on_folder_base=True, tint="#3D8BFD")
    )
    assert p.kind is PayloadKind.ICO and p.ico
    assert src.rendered  # pixels came from the source's render()


@pytest.mark.parametrize("compose", [False, True])
def test_bytes_provider_is_converted(compose):
    src = StubBytesSource("web")
    assert isinstance(src, IconBytesProvider)
    p = CompositeMaterializer(SourceRegistry([src])).materialize(
        src.entry, ApplyOptions(compose_on_folder_base=compose)
    )
    assert p.kind is PayloadKind.ICO and p.ico
    assert src.fetched == 1


def test_non_resource_without_bytes_provider_fails():
    src = StubSource("plain", RefKind.REMOTE)
    with pytest.raises(ConversionError, match="cannot provide image data"):
        CompositeMaterializer(SourceRegistry([src])).materialize(src.entry, ApplyOptions())


def test_fetch_error_and_unknown_source_are_typed():
    src = StubBytesSource("web", OSError("offline"))
    mat = CompositeMaterializer(SourceRegistry([src]))
    with pytest.raises(ConversionError, match="offline"):
        mat.materialize(src.entry, ApplyOptions())
    stray = IconEntry("x", "X", "missing", IconRef(RefKind.REMOTE, "x"))
    with pytest.raises(ConversionError, match="unknown icon source"):
        mat.materialize(stray, ApplyOptions())
    bad = StubBytesSource("bad", b"not an image")
    with pytest.raises(ConversionError):
        CompositeMaterializer(SourceRegistry([bad])).materialize(bad.entry, ApplyOptions())


def test_real_system_icon_composed(tmp_path, monkeypatch):
    from iconreplacer.catalog.system_source import build_system_sources, system_libraries

    monkeypatch.setenv(paths.ENV_HOME, str(tmp_path))
    paths.reset_cache()
    try:
        libs = [lib for lib in system_libraries() if lib.file == "shell32.dll"]
        sources = build_system_sources(libs)
        if not sources:
            pytest.skip("shell32.dll not available")
        src = sources[0]
        entry = src.entries()[0]
        mat = CompositeMaterializer(SourceRegistry(sources))
        plain = mat.materialize(entry, ApplyOptions())
        assert plain.kind is PayloadKind.RESOURCE
        assert plain.location == entry.ref.location
        composed = mat.materialize(entry, ApplyOptions(compose_on_folder_base=True))
        assert composed.kind is PayloadKind.ICO
        src.close()
    finally:
        paths.reset_cache()
