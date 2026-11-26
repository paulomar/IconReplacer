"""Internal contracts. Feature modules implement these; the UI depends only on them."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from iconreplacer.core.models import (
    ActionResult,
    ApplyOptions,
    IconEntry,
    IconPayload,
    SourceInfo,
    SourceState,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QImage


@runtime_checkable
class IconSource(Protocol):
    """A provider of icons (system DLL, online set, local folder...)."""

    @property
    def info(self) -> SourceInfo: ...

    def entries(self) -> Sequence[IconEntry]:
        """All icons of this source. May be cached; must not block on network."""
        ...

    def render(self, entry: IconEntry, size: int) -> QImage:
        """Render ``entry`` as a square ARGB image of ``size`` pixels."""
        ...


@runtime_checkable
class DynamicIconSource(IconSource, Protocol):
    """A source whose content arrives asynchronously (network, background scans).

    ``entries()`` and ``render()`` never block: ``render`` returns a placeholder and
    schedules a fetch when pixels are missing. Subscriber callbacks are always
    invoked on the Qt GUI thread whenever entries, state or thumbnails change.
    """

    def state(self) -> SourceState: ...

    def last_error(self) -> str | None: ...

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register ``callback``; returns a function that unsubscribes it."""
        ...

    def refresh(self) -> None:
        """Start (re)loading in the background; no-op when the network is disallowed."""
        ...

    def set_network_allowed(self, allowed: bool) -> None: ...


@runtime_checkable
class SearchableIconSource(Protocol):
    """A source that can run a remote query; results replace ``entries()``."""

    def search(self, query: str) -> None:
        """Non-blocking; an empty query restores the default listing."""
        ...


@runtime_checkable
class IconBytesProvider(Protocol):
    """Raw image bytes for an entry (to build an .ico). MAY BLOCK: worker threads only."""

    def fetch_bytes(self, entry: IconEntry) -> bytes:
        """Return the original image bytes; raise OSError/ValueError on failure."""
        ...


@runtime_checkable
class IconMaterializer(Protocol):
    """Turns a chosen icon (+ options) into what the folder service writes."""

    def materialize(self, entry: IconEntry, options: ApplyOptions) -> IconPayload: ...


@runtime_checkable
class FolderIconService(Protocol):
    """Applies, reverts and resets folder icons."""

    def apply(
        self, folders: Sequence[Path], entry: IconEntry, options: ApplyOptions
    ) -> ActionResult: ...

    def undo(self, folders: Sequence[Path]) -> ActionResult: ...

    def restore_default(self, folders: Sequence[Path]) -> ActionResult: ...


@runtime_checkable
class SettingsStore(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...

    def set(self, key: str, value: Any) -> None: ...


class InMemorySettingsStore:
    """Non-persistent settings (prototype)."""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(initial or {})

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
