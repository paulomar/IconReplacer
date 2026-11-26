import ctypes
import os
import shutil
import sys
import threading
from pathlib import Path

import pytest

from converter_fixtures import SVG_COLOR, colour_icon_png
from iconreplacer.catalog import local_source
from iconreplacer.catalog.local_source import LocalFolderSource, local_source_id
from iconreplacer.core.contracts import DynamicIconSource, IconBytesProvider, IconSource
from iconreplacer.core.models import IconKind, RefKind, Section, SourceState

DLL = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "SystemResources" / "moricons.dll.mun"
needs_dll = pytest.mark.skipif(
    sys.platform != "win32" or not DLL.is_file(),
    reason="needs a small Windows icon resource file (.mun)",
)


def make_tree(root: Path) -> None:
    (root / "sub" / "deep").mkdir(parents=True)
    (root / "a.png").write_bytes(colour_icon_png(64))
    (root / "Folder_Icon.svg").write_bytes(SVG_COLOR)
    (root / "sub" / "b.png").write_bytes(colour_icon_png(32))
    (root / "sub" / "deep" / "c.png").write_bytes(colour_icon_png(32))
    (root / "notes.txt").write_text("ignore", "utf-8")


def scan(qtbot, src, state=SourceState.READY):
    src.refresh()
    qtbot.waitUntil(lambda: src.state() is state, timeout=10000)
    return src.entries()


def test_protocols_info_and_no_network(tmp_path):
    src = LocalFolderSource(tmp_path)
    for proto in (IconSource, DynamicIconSource, IconBytesProvider):
        assert isinstance(src, proto)
    assert src.info.section is Section.LOCAL and not src.info.requires_network
    assert src.info.id == local_source_id(tmp_path) and src.info.id.startswith("local-")
    src.set_network_allowed(False)
    assert src.state() is not SourceState.OFFLINE


def test_scans_images_recursively(qtbot, tmp_path):
    make_tree(tmp_path)
    src = LocalFolderSource(tmp_path)
    entries = scan(qtbot, src)
    names = sorted(Path(e.ref.location).name for e in entries)
    assert names == ["Folder_Icon.svg", "a.png", "b.png", "c.png"]
    for e in entries:
        assert e.ref.kind is RefKind.FILE and Path(e.ref.location).is_absolute()
        assert e.kind is IconKind.FULL and e.categories
    svg = next(e for e in entries if e.ref.location.endswith(".svg"))
    assert svg.name == "Folder Icon" and "Folders" in svg.categories
    assert src.last_error() is None


def test_render_placeholder_then_real_and_fetch_bytes(qtbot, tmp_path):
    make_tree(tmp_path)
    src = LocalFolderSource(tmp_path)
    entry = next(e for e in scan(qtbot, src) if e.ref.location.endswith("a.png"))
    calls = []
    src.subscribe(lambda: calls.append(threading.current_thread()))
    first = src.render(entry, 32)
    assert first.pixelColor(16, 16).alpha() == 0
    qtbot.waitUntil(lambda: bool(calls))
    real = src.render(entry, 32)
    assert real.pixelColor(16, 16).alpha() == 255
    assert all(t is threading.main_thread() for t in calls)
    assert src.fetch_bytes(entry) == Path(entry.ref.location).read_bytes()


def test_svg_renders_as_vector(qtbot, tmp_path):
    make_tree(tmp_path)
    src = LocalFolderSource(tmp_path)
    entry = next(e for e in scan(qtbot, src) if e.ref.location.endswith(".svg"))
    src.render(entry, 128)
    qtbot.waitUntil(lambda: src.render(entry, 128).pixelColor(30, 64).alpha() == 255)
    big = src.render(entry, 128)
    assert big.pixelColor(30, 64).red() > 200  # red half of the SVG at the requested size


def test_depth_limit(qtbot, tmp_path):
    d = tmp_path
    for level in range(1, 7):
        d = d / f"l{level}"
        d.mkdir()
        (d / f"f{level}.png").write_bytes(colour_icon_png(16))
    (tmp_path / "root.png").write_bytes(colour_icon_png(16))
    entries = scan(qtbot, LocalFolderSource(tmp_path))
    names = sorted(Path(e.ref.location).name for e in entries)
    # root (depth 0) + folders l1..l4 are scanned; l5 and l6 are beyond MAX_DEPTH
    assert names == ["f1.png", "f2.png", "f3.png", "f4.png", "root.png"]


def test_file_limit(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(local_source, "MAX_FILES", 5)
    data = colour_icon_png(16)
    for i in range(12):
        (tmp_path / f"i{i:02d}.png").write_bytes(data)
    src = LocalFolderSource(tmp_path)
    assert len(scan(qtbot, src)) == 5 and src.truncated


def test_hidden_and_system_items_are_skipped(qtbot, tmp_path):
    if sys.platform != "win32":
        pytest.skip("Windows attributes")
    data = colour_icon_png(16)
    (tmp_path / "ok.png").write_bytes(data)
    (tmp_path / "hid.png").write_bytes(data)
    (tmp_path / "sys.png").write_bytes(data)
    (tmp_path / "hdir").mkdir()
    (tmp_path / "hdir" / "inside.png").write_bytes(data)
    set_attr = ctypes.windll.kernel32.SetFileAttributesW
    assert set_attr(str(tmp_path / "hid.png"), 0x2)
    assert set_attr(str(tmp_path / "sys.png"), 0x4)
    assert set_attr(str(tmp_path / "hdir"), 0x2)
    names = [Path(e.ref.location).name for e in scan(qtbot, LocalFolderSource(tmp_path))]
    assert names == ["ok.png"]


def test_symlinks_and_junctions_are_skipped(qtbot, tmp_path):
    if sys.platform != "win32":
        pytest.skip("Windows reparse points")
    import subprocess

    target = tmp_path / "target"
    target.mkdir()
    (target / "t.png").write_bytes(colour_icon_png(16))
    root = tmp_path / "root"
    root.mkdir()
    (root / "r.png").write_bytes(colour_icon_png(16))
    res = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(root / "junction"), str(target)],
        capture_output=True,
        check=False,
    )
    if res.returncode != 0:
        pytest.skip("cannot create junction")
    names = [Path(e.ref.location).name for e in scan(qtbot, LocalFolderSource(root))]
    assert names == ["r.png"]


@needs_dll
def test_icon_library_entries_are_resources(qtbot, tmp_path):
    copy = tmp_path / "icons.dll"
    shutil.copy(DLL, copy)
    (tmp_path / "a.png").write_bytes(colour_icon_png(16))
    src = LocalFolderSource(tmp_path)
    entries = scan(qtbot, src)
    res = [e for e in entries if e.ref.kind is RefKind.RESOURCE]
    assert res and any(e.ref.kind is RefKind.FILE for e in entries)
    for e in res:
        assert e.ref.location == str(copy) and e.ref.resource_id and e.ref.resource_id > 0
    assert len({e.id for e in entries}) == len(entries)
    ico = src.fetch_bytes(res[0])
    assert ico[:4] == b"\x00\x00\x01\x00"
    src.render(res[0], 32)
    qtbot.waitUntil(lambda: src.render(res[0], 32).pixelColor(16, 16).alpha() == 255)


def test_corrupt_library_is_ignored(qtbot, tmp_path):
    (tmp_path / "bad.dll").write_bytes(b"MZ not a real pe")
    (tmp_path / "a.png").write_bytes(colour_icon_png(16))
    entries = scan(qtbot, LocalFolderSource(tmp_path))
    assert [Path(e.ref.location).name for e in entries] == ["a.png"]


def test_missing_folder_is_error(qtbot, tmp_path):
    src = LocalFolderSource(tmp_path / "nope")
    scan(qtbot, src, SourceState.ERROR)
    assert src.last_error() and not src.entries()


def test_undecodable_file_stays_placeholder(qtbot, tmp_path):
    (tmp_path / "broken.png").write_bytes(b"not an image")
    src = LocalFolderSource(tmp_path)
    entry = scan(qtbot, src)[0]
    src.render(entry, 16)
    qtbot.wait(150)
    assert src.render(entry, 16).pixelColor(8, 8).alpha() == 0


def test_forged_entry_is_rejected(qtbot, tmp_path):
    import copy

    make_tree(tmp_path)
    src = LocalFolderSource(tmp_path)
    entry = scan(qtbot, src)[0]
    forged = copy.replace(entry, id="local-x:evil")
    with pytest.raises(ValueError):
        src.fetch_bytes(forged)
