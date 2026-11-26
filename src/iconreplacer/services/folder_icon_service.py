"""Real Windows FolderIconService: desktop.ini + attributes, with history and undo.

Per folder layout::

    <folder>\\desktop.ini                 [.ShellClassInfo] IconResource=...
    <folder>\\.iconreplacer\\icon-<sha256[:12]>.ico  generated icon (ICO payloads only)
    <folder>\\.iconreplacer\\history.json  bounded snapshots for undo
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from iconreplacer.core.contracts import IconMaterializer
from iconreplacer.core.models import (
    ActionResult,
    ApplyOptions,
    IconEntry,
    IconPayload,
    PayloadKind,
)
from iconreplacer.services import win32_shell as w
from iconreplacer.services.folder_safety import UnsafeFolderError, check_folder

DESKTOP_INI = "desktop.ini"
STORE_DIR = ".iconreplacer"
ICON_PATTERN = "icon-*.ico"
ICON_HASH_CHARS = 12
HISTORY_NAME = "history.json"
HISTORY_LIMIT = 10
HISTORY_VERSION = 1
SHELL_SECTION = ".ShellClassInfo"
ICON_KEYS = ("IconResource", "IconFile", "IconIndex")
LEGACY_ICON_KEYS = ("IconFile", "IconIndex")
OWNABLE_FOLDER_BITS = w.FILE_ATTRIBUTE_READONLY | w.FILE_ATTRIBUTE_SYSTEM

_UTF16_BOM = b"\xff\xfe"
_UTF8_BOM = b"\xef\xbb\xbf"


class FolderIconError(Exception):
    """A folder action could not be performed; ``str(exc)`` is a short English reason."""


# --------------------------------------------------------------------------- desktop.ini


class IniDocument:
    """Line-preserving INI editor that keeps the original encoding where possible."""

    def __init__(self, lines: list[str], encoding: str) -> None:
        self.lines = lines
        self.encoding = encoding  # "utf-16" | "utf-8-sig" | "ansi"

    @classmethod
    def parse(cls, data: bytes | None) -> IniDocument:
        if not data:
            return cls([], "ansi")
        if data.startswith(_UTF16_BOM):
            return cls(data[2:].decode("utf-16-le").splitlines(keepends=True), "utf-16")
        if data.startswith(_UTF8_BOM):
            return cls(data[3:].decode("utf-8").splitlines(keepends=True), "utf-8-sig")
        try:
            text = data.decode("ascii")
        except UnicodeDecodeError:
            try:
                text = data.decode("mbcs")
            except (UnicodeDecodeError, LookupError):
                text = data.decode("latin-1")
        return cls(text.splitlines(keepends=True), "ansi")

    @property
    def text(self) -> str:
        return "".join(self.lines)

    def to_bytes(self) -> bytes:
        text = self.text
        if self.encoding == "ansi" and not text.isascii():
            self.encoding = "utf-16"  # Explorer reads Unicode desktop.ini as UTF-16 LE
        if self.encoding == "utf-16":
            return _UTF16_BOM + text.encode("utf-16-le")
        if self.encoding == "utf-8-sig":
            return _UTF8_BOM + text.encode("utf-8")
        return text.encode("ascii")

    # -- parsing helpers
    @staticmethod
    def _section_name(line: str) -> str | None:
        s = line.strip()
        if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
            return s[1:-1].strip()
        return None

    @staticmethod
    def _key_name(line: str) -> str | None:
        s = line.strip()
        if not s or s[0] in ";#" or "=" not in s:
            return None
        return s.split("=", 1)[0].strip()

    def _newline(self) -> str:
        return "\n" if self.lines and not any("\r\n" in ln for ln in self.lines) else "\r\n"

    def _section_span(self, section: str) -> tuple[int, int] | None:
        """(header index, end index exclusive) of the first matching section."""
        wanted = section.casefold()
        start = None
        for i, line in enumerate(self.lines):
            name = self._section_name(line)
            if name is None:
                continue
            if start is not None:
                return start, i
            if name.casefold() == wanted:
                start = i
        return None if start is None else (start, len(self.lines))

    def get(self, section: str, key: str) -> str | None:
        span = self._section_span(section)
        if span is None:
            return None
        for line in self.lines[span[0] + 1 : span[1]]:
            name = self._key_name(line)
            if name is not None and name.casefold() == key.casefold():
                return line.split("=", 1)[1].strip()
        return None

    def set(self, section: str, key: str, value: str) -> None:
        nl = self._newline()
        entry = f"{key}={value}"
        span = self._section_span(section)
        if span is None:
            if self.lines and not self.lines[-1].endswith(("\n", "\r")):
                self.lines[-1] += nl
            self.lines += [f"[{section}]{nl}", f"{entry}{nl}"]
            return
        start, end = span
        matches = [
            i
            for i in range(start + 1, end)
            if (self._key_name(self.lines[i]) or "").casefold() == key.casefold()
        ]
        if matches:
            first = matches[0]
            line = self.lines[first]
            self.lines[first] = entry + (line[len(line.rstrip("\r\n")) :] or nl)
            for i in reversed(matches[1:]):  # drop duplicate keys
                del self.lines[i]
            return
        keys = [i for i in range(start + 1, end) if self._key_name(self.lines[i]) is not None]
        last = keys[-1] if keys else start
        if not self.lines[last].endswith(("\n", "\r")):
            self.lines[last] += nl
        self.lines.insert(last + 1, f"{entry}{nl}")

    def remove(self, section: str, keys: Sequence[str]) -> bool:
        """Remove ``keys`` from ``section``; drop the section if it has no keys left."""
        span = self._section_span(section)
        if span is None:
            return False
        start, end = span
        wanted = {k.casefold() for k in keys}
        body = self.lines[start + 1 : end]
        kept = [ln for ln in body if (self._key_name(ln) or "").casefold() not in wanted]
        if len(kept) == len(body):
            return False
        if any(self._key_name(ln) is not None for ln in kept):
            self.lines[start + 1 : end] = kept
        else:
            del self.lines[start:end]
        return True

    def has_keys(self) -> bool:
        return any(self._key_name(ln) is not None for ln in self.lines)


# --------------------------------------------------------------------------- history


def _b64(data: bytes | None) -> str | None:
    return None if data is None else base64.b64encode(data).decode("ascii")


def _unb64(text: str | None) -> bytes | None:
    return None if text is None else base64.b64decode(text)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Exact state of a folder before a change."""

    desktop_ini: bytes | None
    desktop_ini_attributes: int | None
    folder_attributes: int
    icons: tuple[tuple[str, bytes], ...]  # (file name, bytes) of stored icon-*.ico files
    store_existed: bool

    def to_json(self) -> dict:
        data = asdict(self)
        data["desktop_ini"] = _b64(self.desktop_ini)
        data["icons"] = {name: _b64(blob) for name, blob in self.icons}
        return data

    @classmethod
    def from_json(cls, data: dict) -> Snapshot:
        return cls(
            desktop_ini=_unb64(data["desktop_ini"]),
            desktop_ini_attributes=data["desktop_ini_attributes"],
            folder_attributes=int(data["folder_attributes"]),
            icons=tuple(sorted((str(n), base64.b64decode(b)) for n, b in data["icons"].items())),
            store_existed=bool(data["store_existed"]),
        )


@dataclass(slots=True)
class History:
    entries: list[Snapshot]
    owned_attributes: int = 0  # folder bits IconReplacer turned on

    @classmethod
    def load(cls, store: Path) -> History:
        path = store / HISTORY_NAME
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            entries = [Snapshot.from_json(e) for e in raw.get("entries", [])]
            return cls(entries, int(raw.get("owned_attributes", 0)))
        except FileNotFoundError:
            return cls([])
        except (ValueError, KeyError, TypeError, binascii.Error):
            return cls([])  # unreadable history: start over rather than fail the folder

    def save(self, store: Path) -> None:
        self.entries = self.entries[-HISTORY_LIMIT:]
        payload = {
            "version": HISTORY_VERSION,
            "owned_attributes": self.owned_attributes,
            "entries": [e.to_json() for e in self.entries],
        }
        _atomic_write(store / HISTORY_NAME, json.dumps(payload, indent=1).encode("utf-8"))


# --------------------------------------------------------------------------- file helpers


def _read_optional(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def icon_file_name(ico: bytes) -> str:
    """Content-addressed name, so Explorer's path-keyed icon cache sees a new file."""
    return f"icon-{hashlib.sha256(ico).hexdigest()[:ICON_HASH_CHARS]}.ico"


def _icon_files(store: Path) -> list[Path]:
    return sorted(store.glob(ICON_PATTERN)) if store.is_dir() else []


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


class _Files:
    """File operations that need attribute handling, bound to a shell facade."""

    def __init__(self, shell: w.Win32Shell) -> None:
        self.shell = shell

    def attrs_or_none(self, path: Path) -> int | None:
        return self.shell.get_attributes(path) if path.exists() else None

    def unlink(self, path: Path) -> None:
        if path.exists():
            self.shell.set_attributes(path, w.FILE_ATTRIBUTE_NORMAL)
            path.unlink()

    def write(self, path: Path, data: bytes, attributes: int | None) -> None:
        if path.exists():
            self.shell.set_attributes(path, w.FILE_ATTRIBUTE_NORMAL)
        _atomic_write(path, data)
        if attributes is not None:
            self.shell.set_attributes(path, attributes)

    def remove_tree(self, root: Path) -> None:
        if not root.exists():
            return
        for current, dirs, files in os.walk(root):
            for name in dirs + files:
                self.shell.set_attributes(Path(current, name), w.FILE_ATTRIBUTE_NORMAL)
        self.shell.set_attributes(root, w.FILE_ATTRIBUTE_NORMAL)
        shutil.rmtree(root)

    def ensure_store(self, store: Path) -> None:
        if not store.is_dir():
            store.mkdir()
            self.shell.set_attributes(store, w.FILE_ATTRIBUTE_HIDDEN | w.FILE_ATTRIBUTE_SYSTEM)

    def set_folder_bits(self, folder: Path, keep_mask: int, bits: int) -> None:
        current = self.shell.get_attributes(folder)
        wanted = (current & keep_mask) | bits
        if wanted & w.SETTABLE_ATTRIBUTES != current & w.SETTABLE_ATTRIBUTES:
            self.shell.set_attributes(folder, wanted)


# --------------------------------------------------------------------------- service


class WindowsFolderIconService:
    """``FolderIconService`` that really customizes folders (never elevated)."""

    def __init__(self, materializer: IconMaterializer, shell: w.Win32Shell | None = None) -> None:
        self._materializer = materializer
        self._shell = shell or w.Win32Shell()
        self._files = _Files(self._shell)

    # -- public API
    def apply(
        self, folders: Sequence[Path], entry: IconEntry, options: ApplyOptions
    ) -> ActionResult:
        if not folders:
            return ActionResult(False, "No target folder.")
        try:
            payload = self._materializer.materialize(entry, options)
        except Exception as exc:  # materializers are pluggable; keep the UI alive
            return ActionResult(False, f"The icon could not be prepared: {exc}")
        return self._batch(folders, lambda f: self._apply_one(f, payload), "Applied to")

    def undo(self, folders: Sequence[Path]) -> ActionResult:
        if not folders:
            return ActionResult(False, "No target folder.")
        return self._batch(folders, self._undo_one, "Undone on")

    def restore_default(self, folders: Sequence[Path]) -> ActionResult:
        if not folders:
            return ActionResult(False, "No target folder.")
        return self._batch(folders, self._restore_one, "Default icon restored on")

    # -- batch handling
    @staticmethod
    def _plural(n: int) -> str:
        return "1 folder" if n == 1 else f"{n} folders"

    def _batch(
        self, folders: Sequence[Path], action: Callable[[Path], Path], verb: str
    ) -> ActionResult:
        done: list[Path] = []
        failed: list[str] = []
        for folder in folders:
            try:
                done.append(action(Path(folder)))
            except (UnsafeFolderError, FolderIconError) as exc:
                failed.append(f"{Path(folder).name or folder}: {exc}")
            except OSError as exc:
                failed.append(f"{Path(folder).name or folder}: {exc.strerror or exc}")
        if not failed:
            return ActionResult(True, f"{verb} {self._plural(len(done))}.", tuple(done))
        message = f"{verb} {len(done)} of {self._plural(len(folders))}. Failed: " + "; ".join(
            failed
        )
        return ActionResult(False, message, tuple(done))

    # -- state capture / restore
    def _snapshot(self, folder: Path) -> Snapshot:
        ini = folder / DESKTOP_INI
        store = folder / STORE_DIR
        return Snapshot(
            desktop_ini=_read_optional(ini),
            desktop_ini_attributes=self._files.attrs_or_none(ini),
            folder_attributes=self._shell.get_attributes(folder),
            icons=tuple((p.name, p.read_bytes()) for p in _icon_files(store)),
            store_existed=store.is_dir(),
        )

    def _keep_only_icons(self, store: Path, keep: set[str]) -> None:
        for path in _icon_files(store):
            if path.name not in keep:
                self._files.unlink(path)

    def _restore_snapshot(self, folder: Path, snap: Snapshot, history: History) -> None:
        ini = folder / DESKTOP_INI
        store = folder / STORE_DIR
        if snap.desktop_ini is None:
            self._files.unlink(ini)
        else:
            self._files.write(ini, snap.desktop_ini, snap.desktop_ini_attributes)
        if not snap.store_existed:
            self._files.remove_tree(store)
        else:
            self._keep_only_icons(store, {name for name, _ in snap.icons})
            for name, blob in snap.icons:
                self._files.write(store / name, blob, None)
            history.save(store)
        self._files.set_folder_bits(
            folder, ~w.SETTABLE_ATTRIBUTES, snap.folder_attributes & w.SETTABLE_ATTRIBUTES
        )

    # -- desktop.ini writing
    def _write_icon_resource(self, folder: Path, icon_file: str, index: int) -> None:
        ini = folder / DESKTOP_INI
        value = f"{icon_file},{index}"
        data = _read_optional(ini)
        if data is not None:
            # The profile API silently skips a ReadOnly desktop.ini: drop that bit first.
            attrs = self._shell.get_attributes(ini) & ~w.FILE_ATTRIBUTE_READONLY
            doc = IniDocument.parse(data)
            if doc.remove(SHELL_SECTION, LEGACY_ICON_KEYS):
                self._files.write(ini, doc.to_bytes(), attrs)
            else:
                self._shell.set_attributes(ini, attrs)
        if icon_file.isascii():
            try:
                self._shell.set_folder_icon(folder, icon_file, index)
                written = IniDocument.parse(_read_optional(ini)).get(SHELL_SECTION, "IconResource")
                if written == value:
                    return
            except OSError:
                pass  # fall back to writing desktop.ini ourselves
        self._write_ini_fallback(folder, value)

    def _write_ini_fallback(self, folder: Path, value: str) -> None:
        ini = folder / DESKTOP_INI
        doc = IniDocument.parse(_read_optional(ini))
        doc.set(SHELL_SECTION, "IconResource", value)
        attrs = (self._files.attrs_or_none(ini) or 0) | (
            w.FILE_ATTRIBUTE_HIDDEN | w.FILE_ATTRIBUTE_SYSTEM
        )
        self._files.write(ini, doc.to_bytes(), attrs)
        self._files.set_folder_bits(folder, ~0, w.FILE_ATTRIBUTE_READONLY)

    # -- per-folder actions
    def _apply_one(self, target: Path, payload: IconPayload) -> Path:
        folder = check_folder(target)
        store = folder / STORE_DIR
        snap = self._snapshot(folder)
        history = History.load(store) if snap.store_existed else History([])
        history.entries.append(snap)
        try:
            self._files.ensure_store(store)
            history.save(store)
            if payload.kind is PayloadKind.ICO:
                assert payload.ico is not None
                name = icon_file_name(payload.ico)
                if _read_optional(store / name) != payload.ico:
                    self._files.write(store / name, payload.ico, None)
                self._write_icon_resource(folder, f"{STORE_DIR}\\{name}", 0)
                self._keep_only_icons(store, {name})
            else:
                assert payload.location is not None and payload.resource_id is not None
                self._keep_only_icons(store, set())
                self._write_icon_resource(folder, payload.location, -payload.resource_id)
            added = self._shell.get_attributes(folder) & ~snap.folder_attributes
            if added & OWNABLE_FOLDER_BITS:
                history.owned_attributes |= added & OWNABLE_FOLDER_BITS
                history.save(store)
        except OSError:
            history.entries.pop()
            with contextlib.suppress(OSError):
                self._restore_snapshot(folder, snap, history)
            raise
        finally:
            self._shell.notify_updated(folder)
        return folder

    def _undo_one(self, target: Path) -> Path:
        folder = check_folder(target)
        store = folder / STORE_DIR
        history = History.load(store) if store.is_dir() else History([])
        if not history.entries:
            raise FolderIconError("Nothing to undo.")
        snap = history.entries.pop()
        try:
            self._restore_snapshot(folder, snap, history)
        finally:
            self._shell.notify_updated(folder)
        return folder

    def _restore_one(self, target: Path) -> Path:
        folder = check_folder(target)
        store = folder / STORE_DIR
        ini = folder / DESKTOP_INI
        owned = History.load(store).owned_attributes if store.is_dir() else 0
        try:
            data = _read_optional(ini)
            if data is not None:
                doc = IniDocument.parse(data)
                changed = doc.remove(SHELL_SECTION, ICON_KEYS)
                if not doc.has_keys():
                    self._files.unlink(ini)
                elif changed:
                    self._files.write(ini, doc.to_bytes(), self._shell.get_attributes(ini))
            self._files.remove_tree(store)
            if owned:
                self._files.set_folder_bits(folder, ~owned, 0)
        finally:
            self._shell.notify_updated(folder)
        return folder
