import copy
import threading

import pytest

from external_helpers import FakeTransport, fixture_json, home  # noqa: F401
from iconreplacer.catalog.iconify_source import (
    API,
    IconifySource,
    assemble_svgs,
    default_iconify_sources,
    license_text,
)
from iconreplacer.core.contracts import (
    DynamicIconSource,
    IconBytesProvider,
    IconSource,
    SearchableIconSource,
)
from iconreplacer.core.models import CATEGORIES, IconKind, RefKind, SourceState

SEARCH_FOLDER = f"{API}/search?query=folder&limit=999"


def make_transport():
    t = FakeTransport()
    t.add(SEARCH_FOLDER, fixture_json("iconify_search_folder.json"))
    t.add(f"{API}/collection?prefix=ph", fixture_json("iconify_ph_collection.json"))
    t.add(f"{API}/collections?prefixes=ph", fixture_json("iconify_collections_ph.json"))
    return t


def batch_handler(names_seen=None):
    """Answer any ``/{prefix}.json?icons=a,b`` with simple square icons."""

    def handler(url):
        import json

        from iconreplacer.catalog.net import Response

        names = url.split("icons=")[1].split(",")
        if names_seen is not None:
            names_seen.append(names)
        body = {
            "prefix": "x",
            "width": 24,
            "height": 24,
            "icons": {
                n: {"body": '<rect x="2" y="2" width="20" height="20" fill="currentColor"/>'}
                for n in names
            },
        }
        return Response(200, json.dumps(body).encode(), {}, url)

    return handler


def sources(t, **kw):
    iconify, phosphor = default_iconify_sources(transport=t, **kw)
    return iconify, phosphor


def wait_ready(qtbot, src, state=SourceState.READY):
    src.entries()
    qtbot.waitUntil(
        lambda: src.state() is state and bool(src.entries() or state is not SourceState.READY)
    )


def test_protocols_and_ids(home):  # noqa: F811
    iconify, phosphor = sources(FakeTransport())
    for s in (iconify, phosphor):
        for proto in (IconSource, DynamicIconSource, IconBytesProvider):
            assert isinstance(s, proto)
        assert isinstance(s, SearchableIconSource)
    assert (iconify.info.id, phosphor.info.id) == ("iconify", "phosphor")
    assert iconify.info.requires_network and phosphor.info.requires_network


def test_iconify_default_listing_is_folder_search(qtbot, home):  # noqa: F811
    t = make_transport()
    iconify, _ = sources(t)
    wait_ready(qtbot, iconify)
    entries = iconify.entries()
    assert [e.ref.location for e in entries][:2] == ["mdi:folder", "mdi:folder-outline"]
    assert t.calls_matching("/search?query=folder")
    for e in entries:
        assert e.id.startswith("iconify:")
        assert e.ref.kind is RefKind.REMOTE
        assert e.categories and e.categories <= set(CATEGORIES)
    mdi = entries[0]
    assert "Folders" in mdi.categories
    assert "Apache" in mdi.license and "Material Design Icons" in mdi.license


def test_license_mapping_and_glyph_kind(qtbot, home):  # noqa: F811
    t = make_transport()
    iconify, phosphor = sources(t)
    wait_ready(qtbot, iconify)
    wait_ready(qtbot, phosphor)
    assert phosphor.entries()[0].license == "MIT - Phosphor by Phosphor Icons"
    assert all(e.kind is IconKind.GLYPH for e in phosphor.entries())  # palette: false
    assert license_text(None) == "Unknown"
    assert license_text({"name": "X", "license": {"spdx": "MIT"}}) == "MIT - X"


def test_palette_collection_is_full_kind(qtbot, home):  # noqa: F811
    t = FakeTransport()
    data = fixture_json("iconify_search_folder.json")
    data["collections"]["mdi"]["palette"] = True
    t.add(SEARCH_FOLDER, data)
    iconify, _ = sources(t)
    wait_ready(qtbot, iconify)
    by_prefix = {e.ref.location.split(":")[0]: e.kind for e in iconify.entries()}
    assert by_prefix["mdi"] is IconKind.FULL
    assert by_prefix["tabler"] is IconKind.GLYPH


def test_phosphor_lists_regular_weight_only(qtbot, home):  # noqa: F811
    t = make_transport()
    _, phosphor = sources(t)
    wait_ready(qtbot, phosphor)
    names = [e.ref.location for e in phosphor.entries()]
    assert names == [
        "ph:folder",
        "ph:folder-open",
        "ph:arrow-up",
        "ph:airplane",
        "ph:lock",
        "ph:hard-drive",
    ]
    assert not any(n.endswith(("-thin", "-light", "-bold", "-fill", "-duotone")) for n in names)
    assert t.calls_matching("/collection?prefix=ph") and t.calls_matching(
        "/collections?prefixes=ph"
    )


def test_hidden_and_invalid_names_are_dropped(qtbot, home):  # noqa: F811
    t = make_transport()
    t.routes.clear()
    coll = copy.deepcopy(fixture_json("iconify_ph_collection.json"))
    coll["uncategorized"] = ["folder", "lock", "../evil", "Bad Name", "ok-name"]
    coll["hidden"] = ["lock"]
    t.add(f"{API}/collection?prefix=ph", coll)
    t.add(f"{API}/collections?prefixes=ph", fixture_json("iconify_collections_ph.json"))
    _, phosphor = sources(t)
    wait_ready(qtbot, phosphor)
    assert [e.ref.location for e in phosphor.entries()] == ["ph:folder", "ph:ok-name"]


def test_assemble_svgs_uses_json_geometry_and_defaults():
    data = fixture_json("iconify_ph_batch.json")
    svgs = assemble_svgs(data, ["folder", "missing"])
    assert set(svgs) == {"folder"}
    text = svgs["folder"].decode()
    assert 'viewBox="0 0 256 256"' in text and 'width="256"' in text
    assert text.startswith("<svg") and "<path" in text
    # default geometry is 16x16 when the JSON declares none
    plain = assemble_svgs({"icons": {"a": {"body": "<g/>", "left": 1, "top": 2}}}, ["a"])
    assert b'viewBox="1 2 16 16"' in plain["a"]


def test_assemble_svgs_aliases_and_transforms():
    data = {"icons": {"a": {"body": "<g/>"}}, "aliases": {"b": {"parent": "a", "hFlip": True}}}
    svgs = assemble_svgs(data, ["a", "b"])
    assert b"transform" not in svgs["a"] and b"scale(-1 1)" in svgs["b"]


def test_render_placeholder_then_real_image_and_batching(qtbot, home):  # noqa: F811
    t = make_transport()
    seen: list[list[str]] = []
    t.add_handler(f"{API}/ph.json?icons=", batch_handler(seen))
    _, phosphor = sources(t)
    wait_ready(qtbot, phosphor)
    calls = []
    phosphor.subscribe(lambda: calls.append(threading.current_thread()))
    entries = phosphor.entries()
    first = phosphor.render(entries[0], 32)
    assert (first.width(), first.height()) == (32, 32)
    assert first.pixelColor(16, 16).alpha() == 0  # transparent placeholder
    for e in entries[1:4]:
        phosphor.render(e, 32)
    qtbot.waitUntil(lambda: bool(calls), timeout=5000)
    real = phosphor.render(entries[0], 32)
    assert real.pixelColor(16, 16).alpha() == 255
    assert real.pixelColor(16, 16).red() == 0  # currentColor resolved to black
    # thumbnails requested together were fetched in a single batch call
    assert len(seen) == 1 and len(seen[0]) == 4
    # callbacks arrive on the GUI thread
    assert all(th is threading.main_thread() for th in calls)
    # decoded images are memoized
    assert phosphor.render(entries[0], 32) is real


def test_fetch_bytes_returns_svg_and_caches(qtbot, home):  # noqa: F811
    t = make_transport()
    t.add(f"{API}/ph.json?icons=folder", fixture_json("iconify_ph_batch.json"))
    _, phosphor = sources(t)
    wait_ready(qtbot, phosphor)
    entry = phosphor.entries()[0]
    data = phosphor.fetch_bytes(entry)
    assert data.startswith(b"<svg")
    n = len(t.calls)
    assert phosphor.fetch_bytes(entry) == data
    assert len(t.calls) == n  # served from disk cache
    with pytest.raises(ValueError):
        phosphor.fetch_bytes(copy.replace(entry, id="phosphor:ph:forged"))


def test_search_replaces_and_empty_query_restores(qtbot, home):  # noqa: F811
    t = make_transport()
    results = {
        "icons": ["mdi:arrow-up", "mdi:arrow-down"],
        "collections": fixture_json("iconify_search_folder.json")["collections"],
        "total": 2,
    }
    t.add(f"{API}/search?query=arrow%20up&limit=999", results)
    iconify, _ = sources(t)
    wait_ready(qtbot, iconify)
    default = list(iconify.entries())
    iconify.search("arrow up")
    qtbot.waitUntil(lambda: [e.ref.location for e in iconify.entries()] == results["icons"])
    iconify.search("")
    qtbot.waitUntil(lambda: list(iconify.entries()) == default)


def test_phosphor_search_stays_in_collection_and_weight(qtbot, home):  # noqa: F811
    t = make_transport()
    t.add(
        f"{API}/search?query=arrow&limit=999&prefix=ph",
        {"icons": ["ph:arrow-up", "ph:arrow-up-bold", "mdi:arrow-up"], "collections": {}},
    )
    _, phosphor = sources(t)
    wait_ready(qtbot, phosphor)
    phosphor.search("arrow")
    qtbot.waitUntil(lambda: [e.ref.location for e in phosphor.entries()] == ["ph:arrow-up"])


def test_stale_search_result_is_ignored(qtbot, home):  # noqa: F811
    t = make_transport()
    gate = threading.Event()

    def slow(url):
        import json

        from iconreplacer.catalog.net import Response

        gate.wait(5)
        body = {"icons": ["mdi:old"], "collections": {}}
        return Response(200, json.dumps(body).encode(), {}, url)

    t.routes.insert(0, (f"{API}/search?query=old", slow))
    t.add(f"{API}/search?query=new&limit=999", {"icons": ["mdi:new"], "collections": {}})
    iconify, _ = sources(t)
    wait_ready(qtbot, iconify)
    iconify.search("old")
    iconify.search("new")
    qtbot.waitUntil(lambda: [e.ref.location for e in iconify.entries()] == ["mdi:new"])
    gate.set()
    qtbot.wait(200)
    assert [e.ref.location for e in iconify.entries()] == ["mdi:new"]


def test_offline_never_calls_transport_and_serves_cache(qtbot, home):  # noqa: F811
    t = make_transport()
    t.add_handler(f"{API}/ph.json?icons=", batch_handler())
    _, phosphor = sources(t)
    wait_ready(qtbot, phosphor)
    entry = phosphor.entries()[0]
    phosphor.render(entry, 16)
    qtbot.waitUntil(lambda: phosphor.render(entry, 16).pixelColor(8, 8).alpha() == 255)
    expected = [e.id for e in phosphor.entries()]

    t2 = make_transport()
    _, offline = sources(t2, network_allowed=False)
    wait_ready(qtbot, offline, SourceState.OFFLINE)
    qtbot.waitUntil(lambda: bool(offline.entries()))
    assert [e.id for e in offline.entries()] == expected
    assert offline.state() is SourceState.OFFLINE
    assert offline.render(offline.entries()[0], 16).pixelColor(8, 8).alpha() == 255
    offline.refresh()
    qtbot.wait(100)
    assert t2.calls == []
    assert offline.state() is SourceState.OFFLINE


def test_offline_without_cache_has_no_entries(qtbot, home):  # noqa: F811
    t = make_transport()
    iconify, _ = sources(t, network_allowed=False)
    iconify.entries()
    qtbot.wait(100)
    assert iconify.state() is SourceState.OFFLINE and not iconify.entries()
    assert t.calls == []


def test_enabling_network_refreshes(qtbot, home):  # noqa: F811
    t = make_transport()
    _, phosphor = sources(t, network_allowed=False)
    phosphor.entries()
    qtbot.wait(50)
    assert not phosphor.entries()
    phosphor.set_network_allowed(True)
    qtbot.waitUntil(lambda: phosphor.state() is SourceState.READY and bool(phosphor.entries()))


def test_http_error_sets_error_state_and_keeps_entries(qtbot, home):  # noqa: F811
    t = make_transport()
    _, phosphor = sources(t)
    wait_ready(qtbot, phosphor)
    t.clear()
    t.add(f"{API}/collection?prefix=ph", b"", 500)
    phosphor.refresh()
    qtbot.waitUntil(lambda: phosphor.state() is SourceState.ERROR)
    assert "500" in (phosphor.last_error() or "")
    assert phosphor.entries()


def test_garbage_response_is_an_error(qtbot, home):  # noqa: F811
    t = FakeTransport()
    t.add(SEARCH_FOLDER, b"<html>not json</html>")
    iconify, _ = sources(t)
    iconify.entries()
    qtbot.waitUntil(lambda: iconify.state() is SourceState.ERROR)
    assert iconify.last_error()


def test_cache_files_are_hashed(qtbot, home):  # noqa: F811
    import re

    t = make_transport()
    t.add(f"{API}/ph.json?icons=", fixture_json("iconify_ph_batch.json"))
    _, phosphor = sources(t)
    wait_ready(qtbot, phosphor)
    phosphor.fetch_bytes(phosphor.entries()[0])
    files = [f for f in (home / "cache").rglob("*") if f.is_file()]
    assert files and all(re.fullmatch(r"[0-9a-f]{40}\.(bin|json)", f.name) for f in files)


def test_invalid_prefix_rejected():
    with pytest.raises(ValueError):
        IconifySource("x", "X", "", prefix="../etc")
    with pytest.raises(ValueError):
        IconifySource("x", "X", "")
