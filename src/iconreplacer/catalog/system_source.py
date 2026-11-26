"""Icon sources backed by the icon libraries that ship with Windows.

Icons are referenced in place (``%SystemRoot%\\System32\\<file>,-<id>``) and
never copied. Each source enumerates its library lazily, keeps a small JSON
index in ``cache_dir("system")`` and renders icons on demand from the live file.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import threading
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from iconreplacer.catalog import pe_icons
from iconreplacer.catalog.pe_icons import RT_GROUP_ICON, RT_ICON, GroupImage, PeIconError
from iconreplacer.core import paths
from iconreplacer.core.models import (
    CATEGORIES,
    IconEntry,
    IconKind,
    IconRef,
    RefKind,
    Section,
    SourceInfo,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QImage

LICENSE = "Microsoft Windows (referenced in place, not redistributed)"
CACHE_NAME = "system"
INDEX_VERSION = 1
_ICO_LRU = 256


@dataclass(frozen=True, slots=True)
class LibraryInfo:
    file: str
    description: str
    categories: tuple[str, ...]
    default_categories: tuple[str, ...]
    companion_of: str | None = None

    @property
    def source_id(self) -> str:
        return self.file.lower()

    @property
    def location(self) -> str:
        return f"%SystemRoot%\\System32\\{self.file}"


@dataclass(frozen=True, slots=True)
class CuratedIcon:
    name: str
    categories: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IndexItem:
    resource_id: int
    sizes: tuple[int, ...]
    hash: str


def _data_json(name: str) -> Any:
    text = resources.files("iconreplacer.catalog").joinpath("system_data", name).read_text("utf-8")
    return json.loads(text)


@cache
def system_libraries() -> tuple[LibraryInfo, ...]:
    """Library metadata from ``system_data/system_libraries.json``."""
    raw = _data_json("system_libraries.json")
    return tuple(
        LibraryInfo(
            file=lib["file"],
            description=lib["description"],
            categories=tuple(lib["categories"]),
            default_categories=tuple(lib["default_categories"]),
            companion_of=lib.get("companion_of"),
        )
        for lib in raw["libraries"]
    )


@cache
def curated_icons() -> dict[str, dict[int, CuratedIcon]]:
    """Curated names/categories/tags from ``system_data/system_icon_tags.json``."""
    raw = _data_json("system_icon_tags.json")
    out: dict[str, dict[int, CuratedIcon]] = {}
    for lib, items in raw["libraries"].items():
        out[lib.lower()] = {
            int(rid): CuratedIcon(
                name=item["name"],
                categories=tuple(item["categories"]),
                tags=tuple(item.get("tags", ())),
            )
            for rid, item in items.items()
        }
    return out


def system_root() -> Path:
    return Path(os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR") or r"C:\Windows")


def _stat_key(path: Path) -> list[Any] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return [str(path).casefold(), st.st_size, st.st_mtime_ns]


def _best_image(images: Sequence[GroupImage], size: int) -> GroupImage:
    exact = [i for i in images if i.width == size]
    if exact:
        return max(exact, key=lambda i: (i.bit_count, i.size))
    larger = [i for i in images if i.width > size]
    if larger:
        smallest = min(i.width for i in larger)
        return max((i for i in larger if i.width == smallest), key=lambda i: i.bit_count)
    largest = max(i.width for i in images)
    return max((i for i in images if i.width == largest), key=lambda i: i.bit_count)


class SystemIconSource:
    """``IconSource`` for one Windows icon library (DLL/EXE)."""

    def __init__(
        self,
        library: LibraryInfo,
        path: Path | None = None,
        mun_path: Path | None = None,
        use_cache: bool = True,
    ) -> None:
        root = system_root()
        self.library = library
        self.path = Path(path) if path is not None else root / "System32" / library.file
        self.mun_path = (
            Path(mun_path)
            if mun_path is not None
            else root / "SystemResources" / f"{library.file}.mun"
        )
        self._use_cache = use_cache
        self._info = SourceInfo(
            id=library.source_id,
            name=library.file,
            description=library.description,
            section=Section.SYSTEM,
            license=LICENSE,
        )
        self._lock = threading.RLock()
        self._module: pe_icons.PeModule | None = None
        self._entries: tuple[IconEntry, ...] | None = None
        self._index: dict[int, IndexItem] = {}
        self._ico_cache: OrderedDict[int, bytes] = OrderedDict()
        self.skipped_named = 0
        self.loaded_from_cache = False

    # -- IconSource ---------------------------------------------------------
    @property
    def info(self) -> SourceInfo:
        return self._info

    @property
    def available(self) -> bool:
        return pe_icons.IS_WINDOWS and self.path.is_file()

    def entries(self) -> Sequence[IconEntry]:
        with self._lock:
            if self._entries is None:
                items = self._load_index()
                self._index = {i.resource_id: i for i in items}
                self._entries = tuple(self._make_entry(i) for i in items)
            return self._entries

    def render(self, entry: IconEntry, size: int) -> QImage:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage, QPainter

        canvas = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        canvas.fill(Qt.GlobalColor.transparent)
        try:
            image = self._decode_best(self._resource_id(entry), size)
        except (OSError, ValueError):
            return canvas
        if image.isNull():
            return canvas
        if image.width() != size or image.height() != size:
            image = image.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        painter = QPainter(canvas)
        painter.drawImage((size - image.width()) // 2, (size - image.height()) // 2, image)
        painter.end()
        return canvas

    # -- extras -------------------------------------------------------------
    def extract_ico_bytes(self, entry: IconEntry) -> bytes:
        """Standalone ``.ico`` file content with every image of the group."""
        rid = self._resource_id(entry)
        with self._lock:
            cached = self._ico_cache.get(rid)
            if cached is not None:
                self._ico_cache.move_to_end(rid)
                return cached
            data = self._open().ico_bytes(rid)
            self._ico_cache[rid] = data
            if len(self._ico_cache) > _ICO_LRU:
                self._ico_cache.popitem(last=False)
            return data

    def available_sizes(self, entry: IconEntry) -> tuple[int, ...]:
        self.entries()
        item = self._index.get(self._resource_id(entry))
        return item.sizes if item else ()

    def content_hash(self, entry: IconEntry) -> str | None:
        self.entries()
        item = self._index.get(self._resource_id(entry))
        return item.hash if item else None

    def close(self) -> None:
        with self._lock:
            if self._module is not None:
                self._module.close()
            self._module = None
            self._ico_cache.clear()

    def __enter__(self) -> SystemIconSource:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internals ----------------------------------------------------------
    def _resource_id(self, entry: IconEntry) -> int:
        rid = entry.ref.resource_id
        if entry.source_id != self._info.id or rid is None or rid <= 0:
            raise ValueError(f"entry {entry.id!r} does not belong to {self._info.id}")
        return rid

    def _open(self) -> pe_icons.PeModule:
        """Open the library as a datafile: System32 path, falling back to the .mun."""
        if self._module is not None and not self._module.closed:
            return self._module
        errors: list[str] = []
        for candidate in (self.path, self.mun_path):
            if not candidate.is_file():
                continue
            try:
                module = pe_icons.PeModule(str(candidate))
            except OSError as exc:
                errors.append(str(exc))
                continue
            ids, _ = module.group_icon_ids()
            if ids or candidate == self.mun_path or not self.mun_path.is_file():
                self._module = module
                return module
            module.close()  # stub without visible icons: try the .mun file
        raise PeIconError(f"cannot open {self.library.file}: {'; '.join(errors) or 'missing'}")

    def _cache_key(self) -> dict[str, Any]:
        return {
            "version": INDEX_VERSION,
            "file": _stat_key(self.path),
            "mun": _stat_key(self.mun_path),
        }

    def _cache_file(self) -> Path:
        return paths.cache_dir(CACHE_NAME) / f"{self.library.source_id}.json"

    def _load_index(self) -> list[IndexItem]:
        if not self.available:
            return []
        key = self._cache_key()
        if self._use_cache:
            cached = self._read_cache(key)
            if cached is not None:
                self.loaded_from_cache = True
                return cached
        try:
            items = self._enumerate()
        except OSError:
            return []
        if self._use_cache:
            self._write_cache(key, items)
        return items

    def _enumerate(self) -> list[IndexItem]:
        with self._lock:
            module = self._open()
            ids, self.skipped_named = module.group_icon_ids()
            items: list[IndexItem] = []
            for rid in ids:
                group = module.resource(RT_GROUP_ICON, rid)
                if group is None:
                    continue
                try:
                    images = pe_icons.parse_group(group)
                except PeIconError:
                    continue
                digest = hashlib.blake2b(group, digest_size=8)
                present: set[int] = set()
                for img in images:
                    blob = module.resource(RT_ICON, img.icon_id)
                    if blob:
                        digest.update(blob)
                        present.add(img.width)
                if present:
                    items.append(IndexItem(rid, tuple(sorted(present)), digest.hexdigest()))
            return items

    def _read_cache(self, key: dict[str, Any]) -> list[IndexItem] | None:
        try:
            raw = json.loads(self._cache_file().read_text("utf-8"))
            if raw.get("key") != key:
                return None
            self.skipped_named = int(raw.get("skipped_named", 0))
            return [
                IndexItem(int(i), tuple(int(s) for s in sz), str(h)) for i, sz, h in raw["items"]
            ]
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _write_cache(self, key: dict[str, Any], items: list[IndexItem]) -> None:
        payload = {
            "key": key,
            "skipped_named": self.skipped_named,
            "items": [[i.resource_id, list(i.sizes), i.hash] for i in items],
        }
        try:
            target = self._cache_file()
            fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=target.stem, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, separators=(",", ":"))
                os.replace(tmp, target)
            except BaseException:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
                raise
        except OSError:
            pass  # the cache is an optimisation only

    def _make_entry(self, item: IndexItem) -> IconEntry:
        lib = self.library
        curated = curated_icons().get(lib.source_id, {}).get(item.resource_id)
        if curated:
            name = curated.name
            cats = [c for c in curated.categories if c in CATEGORIES]
            extra = curated.tags
        else:
            name = f"{lib.file} #{item.resource_id}"
            cats = []
            extra = ()
        if not cats:
            cats = [c for c in lib.default_categories if c in CATEGORIES] or ["System"]
        stem = lib.file.rsplit(".", 1)[0].lower()
        tags = {lib.file.lower(), stem, str(item.resource_id), *(c.lower() for c in cats)}
        tags.update(t.lower() for t in extra)
        return IconEntry(
            id=f"{lib.source_id}:{item.resource_id}",
            name=name,
            source_id=lib.source_id,
            ref=IconRef(RefKind.RESOURCE, lib.location, item.resource_id),
            categories=frozenset(cats),
            tags=frozenset(tags),
            license=LICENSE,
            kind=IconKind.FULL,
        )

    def _decode_best(self, rid: int, size: int) -> QImage:
        from PySide6.QtGui import QImage

        with self._lock:
            module = self._open()
            images = module.group_images(rid)
            if not images:
                raise PeIconError(f"empty icon group {rid}")
            best = _best_image(images, size)
            blob = module.resource(RT_ICON, best.icon_id)
        if not blob:
            raise PeIconError(f"missing icon image {best.icon_id}")
        if blob.startswith(b"\x89PNG"):
            return QImage.fromData(blob, "PNG")
        single = pe_icons.build_ico([(best, blob)])
        return QImage.fromData(single, "ICO")


def build_system_sources(
    libraries: Sequence[LibraryInfo] | None = None, include_missing: bool = False
) -> list[SystemIconSource]:
    """One source per library present on this Windows build (missing ones skipped)."""
    out: list[SystemIconSource] = []
    for lib in libraries if libraries is not None else system_libraries():
        src = SystemIconSource(lib)
        if include_missing or src.available:
            out.append(src)
    return out
