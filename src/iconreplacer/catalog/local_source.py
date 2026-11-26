"""Icon source for a folder on disk (images and icon libraries), scanned in the background."""

from __future__ import annotations

import hashlib
import logging
import os
import stat
from collections import OrderedDict
from pathlib import Path

from iconreplacer.catalog import pe_icons
from iconreplacer.catalog.categories import categorize, iter_tags
from iconreplacer.catalog.external_base import ExternalSourceBase
from iconreplacer.catalog.github_source import pretty_stem
from iconreplacer.catalog.net import MAX_FILE_BYTES
from iconreplacer.core.models import (
    IconEntry,
    IconKind,
    IconRef,
    RefKind,
    Section,
    SourceInfo,
    SourceState,
)

log = logging.getLogger(__name__)

IMAGE_EXTS = frozenset({".ico", ".png", ".svg", ".icns"})
LIBRARY_EXTS = frozenset({".dll", ".exe", ".icl", ".mun"})
MAX_DEPTH = 4
MAX_FILES = 5000
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MEM_ITEMS = 64
MEM_ITEM_BYTES = 4 * 1024 * 1024
LICENSE = "Local files (your own)"
_SKIP_ATTRS = (
    getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2)
    | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 0x4)
    | getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
)


def local_source_id(path: Path) -> str:
    norm = os.path.normcase(os.path.abspath(path))
    return "local-" + hashlib.sha1(norm.encode("utf-8")).hexdigest()[:10]  # noqa: S324


def _skipped(entry: os.DirEntry[str]) -> bool:
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    if getattr(st, "st_file_attributes", 0) & _SKIP_ATTRS:
        return True
    return entry.is_symlink()


class LocalFolderSource(ExternalSourceBase):
    def __init__(self, path: Path | str, *, name: str | None = None) -> None:
        self.root = Path(path)
        super().__init__(
            SourceInfo(
                id=local_source_id(self.root),
                name=name or self.root.name or str(self.root),
                description=str(self.root),
                section=Section.LOCAL,
                license=LICENSE,
                requires_network=False,
            ),
            network_allowed=True,
        )
        self._mem: OrderedDict[str, bytes] = OrderedDict()
        self.truncated = False

    # network switch is irrelevant here
    def set_network_allowed(self, allowed: bool) -> None:
        return

    def _can_fetch(self) -> bool:
        return True

    def _cached_bytes(self, entry: IconEntry) -> bytes | None:
        with self._lock:  # small in-memory cache only: files are local, no disk cache
            return self._mem.get(entry.id)

    def _remember(self, entry: IconEntry, data: bytes) -> bytes:
        if len(data) > MEM_ITEM_BYTES:
            raise ValueError("file too large to preview")
        with self._lock:
            self._mem[entry.id] = data
            while len(self._mem) > MEM_ITEMS:
                self._mem.popitem(last=False)
        return data

    def fetch_bytes(self, entry: IconEntry) -> bytes:
        return self._read(self._resolve(entry))

    def _refresh_task(self, force: bool) -> None:
        with self._lock:
            self._mem.clear()
            self._lru.clear()
        self._set_state(SourceState.LOADING, None)
        try:
            entries = self._scan()
        except OSError as exc:
            self._set_state(SourceState.ERROR, f"cannot scan {self.root}: {exc}")
            return
        self._apply_entries(entries)
        self._set_state(SourceState.READY, None)

    # -- scanning -----------------------------------------------------------
    def _scan(self) -> list[IconEntry]:
        if not self.root.is_dir():
            raise OSError("folder not found")
        out: list[IconEntry] = []
        examined = 0
        self.truncated = False
        stack: list[tuple[str, int]] = [(str(self.root), 0)]
        while stack:
            directory, depth = stack.pop()
            try:
                with os.scandir(directory) as it:
                    children = sorted(it, key=lambda e: e.name.casefold())
            except OSError:
                continue
            subdirs: list[tuple[str, int]] = []
            for child in children:
                if _skipped(child):
                    continue
                if child.is_dir(follow_symlinks=False):
                    if depth < MAX_DEPTH:
                        subdirs.append((child.path, depth + 1))
                    continue
                ext = os.path.splitext(child.name)[1].lower()
                if ext not in IMAGE_EXTS and ext not in LIBRARY_EXTS:
                    continue
                if examined >= MAX_FILES:
                    self.truncated = True
                    stack.clear()
                    subdirs.clear()
                    break
                examined += 1
                if ext in IMAGE_EXTS:
                    out.append(self._image_entry(Path(child.path)))
                else:
                    out.extend(self._library_entries(Path(child.path)))
            stack.extend(reversed(subdirs))
        return out

    def _rel_parts(self, path: Path) -> list[str]:
        try:
            return list(path.relative_to(self.root).parts[:-1])
        except ValueError:
            return []

    def _digest(self, path: Path) -> str:
        return hashlib.sha1(os.path.normcase(str(path)).encode("utf-8")).hexdigest()[:12]  # noqa: S324

    def _image_entry(self, path: Path) -> IconEntry:
        folders = self._rel_parts(path)
        return IconEntry(
            id=f"{self._info.id}:{self._digest(path)}",
            name=pretty_stem(path.stem),
            source_id=self._info.id,
            ref=IconRef(RefKind.FILE, str(path)),
            categories=categorize(*folders, path.stem),
            tags=frozenset(iter_tags(path.stem, *folders)),
            license=LICENSE,
            kind=IconKind.FULL,
        )

    def _library_entries(self, path: Path) -> list[IconEntry]:
        try:
            with pe_icons.PeModule(str(path)) as module:
                ids, _skipped_named = module.group_icon_ids()
        except OSError:
            return []
        folders = self._rel_parts(path)
        digest = self._digest(path)
        cats = categorize(*folders, path.stem)
        base_tags = frozenset(iter_tags(path.stem, *folders)) | {path.name.lower()}
        return [
            IconEntry(
                id=f"{self._info.id}:{digest}:{rid}",
                name=f"{path.name} #{rid}",
                source_id=self._info.id,
                ref=IconRef(RefKind.RESOURCE, str(path), rid),
                categories=cats,
                tags=base_tags | {str(rid)},
                license=LICENSE,
                kind=IconKind.FULL,
            )
            for rid in ids
        ]

    # -- bytes --------------------------------------------------------------
    def _get_bytes(self, entry: IconEntry) -> bytes:
        return self._remember(entry, self._read(entry))

    def _read(self, entry: IconEntry) -> bytes:
        path = Path(entry.ref.location)
        if entry.ref.kind is RefKind.RESOURCE:
            rid = entry.ref.resource_id
            if rid is None or rid <= 0:
                raise ValueError("invalid resource id")
            with pe_icons.PeModule(str(path)) as module:
                return module.ico_bytes(rid)
        if path.stat().st_size > min(MAX_IMAGE_BYTES, MAX_FILE_BYTES * 4):
            raise ValueError("file too large")
        return path.read_bytes()
