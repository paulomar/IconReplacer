from __future__ import annotations

import pytest

from converter_fixtures import SVG_GLYPH, solid
from iconreplacer.converter import ConversionError, ConverterMaterializer
from iconreplacer.core.contracts import IconMaterializer
from iconreplacer.core.models import (
    ApplyOptions,
    IconEntry,
    IconKind,
    IconRef,
    PayloadKind,
    RefKind,
)


@pytest.fixture(autouse=True)
def _app(qapp):
    return qapp


def entry(kind: RefKind, icon_kind: IconKind = IconKind.GLYPH) -> IconEntry:
    ref = (
        IconRef(RefKind.RESOURCE, "imageres.dll", 3)
        if kind is RefKind.RESOURCE
        else IconRef(kind, "x.svg")
    )
    return IconEntry("e", "Entry", "src", ref, kind=icon_kind)


def mat(render=True) -> ConverterMaterializer:
    return ConverterMaterializer(
        lambda e: SVG_GLYPH, (lambda e, size: solid(size, "black")) if render else None
    )


def test_satisfies_contract():
    assert isinstance(mat(), IconMaterializer)


@pytest.mark.parametrize("compose", [False, True])
def test_file_and_remote_entries_give_ico(compose):
    for kind in (RefKind.FILE, RefKind.REMOTE):
        p = mat().materialize(entry(kind), ApplyOptions(compose_on_folder_base=compose))
        assert p.kind is PayloadKind.ICO and p.ico


def test_resource_in_place_without_compose():
    p = mat(render=False).materialize(entry(RefKind.RESOURCE), ApplyOptions())
    assert p.kind is PayloadKind.RESOURCE
    assert (p.location, p.resource_id) == ("imageres.dll", 3)


def test_resource_composed_is_ico():
    opts = ApplyOptions(compose_on_folder_base=True)
    p = mat().materialize(entry(RefKind.RESOURCE), opts)
    assert p.kind is PayloadKind.ICO
    q = mat().materialize(entry(RefKind.RESOURCE, IconKind.FULL), opts)
    assert q.kind is PayloadKind.ICO and q.ico != p.ico


def test_resource_compose_without_render_provider_fails():
    with pytest.raises(ConversionError):
        mat(render=False).materialize(
            entry(RefKind.RESOURCE), ApplyOptions(compose_on_folder_base=True)
        )
