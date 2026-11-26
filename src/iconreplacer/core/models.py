"""Immutable domain models shared by all IconReplacer components."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Section(StrEnum):
    SYSTEM = "system"
    ONLINE = "online"
    LOCAL = "local"


class IconKind(StrEnum):
    FULL = "full"  # full-color artwork, usable as-is
    GLYPH = "glyph"  # monochrome glyph, best composed on a folder base


class SourceState(StrEnum):
    READY = "ready"
    LOADING = "loading"
    OFFLINE = "offline"  # network disallowed or unreachable
    ERROR = "error"


class RefKind(StrEnum):
    RESOURCE = "resource"  # PE resource in a DLL/EXE: location + resource_id
    FILE = "file"  # standalone image file (.ico/.png/.svg/.icns)
    REMOTE = "remote"  # downloadable item (URL or provider id)


# Canonical category names. Sources may only use these (UI groups by them).
CATEGORIES: tuple[str, ...] = (
    "Folders",
    "Drives & Storage",
    "Devices",
    "Media",
    "Network",
    "Security",
    "System",
    "Users",
    "Accessibility",
    "Power",
    "Web",
    "Documents",
    "Legacy",
)


@dataclass(frozen=True, slots=True)
class IconRef:
    kind: RefKind
    location: str
    resource_id: int | None = None


@dataclass(frozen=True, slots=True)
class IconEntry:
    id: str
    name: str
    source_id: str
    ref: IconRef
    categories: frozenset[str] = field(default_factory=frozenset)
    tags: frozenset[str] = field(default_factory=frozenset)
    license: str = "Unknown"
    kind: IconKind = IconKind.FULL

    def matches(self, needle: str) -> bool:
        """Case-insensitive match on name, tags and resource identifier."""
        n = needle.casefold().strip()
        if not n:
            return True
        if n in self.name.casefold():
            return True
        if any(n in t.casefold() for t in self.tags):
            return True
        return self.ref.resource_id is not None and n in str(self.ref.resource_id)


@dataclass(frozen=True, slots=True)
class SourceInfo:
    id: str
    name: str
    description: str
    section: Section
    license: str = "Unknown"
    requires_network: bool = False


@dataclass(frozen=True, slots=True)
class ApplyOptions:
    compose_on_folder_base: bool = False
    tint: str = "#F2C14E"


@dataclass(frozen=True, slots=True)
class ActionResult:
    ok: bool
    message: str
    affected: tuple[Path, ...] = ()
    simulated: bool = False


ICO_MAGIC = bytes((0, 0, 1, 0))  # ICONDIR: reserved=0, type=1 (icon)


class PayloadKind(StrEnum):
    RESOURCE = "resource"  # icon resource inside a DLL/EXE, referenced in place
    ICO = "ico"  # ready-to-write .ico file content


@dataclass(frozen=True, slots=True)
class IconPayload:
    """What will actually be written for a folder icon."""

    kind: PayloadKind
    location: str | None = None
    resource_id: int | None = None
    ico: bytes | None = None

    def __post_init__(self) -> None:
        if self.kind is PayloadKind.RESOURCE:
            if not self.location or self.resource_id is None or self.ico is not None:
                raise ValueError("resource payload needs location and resource_id only")
            if self.resource_id <= 0:
                raise ValueError("resource_id must be a positive resource identifier")
        else:
            if self.location is not None or self.resource_id is not None:
                raise ValueError("ico payload must not carry a resource reference")
            if not self.ico or not self.ico.startswith(ICO_MAGIC):
                raise ValueError("ico payload must be non-empty ICO data")

    @classmethod
    def resource(cls, location: str, resource_id: int) -> IconPayload:
        return cls(PayloadKind.RESOURCE, location=location, resource_id=resource_id)

    @classmethod
    def from_ico(cls, data: bytes) -> IconPayload:
        return cls(PayloadKind.ICO, ico=bytes(data))
