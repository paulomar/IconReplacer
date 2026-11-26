"""Internal contracts. Feature modules implement these; the UI depends only on them."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from iconreplacer.core.models import (
    ActionResult,
    ApplyOptions,
    IconEntry,
    IconPayload,
    SourceInfo,
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
