"""Icon sources backed by the public Iconify API (``api.iconify.design``)."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable, Sequence
from typing import Any
from urllib.parse import quote

from iconreplacer.catalog.categories import categorize, iter_tags
from iconreplacer.catalog.external_base import ExternalSourceBase
from iconreplacer.catalog.net import MAX_FILE_BYTES, MAX_INDEX_BYTES, NetError, Transport
from iconreplacer.core.models import (
    IconEntry,
    IconKind,
    IconRef,
    RefKind,
    Section,
    SourceInfo,
)

API = "https://api.iconify.design"
HOSTS = ("api.iconify.design",)
SEARCH_LIMIT = 999
BATCH_SIZE = 40
BATCH_DELAY = 0.03
WEIGHT_SUFFIXES = ("-thin", "-light", "-bold", "-fill", "-duotone")
_PREFIX = re.compile(r"[a-z0-9][a-z0-9-]{0,49}")
_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,99}")


def license_text(meta: dict[str, Any] | None) -> str:
    """Human readable license of an Iconify collection (``Unknown`` when absent)."""
    if not meta:
        return "Unknown"
    lic = meta.get("license") or {}
    title = lic.get("title") or lic.get("spdx")
    if not title:
        return "Unknown"
    text = f"{title} - {meta.get('name') or 'Iconify'}"
    author = (meta.get("author") or {}).get("name")
    return f"{text} by {author}" if author else text


def pretty_name(name: str) -> str:
    return re.sub(r"[-_.]+", " ", name).strip().title()


def _num(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number and abs(number) < 1e6 else default  # noqa: PLR0124


def _fmt(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:.4f}".rstrip("0").rstrip(".")


def assemble_svgs(data: dict[str, Any], wanted: Iterable[str]) -> dict[str, bytes]:
    """Build standalone SVG documents from an Iconify ``/{prefix}.json?icons=`` payload."""
    icons = data.get("icons") or {}
    aliases = data.get("aliases") or {}
    base_w = _num(data.get("width"), 16)
    base_h = _num(data.get("height"), 16)
    out: dict[str, bytes] = {}
    for name in wanted:
        node = icons.get(name)
        if node is None and name in aliases:
            alias = aliases[name]
            parent = icons.get(alias.get("parent"))
            if parent is not None:
                node = {**parent, **{k: v for k, v in alias.items() if k != "parent"}}
        if not isinstance(node, dict) or not isinstance(node.get("body"), str):
            continue
        w = _num(node.get("width"), base_w)
        h = _num(node.get("height"), base_h)
        left = _num(node.get("left"), _num(data.get("left"), 0))
        top = _num(node.get("top"), _num(data.get("top"), 0))
        if w <= 0 or h <= 0:
            continue
        body = node["body"]
        cx, cy = left + w / 2, top + h / 2
        transforms: list[str] = []
        if node.get("hFlip"):
            transforms.append(f"translate({_fmt(2 * cx)} 0) scale(-1 1)")
        if node.get("vFlip"):
            transforms.append(f"translate(0 {_fmt(2 * cy)}) scale(1 -1)")
        rotate = int(_num(node.get("rotate"), 0)) % 4
        if rotate:
            transforms.append(f"rotate({90 * rotate} {_fmt(cx)} {_fmt(cy)})")
        if transforms:
            body = f'<g transform="{" ".join(transforms)}">{body}</g>'
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{_fmt(w)}" height="{_fmt(h)}" '
            f'viewBox="{_fmt(left)} {_fmt(top)} {_fmt(w)} {_fmt(h)}">{body}</svg>'
        )
        out[name] = svg.encode("utf-8")
    return out


class IconifySource(ExternalSourceBase):
    """One Iconify collection (``prefix``) or free search across all collections."""

    def __init__(
        self,
        source_id: str,
        name: str,
        description: str,
        *,
        prefix: str | None = None,
        default_query: str | None = None,
        exclude_suffixes: Sequence[str] = (),
        network_allowed: bool = True,
        transport: Transport | None = None,
    ) -> None:
        if prefix is not None and not _PREFIX.fullmatch(prefix):
            raise ValueError(f"invalid Iconify prefix: {prefix!r}")
        if prefix is None and not default_query:
            raise ValueError("a search source needs a default query")
        super().__init__(
            SourceInfo(
                id=source_id,
                name=name,
                description=description,
                section=Section.ONLINE,
                license="Per icon set (see each icon)",
                requires_network=True,
            ),
            hosts=HOSTS,
            network_allowed=network_allowed,
            transport=transport,
        )
        self.prefix = prefix
        self.default_query = default_query
        self.exclude_suffixes = tuple(exclude_suffixes)
        self._query = ""
        self._collections: dict[str, dict[str, Any]] = {}
        self._pending: list[IconEntry] = []
        self._flushing = False

    # -- SearchableIconSource -----------------------------------------------
    def search(self, query: str) -> None:
        q = " ".join(query.split())[:100]
        with self._lock:
            self._query = q
            self._gen += 1
            gen = self._gen
            self._started = True
        self._submit(lambda: self._search_task(q, gen))

    # -- listing ------------------------------------------------------------
    def _refresh_task(self, force: bool) -> None:
        with self._lock:
            q, gen = self._query, self._gen
        self._listing(q, gen, force)

    def _search_task(self, q: str, gen: int) -> None:
        self._listing(q, gen, False)

    def _listing(self, q: str, gen: int, force: bool) -> None:
        query = q or self.default_query
        if query:
            key = f"search:{self.prefix or '*'}:{query.casefold()}:{SEARCH_LIMIT}"
            fetch = lambda: self._fetch_search(query)  # noqa: E731
        else:
            key = f"collection:{self.prefix}"
            fetch = self._fetch_collection
        self._run_listing(key, fetch, self._build_entries, force=force, gen=gen)

    def _get_json(self, url: str, max_bytes: int) -> Any:
        return json.loads(self._http.get(url, max_bytes=max_bytes, accept="application/json").body)

    def _fetch_search(self, query: str) -> dict[str, Any]:
        url = f"{API}/search?query={quote(query, safe='')}&limit={SEARCH_LIMIT}"
        if self.prefix:
            url += f"&prefix={self.prefix}"
        data = self._get_json(url, MAX_INDEX_BYTES)
        return {"icons": list(data["icons"]), "collections": dict(data.get("collections") or {})}

    def _fetch_collection(self) -> dict[str, Any]:
        prefix = self.prefix
        data = self._get_json(f"{API}/collection?prefix={prefix}", MAX_INDEX_BYTES)
        names = list(data.get("uncategorized") or [])
        for group in (data.get("categories") or {}).values():
            names.extend(group)
        hidden = set(data.get("hidden") or [])
        icons = [f"{prefix}:{n}" for n in dict.fromkeys(names) if n not in hidden]
        meta = self._get_json(f"{API}/collections?prefixes={prefix}", MAX_FILE_BYTES)
        return {"icons": icons, "collections": meta}

    def _build_entries(self, raw: dict[str, Any]) -> list[IconEntry]:
        collections: dict[str, dict[str, Any]] = raw.get("collections") or {}
        with self._lock:
            self._collections.update(collections)
        out: list[IconEntry] = []
        seen: set[str] = set()
        for full in raw["icons"]:
            prefix, _, name = str(full).partition(":")
            if not _PREFIX.fullmatch(prefix) or not _NAME.fullmatch(name):
                continue
            if self.prefix and prefix != self.prefix:
                continue
            if self.exclude_suffixes and name.endswith(self.exclude_suffixes):
                continue
            if full in seen:
                continue
            seen.add(full)
            meta = collections.get(prefix) or self._collections.get(prefix) or {}
            out.append(self._make_entry(prefix, name, meta))
        return out

    def _make_entry(self, prefix: str, name: str, meta: dict[str, Any]) -> IconEntry:
        collection_name = str(meta.get("name") or prefix)
        tags = {*iter_tags(name), prefix, collection_name.casefold()}
        return IconEntry(
            id=f"{self._info.id}:{prefix}:{name}",
            name=pretty_name(name),
            source_id=self._info.id,
            ref=IconRef(RefKind.REMOTE, f"{prefix}:{name}"),
            categories=categorize(name, collection_category=meta.get("category")),
            tags=frozenset(tags),
            license=license_text(meta),
            kind=IconKind.GLYPH if meta.get("palette") is False else IconKind.FULL,
        )

    # -- bytes --------------------------------------------------------------
    @staticmethod
    def _split(entry: IconEntry) -> tuple[str, str]:
        prefix, _, name = entry.ref.location.partition(":")
        if not _PREFIX.fullmatch(prefix) or not _NAME.fullmatch(name):
            raise ValueError(f"invalid Iconify reference: {entry.ref.location!r}")
        return prefix, name

    def _bytes_key(self, entry: IconEntry) -> str:
        return "svg:" + entry.ref.location

    def _fetch_batch(self, prefix: str, names: Sequence[str]) -> dict[str, bytes]:
        url = f"{API}/{prefix}.json?icons={','.join(quote(n, safe='') for n in names)}"
        data = self._get_json(url, MAX_FILE_BYTES)
        svgs = assemble_svgs(data, names)
        for name, svg in svgs.items():
            self._cache.put_bytes(f"svg:{prefix}:{name}", svg)
        return svgs

    def _download(self, entry: IconEntry) -> bytes:
        prefix, name = self._split(entry)
        svgs = self._fetch_batch(prefix, [name])
        if name not in svgs:
            raise ValueError(f"icon not found: {entry.ref.location}")
        return svgs[name]

    def _schedule_fetch(self, entry: IconEntry) -> None:
        """Coalesce thumbnails requested close together into batched API calls."""
        if not self._can_fetch():
            return
        with self._lock:
            if entry.id in self._inflight:
                return
            if self._backing_off(entry.id):
                return
            self._inflight.add(entry.id)
            self._pending.append(entry)
            if self._flushing:
                return
            self._flushing = True
        self._submit(self._flush)

    def _flush(self) -> None:
        time.sleep(BATCH_DELAY)
        while True:
            with self._lock:
                batch, self._pending = self._pending, []
                if not batch:
                    self._flushing = False
                    return
            groups: dict[str, list[IconEntry]] = {}
            for entry in batch:
                try:
                    groups.setdefault(self._split(entry)[0], []).append(entry)
                except ValueError:
                    self._finish([entry], ok=False)
            for prefix, items in groups.items():
                for i in range(0, len(items), BATCH_SIZE):
                    chunk = items[i : i + BATCH_SIZE]
                    try:
                        svgs = self._fetch_batch(prefix, [self._split(e)[1] for e in chunk])
                    except (NetError, ValueError, KeyError, TypeError):
                        self._finish(chunk, ok=False)
                        continue
                    done = [e for e in chunk if self._split(e)[1] in svgs]
                    self._finish(done, ok=True)
                    self._finish([e for e in chunk if e not in done], ok=False)

    def _finish(self, entries: Sequence[IconEntry], *, ok: bool) -> None:
        if not entries:
            return
        with self._lock:
            for e in entries:
                self._inflight.discard(e.id)
        for e in entries:
            if ok:
                self._reset_backoff(e.id)
            else:
                self._fail(e.id)
        if ok:
            self._notify()


def default_iconify_sources(
    *, network_allowed: bool = True, transport: Transport | None = None
) -> list[IconifySource]:
    return [
        IconifySource(
            "iconify",
            "Iconify",
            "Search more than 200 open-source icon sets",
            default_query="folder",
            network_allowed=network_allowed,
            transport=transport,
        ),
        IconifySource(
            "phosphor",
            "Phosphor",
            "Flexible icon family (regular weight)",
            prefix="ph",
            exclude_suffixes=WEIGHT_SUFFIXES,
            network_allowed=network_allowed,
            transport=transport,
        ),
    ]
