"""Shared machinery of the external (dynamic) icon sources.

Work happens on pool threads and only produces bytes/JSON. Subscriber callbacks
and image decoding run on the Qt GUI thread: results are marshalled with a queued
signal of a ``QObject`` that lives in the GUI thread (sources must therefore be
constructed on the GUI thread). Notifications are coalesced.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QByteArray, QObject, QRectF, Qt, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from iconreplacer.catalog.net import (
    HttpClient,
    HttpError,
    NetError,
    OfflineError,
    Transport,
    TransportError,
)
from iconreplacer.catalog.online_cache import DiskCache
from iconreplacer.converter.loader import ConversionError, load_image
from iconreplacer.core.models import IconEntry, SourceInfo, SourceState

if TYPE_CHECKING:
    from collections.abc import Collection

log = logging.getLogger(__name__)

DECODED_LRU = 512
_POOL: ThreadPoolExecutor | None = None
_POOL_LOCK = threading.Lock()
_DISPATCHER: _Dispatcher | None = None


class _Dispatcher(QObject):
    """Runs posted callables on the thread this object lives in (the GUI thread)."""

    _call = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._call.connect(self._run)

    def _run(self, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception:  # a failing subscriber must not break the event loop
            log.exception("callback failed")

    def post(self, fn: Callable[[], None]) -> None:
        self._call.emit(fn)


def dispatcher() -> _Dispatcher:
    global _DISPATCHER
    with _POOL_LOCK:
        if _DISPATCHER is None:
            _DISPATCHER = _Dispatcher()
        return _DISPATCHER


def pool() -> ThreadPoolExecutor:
    global _POOL
    with _POOL_LOCK:
        if _POOL is None:
            _POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="iconreplacer-src")
        return _POOL


def placeholder(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    return image


def decode_to_square(data: bytes, size: int, hint: str | None = None) -> QImage:
    """Validate and render image bytes into a square ARGB image (GUI thread)."""
    src = load_image(data, hint)
    canvas = placeholder(size)
    painter = QPainter(canvas)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if src.is_vector:
            renderer = QSvgRenderer(QByteArray(src.svg or b""))
            renderer.render(painter, QRectF(0, 0, size, size))
        elif src.raster is not None:
            image = src.raster
            if image.width() != size or image.height() != size:
                image = image.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            painter.drawImage((size - image.width()) // 2, (size - image.height()) // 2, image)
    finally:
        painter.end()
    return canvas


class ExternalSourceBase:
    """``IconSource`` + ``DynamicIconSource`` + ``IconBytesProvider`` skeleton."""

    def __init__(
        self,
        info: SourceInfo,
        *,
        hosts: Collection[str] = (),
        network_allowed: bool = True,
        transport: Transport | None = None,
        cache_name: str | None = None,
    ) -> None:
        self._info = info
        self._lock = threading.RLock()
        self._entries: tuple[IconEntry, ...] = ()
        self._by_id: dict[str, IconEntry] = {}
        self._state = SourceState.LOADING if network_allowed else SourceState.OFFLINE
        self._error: str | None = None
        self._subs: list[Callable[[], None]] = []
        self._http = HttpClient(hosts, transport, network_allowed)
        self._cache = DiskCache(cache_name or info.id)
        self._lru: OrderedDict[tuple[str, int], QImage] = OrderedDict()
        self._inflight: set[str] = set()
        self._failed: set[str] = set()
        self._started = False
        self._gen = 0
        self._notify_pending = False
        self._dispatcher = dispatcher()

    # -- IconSource ---------------------------------------------------------
    @property
    def info(self) -> SourceInfo:
        return self._info

    def entries(self) -> Sequence[IconEntry]:
        self._ensure_started()
        return self._entries

    def render(self, entry: IconEntry, size: int) -> QImage:
        key = (entry.id, size)
        with self._lock:
            cached = self._lru.get(key)
            if cached is not None:
                self._lru.move_to_end(key)
                return cached
            known = self._by_id.get(entry.id)
            failed = entry.id in self._failed
        if known is None or failed:
            return placeholder(size)
        data = self._cached_bytes(known)
        if data is not None:
            try:
                image = decode_to_square(data, size, known.name)
            except ConversionError:
                with self._lock:
                    self._failed.add(known.id)
                return placeholder(size)
            with self._lock:
                self._lru[key] = image
                while len(self._lru) > DECODED_LRU:
                    self._lru.popitem(last=False)
            return image
        self._schedule_fetch(known)
        return placeholder(size)

    # -- DynamicIconSource --------------------------------------------------
    def state(self) -> SourceState:
        return self._state

    def last_error(self) -> str | None:
        return self._error

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        with self._lock:
            self._subs.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subs:
                    self._subs.remove(callback)

        return unsubscribe

    def refresh(self) -> None:
        self._started = True
        self._submit(lambda: self._refresh_task(force=True))

    def set_network_allowed(self, allowed: bool) -> None:
        allowed = bool(allowed)
        if allowed == self._http.network_allowed:
            return
        self._http.network_allowed = allowed
        if allowed:
            with self._lock:
                self._failed.clear()
            self.refresh()
        else:
            self._gen += 1
            self._set_state(SourceState.OFFLINE, None)

    # -- IconBytesProvider --------------------------------------------------
    def fetch_bytes(self, entry: IconEntry) -> bytes:
        """Original image bytes (cache first). Blocking: call from worker threads."""
        known = self._resolve(entry)
        return self._get_bytes(known)

    # -- hooks for subclasses -----------------------------------------------
    def _refresh_task(self, force: bool) -> None:
        raise NotImplementedError

    def _download(self, entry: IconEntry) -> bytes:
        raise NotImplementedError

    def _bytes_key(self, entry: IconEntry) -> str:
        return entry.ref.location

    def _cached_bytes(self, entry: IconEntry) -> bytes | None:
        return self._cache.get_bytes(self._bytes_key(entry))

    def _get_bytes(self, entry: IconEntry) -> bytes:
        data = self._cached_bytes(entry)
        if data is not None:
            return data
        data = self._download(entry)
        if not data:
            raise ValueError("empty download")
        self._cache.put_bytes(self._bytes_key(entry), data)
        return data

    def _can_fetch(self) -> bool:
        return self._http.network_allowed

    # -- internals ----------------------------------------------------------
    def _resolve(self, entry: IconEntry) -> IconEntry:
        known = self._by_id.get(entry.id)
        if known is None:
            raise ValueError(f"unknown entry for {self._info.id}: {entry.id!r}")
        return known

    def _ensure_started(self) -> None:
        if not self._started:
            self._started = True
            self._submit(lambda: self._refresh_task(force=False))

    def _submit(self, fn: Callable[[], None]) -> None:
        def guarded() -> None:
            try:
                fn()
            except Exception as exc:
                log.exception("background task failed")
                self._set_state(SourceState.ERROR, f"unexpected error: {exc}")

        pool().submit(guarded)

    def _schedule_fetch(self, entry: IconEntry) -> None:
        if not self._can_fetch():
            return
        with self._lock:
            if entry.id in self._inflight:
                return
            self._inflight.add(entry.id)

        def task() -> None:
            ok = False
            try:
                self._get_bytes(entry)
                ok = True
            except (OSError, ValueError) as exc:
                log.debug("fetch failed for %s: %s", entry.id, exc)
                if not isinstance(exc, OfflineError):
                    with self._lock:
                        self._failed.add(entry.id)
            finally:
                with self._lock:
                    self._inflight.discard(entry.id)
            if ok:
                self._notify()

        self._submit(task)

    def _apply_entries(self, entries: Sequence[IconEntry], gen: int | None = None) -> bool:
        with self._lock:
            if gen is not None and gen != self._gen:
                return False
            self._entries = tuple(entries)
            self._by_id = {e.id: e for e in self._entries}
        self._notify()
        return True

    def _set_state(self, state: SourceState, error: str | None) -> None:
        with self._lock:
            changed = state != self._state or error != self._error
            self._state = state
            self._error = error
        if changed:
            self._notify()

    def _set_info(self, info: SourceInfo) -> None:
        self._info = info

    def _notify(self) -> None:
        with self._lock:
            if self._notify_pending:
                return
            self._notify_pending = True
        self._dispatcher.post(self._deliver)

    def _deliver(self) -> None:
        with self._lock:
            self._notify_pending = False
            subs = list(self._subs)
        for cb in subs:
            try:
                cb()
            except Exception:
                log.exception("subscriber failed")

    # -- cached listing flow (stale-while-revalidate) -------------------------
    def _run_listing(
        self,
        key: str,
        fetch: Callable[[], Any],
        build: Callable[[Any], Sequence[IconEntry]],
        *,
        force: bool,
        gen: int | None = None,
    ) -> None:
        cached = self._cache.get_json(key)
        if cached is not None:
            try:
                self._apply_entries(build(cached[0]), gen)
            except (KeyError, TypeError, ValueError):
                cached = None  # unusable cache
        if not self._http.network_allowed:
            self._set_state(SourceState.OFFLINE, None)
            return
        if cached is not None and not force and self._cache.is_fresh(cached[1]):
            self._set_state(SourceState.READY, None)
            return
        if not self._entries:
            self._set_state(SourceState.LOADING, None)
        try:
            raw = fetch()
            entries = build(raw)
        except NetError as exc:
            self._handle_error(exc)
            return
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            self._set_state(SourceState.ERROR, f"unexpected response: {exc}")
            return
        self._cache.put_json(key, raw)
        self._apply_entries(entries, gen)
        self._set_state(SourceState.READY, None)

    def _handle_error(self, exc: NetError) -> None:
        if isinstance(exc, OfflineError | TransportError):
            self._set_state(SourceState.OFFLINE, str(exc))
        elif isinstance(exc, HttpError):
            self._set_state(SourceState.ERROR, self._describe_http(exc))
        else:
            self._set_state(SourceState.ERROR, str(exc))

    def _describe_http(self, exc: HttpError) -> str:
        if exc.rate_limited:
            return "Rate limit reached; try again later."
        return f"Server error (HTTP {exc.status})."
