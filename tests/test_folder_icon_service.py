"""WindowsFolderIconService on folders created under pytest tmp_path only."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
from pathlib import Path

import pytest

from iconreplacer.core.contracts import FolderIconService
from iconreplacer.core.models import (
    ApplyOptions,
    IconEntry,
    IconPayload,
    IconRef,
    RefKind,
)
from iconreplacer.services import win32_shell as w
from iconreplacer.services.folder_icon_service import (
    HISTORY_LIMIT,
    WindowsFolderIconService,
    icon_file_name,
)

SHELL32 = "%SystemRoot%\\System32\\shell32.dll"
OPTS = ApplyOptions()
ENTRY = IconEntry("e", "Entry", "test", IconRef(RefKind.RESOURCE, SHELL32, 4))


def make_ico(rgba: bytes = b"\x10\x20\x30\xff") -> bytes:
    """A valid 1x1 32-bit ICO."""
    bmp = struct.pack("<IiiHHIIiiII", 40, 1, 2, 1, 32, 0, 8, 0, 0, 0, 0) + rgba + b"\0" * 4
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 1, 1, 0, 0, 1, 32, len(bmp), 6 + 16)
    return header + entry + bmp


class FixedMaterializer:
    def __init__(self, payload: IconPayload) -> None:
        self.payload = payload

    def materialize(self, entry, options):
        return self.payload


class RecordingShell(w.Win32Shell):
    def __init__(self, api_fails: bool = False) -> None:
        self.api_fails = api_fails
        self.notified: list[Path] = []
        self.api_calls = 0

    def set_folder_icon(self, folder, icon_file, index):
        self.api_calls += 1
        if self.api_fails:
            raise OSError(0, "simulated API failure")
        super().set_folder_icon(folder, icon_file, index)

    def notify_updated(self, folder):
        self.notified.append(folder)
        super().notify_updated(folder)


@pytest.fixture
def work(tmp_path):
    yield tmp_path
    for root, dirs, files in os.walk(tmp_path):
        for name in dirs + files:
            w.set_attributes(os.path.join(root, name), w.FILE_ATTRIBUTE_NORMAL)
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture
def shell():
    return RecordingShell()


def service(payload: IconPayload, shell: RecordingShell | None = None) -> WindowsFolderIconService:
    return WindowsFolderIconService(FixedMaterializer(payload), shell or RecordingShell())


def resource(rid: int = 4, location: str = SHELL32) -> IconPayload:
    return IconPayload.resource(location, rid)


def folder_in(base: Path, name: str = "Target") -> Path:
    path = base / name
    path.mkdir()
    return path


def tree_state(folder: Path) -> list[tuple]:
    """Names, attributes and bytes of the folder and everything inside it."""
    state = [(".", w.get_attributes(folder) & w.SETTABLE_ATTRIBUTES, None)]
    for root, dirs, files in os.walk(folder):
        for name in sorted(dirs + files):
            p = Path(root, name)
            data = p.read_bytes() if p.is_file() else None
            state.append(
                (str(p.relative_to(folder)), w.get_attributes(p) & w.SETTABLE_ATTRIBUTES, data)
            )
    return sorted(state, key=lambda t: t[0])


def icons(folder: Path) -> list[str]:
    store = folder / ".iconreplacer"
    return sorted(p.name for p in store.glob("*.ico")) if store.is_dir() else []


def ini_text(folder: Path) -> str:
    data = (folder / "desktop.ini").read_bytes()
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16-le")
    return data.decode("ascii")


def has(path: Path, bit: int) -> bool:
    return bool(w.get_attributes(path) & bit)


EXISTING_INI = (
    b"[.ShellClassInfo]\r\n"
    b"LocalizedResourceName=My Stuff\r\n"
    b"IconFile=C:\\old\\legacy.ico\r\n"
    b"IconIndex=2\r\n"
    b"[ViewState]\r\n"
    b"Mode=\r\n"
    b"Vid=\r\n"
    b"FolderType=Pictures\r\n"
)


def seed_ini(folder: Path, data: bytes = EXISTING_INI, attrs: int | None = None) -> None:
    (folder / "desktop.ini").write_bytes(data)
    w.set_attributes(
        folder / "desktop.ini",
        w.FILE_ATTRIBUTE_HIDDEN | w.FILE_ATTRIBUTE_SYSTEM if attrs is None else attrs,
    )


# --------------------------------------------------------------------------- apply


def test_implements_protocol():
    assert isinstance(service(resource()), FolderIconService)


def test_apply_resource_payload(work, shell):
    folder = folder_in(work)
    result = service(resource(), shell).apply([folder], ENTRY, OPTS)
    assert result.ok, result.message
    assert result.message == "Applied to 1 folder."
    assert result.affected == (folder.resolve(),)
    assert not result.simulated
    assert (folder / "desktop.ini").read_bytes() == (
        b"[.ShellClassInfo]\r\nIconResource=%SystemRoot%\\System32\\shell32.dll,-4\r\n"
    )
    assert has(folder / "desktop.ini", w.FILE_ATTRIBUTE_HIDDEN)
    assert has(folder / "desktop.ini", w.FILE_ATTRIBUTE_SYSTEM)
    assert has(folder, w.FILE_ATTRIBUTE_READONLY)
    assert icons(folder) == []
    assert (folder / ".iconreplacer" / "history.json").is_file()
    assert shell.notified == [folder.resolve()]
    assert shell.api_calls == 1


def test_apply_ico_payload(work):
    folder = folder_in(work)
    ico = make_ico()
    assert service(IconPayload.from_ico(ico)).apply([folder], ENTRY, OPTS).ok
    store = folder / ".iconreplacer"
    name = f"icon-{hashlib.sha256(ico).hexdigest()[:12]}.ico"
    assert icon_file_name(ico) == name
    assert icons(folder) == [name]
    assert (store / name).read_bytes() == ico
    assert has(store, w.FILE_ATTRIBUTE_HIDDEN) and has(store, w.FILE_ATTRIBUTE_SYSTEM)
    assert ini_text(folder) == f"[.ShellClassInfo]\r\nIconResource=.iconreplacer\\{name},0\r\n"
    assert [p.name for p in store.iterdir() if p.suffix == ".tmp"] == []


def test_reapplying_different_ico_changes_file_name(work):
    folder = folder_in(work)
    first, second = make_ico(b"\x01\x02\x03\xff"), make_ico(b"\x09\x08\x07\xff")
    service(IconPayload.from_ico(first)).apply([folder], ENTRY, OPTS)
    service(IconPayload.from_ico(second)).apply([folder], ENTRY, OPTS)
    assert icon_file_name(first) != icon_file_name(second)
    assert icons(folder) == [icon_file_name(second)]  # old file removed
    assert f"IconResource=.iconreplacer\\{icon_file_name(second)},0" in ini_text(folder)


def test_ico_reference_survives_moving_the_folder(work):
    folder = folder_in(work)
    service(IconPayload.from_ico(make_ico())).apply([folder], ENTRY, OPTS)
    before = (folder / "desktop.ini").read_bytes()
    moved = work / "elsewhere" / "Moved"
    moved.parent.mkdir()
    os.rename(folder, moved)
    assert (moved / "desktop.ini").read_bytes() == before
    assert len(icons(moved)) == 1


def test_apply_preserves_unrelated_keys_and_drops_legacy_icon_keys(work):
    folder = folder_in(work)
    seed_ini(folder)
    assert service(resource(7)).apply([folder], ENTRY, OPTS).ok
    text = ini_text(folder)
    assert "LocalizedResourceName=My Stuff" in text
    assert "[ViewState]" in text and "FolderType=Pictures" in text
    assert "IconFile" not in text and "IconIndex" not in text
    assert text.count("IconResource=") == 1
    assert "IconResource=%SystemRoot%\\System32\\shell32.dll,-7" in text


def test_apply_keeps_utf16_encoding(work):
    folder = folder_in(work)
    original = "[.ShellClassInfo]\r\nLocalizedResourceName=Fotos ñandú\r\n[ViewState]\r\nMode=\r\n"
    seed_ini(folder, b"\xff\xfe" + original.encode("utf-16-le"))
    assert service(resource()).apply([folder], ENTRY, OPTS).ok
    assert (folder / "desktop.ini").read_bytes().startswith(b"\xff\xfe")
    text = ini_text(folder)
    assert "LocalizedResourceName=Fotos ñandú" in text
    assert "[ViewState]" in text
    assert "IconResource=%SystemRoot%\\System32\\shell32.dll,-4" in text


def test_apply_over_readonly_desktop_ini(work):
    folder = folder_in(work)
    seed_ini(
        folder, attrs=w.FILE_ATTRIBUTE_HIDDEN | w.FILE_ATTRIBUTE_SYSTEM | w.FILE_ATTRIBUTE_READONLY
    )
    before = tree_state(folder)
    svc = service(resource())
    assert svc.apply([folder], ENTRY, OPTS).ok
    assert "IconResource=" in ini_text(folder)
    assert svc.undo([folder]).ok
    assert tree_state(folder) == before


def test_fallback_writer_matches_api_output(work):
    via_api, via_fallback = folder_in(work, "api"), folder_in(work, "fallback")
    seed_ini(via_api)
    seed_ini(via_fallback)
    failing = RecordingShell(api_fails=True)
    assert service(resource()).apply([via_api], ENTRY, OPTS).ok
    assert service(resource(), failing).apply([via_fallback], ENTRY, OPTS).ok
    assert failing.api_calls == 1
    assert (via_fallback / "desktop.ini").read_bytes() == (via_api / "desktop.ini").read_bytes()
    assert has(via_fallback / "desktop.ini", w.FILE_ATTRIBUTE_HIDDEN)
    assert has(via_fallback / "desktop.ini", w.FILE_ATTRIBUTE_SYSTEM)
    assert has(via_fallback, w.FILE_ATTRIBUTE_READONLY)


def test_unicode_folder_and_location_use_utf16(work, shell):
    folder = folder_in(work, "Música 写真 🎵")
    location = str(work / "Iconos ñ" / "pack.dll")
    result = service(resource(12, location), shell).apply([folder], ENTRY, OPTS)
    assert result.ok, result.message
    assert shell.api_calls == 0  # non-ASCII goes straight to our own writer
    assert (folder / "desktop.ini").read_bytes().startswith(b"\xff\xfe")
    assert f"IconResource={location},-12" in ini_text(folder)
    assert service(resource(12, location)).undo([folder]).ok
    assert not (folder / "desktop.ini").exists()


def test_unicode_folder_with_ico(work):
    folder = folder_in(work, "Документы ✓")
    svc = service(IconPayload.from_ico(make_ico()))
    assert svc.apply([folder], ENTRY, OPTS).ok
    assert len(icons(folder)) == 1
    assert svc.restore_default([folder]).ok
    assert list(folder.iterdir()) == []


def test_repeated_apply_is_idempotent(work):
    folder = folder_in(work)
    svc = service(IconPayload.from_ico(make_ico()))
    svc.apply([folder], ENTRY, OPTS)
    first_ini = (folder / "desktop.ini").read_bytes()
    first_icons = icons(folder)
    svc.apply([folder], ENTRY, OPTS)
    assert (folder / "desktop.ini").read_bytes() == first_ini
    assert icons(folder) == first_icons  # same bytes -> same name
    assert (folder / ".iconreplacer" / first_icons[0]).read_bytes() == make_ico()
    assert ini_text(folder).count("IconResource=") == 1


def test_history_is_bounded(work):
    folder = folder_in(work)
    svc = service(resource())
    for _ in range(HISTORY_LIMIT + 3):
        assert svc.apply([folder], ENTRY, OPTS).ok
    history = json.loads((folder / ".iconreplacer" / "history.json").read_text("utf-8"))
    assert len(history["entries"]) == HISTORY_LIMIT
    assert history["owned_attributes"] & w.FILE_ATTRIBUTE_READONLY


def test_failed_write_rolls_back(work, monkeypatch):
    folder = folder_in(work)
    seed_ini(folder)
    before = tree_state(folder)

    def boom(self, *args):
        raise OSError(0, "disk on fire")

    monkeypatch.setattr(WindowsFolderIconService, "_write_ini_fallback", boom)
    result = service(resource(), RecordingShell(api_fails=True)).apply([folder], ENTRY, OPTS)
    assert not result.ok
    assert "disk on fire" in result.message
    assert tree_state(folder) == before


# --------------------------------------------------------------------------- batch


def test_batch_with_refused_and_missing_folders(work):
    a, b = folder_in(work, "A"), folder_in(work, "B")
    root = Path(os.environ.get("SYSTEMDRIVE", "C:") + "\\")
    result = service(resource()).apply([a, root, b, work / "Missing"], ENTRY, OPTS)
    assert not result.ok
    assert result.affected == (a.resolve(), b.resolve())
    assert result.message.startswith("Applied to 2 of 4 folders. Failed: ")
    assert "Drive and share roots are not supported." in result.message
    assert "Missing: The folder does not exist." in result.message
    assert "IconResource=" in ini_text(a) and "IconResource=" in ini_text(b)


def test_empty_selection_and_materializer_error(work):
    assert not service(resource()).apply([], ENTRY, OPTS).ok

    class Broken:
        def materialize(self, entry, options):
            raise ValueError("bad svg")

    result = WindowsFolderIconService(Broken()).apply([folder_in(work)], ENTRY, OPTS)
    assert not result.ok and "bad svg" in result.message
    assert list((work / "Target").iterdir()) == []


# --------------------------------------------------------------------------- undo


def test_undo_first_apply_restores_byte_identical_state(work, shell):
    clean, seeded = folder_in(work, "Clean"), folder_in(work, "Seeded")
    seed_ini(seeded)
    w.set_attributes(seeded, w.FILE_ATTRIBUTE_READONLY)
    before = {f: tree_state(f) for f in (clean, seeded)}
    svc = service(IconPayload.from_ico(make_ico()), shell)
    assert svc.apply([clean, seeded], ENTRY, OPTS).ok
    shell.notified.clear()
    result = svc.undo([clean, seeded])
    assert result.ok and result.message == "Undone on 2 folders."
    for f in (clean, seeded):
        assert tree_state(f) == before[f]
    assert not (clean / ".iconreplacer").exists()
    assert shell.notified == [clean.resolve(), seeded.resolve()]


def test_undo_second_apply_restores_first(work):
    folder = folder_in(work)
    first, second = make_ico(b"\x01\x02\x03\xff"), make_ico(b"\x09\x08\x07\xff")
    service(IconPayload.from_ico(first)).apply([folder], ENTRY, OPTS)
    after_first = tree_state(folder)
    svc = service(IconPayload.from_ico(second))
    svc.apply([folder], ENTRY, OPTS)
    assert icons(folder) == [icon_file_name(second)]
    assert svc.undo([folder]).ok
    assert icons(folder) == [icon_file_name(first)]  # old name and content are back
    assert (folder / ".iconreplacer" / icon_file_name(first)).read_bytes() == first
    assert f"\\{icon_file_name(first)},0" in ini_text(folder)
    state = [t for t in tree_state(folder) if not t[0].endswith("history.json")]
    assert state == [t for t in after_first if not t[0].endswith("history.json")]


def test_undo_resource_after_ico_restores_icon_file(work):
    folder = folder_in(work)
    ico = make_ico()
    service(IconPayload.from_ico(ico)).apply([folder], ENTRY, OPTS)
    svc = service(resource())
    svc.apply([folder], ENTRY, OPTS)
    assert icons(folder) == []
    assert svc.undo([folder]).ok
    assert (folder / ".iconreplacer" / icon_file_name(ico)).read_bytes() == ico
    assert f"{icon_file_name(ico)},0" in ini_text(folder)


def test_nothing_to_undo(work):
    folder = folder_in(work)
    result = service(resource()).undo([folder])
    assert not result.ok
    assert "Nothing to undo." in result.message
    assert list(folder.iterdir()) == []


# --------------------------------------------------------------------------- restore default


def test_restore_default_on_clean_folder_removes_everything(work, shell):
    folder = folder_in(work)
    svc = service(IconPayload.from_ico(make_ico()), shell)
    svc.apply([folder], ENTRY, OPTS)
    svc.apply([folder], ENTRY, OPTS)
    shell.notified.clear()
    result = svc.restore_default([folder])
    assert result.ok and result.message == "Default icon restored on 1 folder."
    assert list(folder.iterdir()) == []
    assert not has(folder, w.FILE_ATTRIBUTE_READONLY)
    assert shell.notified == [folder.resolve()]


def test_restore_default_keeps_other_keys_and_preexisting_readonly(work):
    folder = folder_in(work)
    seed_ini(folder)
    w.set_attributes(folder, w.FILE_ATTRIBUTE_READONLY)
    svc = service(resource())
    svc.apply([folder], ENTRY, OPTS)
    assert svc.restore_default([folder]).ok
    text = ini_text(folder)
    assert "LocalizedResourceName=My Stuff" in text and "[ViewState]" in text
    assert not any(k in text for k in ("IconResource", "IconFile", "IconIndex"))
    assert has(folder / "desktop.ini", w.FILE_ATTRIBUTE_HIDDEN)
    assert has(folder, w.FILE_ATTRIBUTE_READONLY)  # was already set: not ours to clear
    assert not (folder / ".iconreplacer").exists()


def test_restore_default_on_foreign_customization(work):
    folder = folder_in(work)
    seed_ini(folder, b"[.ShellClassInfo]\r\nIconResource=C:\\x.dll,-1\r\n")
    w.set_attributes(folder, w.FILE_ATTRIBUTE_READONLY)
    assert service(resource()).restore_default([folder]).ok
    assert list(folder.iterdir()) == []
    assert has(folder, w.FILE_ATTRIBUTE_READONLY)  # no history: we did not set it
