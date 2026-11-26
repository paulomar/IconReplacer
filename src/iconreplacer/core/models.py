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
