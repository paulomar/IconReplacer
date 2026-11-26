"""Procedural mock icon sources for the UI prototype.

No real artwork is used: glyphs are drawn with QPainter from a deterministic
seed so the prototype can be validated without extracting or shipping icons.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property

from iconreplacer.core.models import (
    IconEntry,
    IconKind,
    IconRef,
    RefKind,
    Section,
    SourceInfo,
)


@dataclass(frozen=True, slots=True)
class LibrarySpec:
    file: str
    description: str
    categories: tuple[str, ...]
    count: int


# The Windows icon libraries from the product research (descriptions are ours).
SYSTEM_LIBRARIES: tuple[LibrarySpec, ...] = (
    LibrarySpec(
        "imageres.dll",
        "Modern Windows icons: colored folders, drives, actions, alerts",
        ("Folders", "Drives & Storage", "System", "Security"),
        420,
    ),
    LibrarySpec(
        "shell32.dll",
        "Classic Explorer icons: folders, files, shortcuts, system",
        ("Folders", "Documents", "System"),
        330,
    ),
    LibrarySpec("ddores.dll", "Hardware devices and peripherals", ("Devices",), 140),
    LibrarySpec("wmploc.dll", "Media, players, music, video and playlists", ("Media",), 110),
    LibrarySpec("mmres.dll", "Audio, speakers, microphones and volume", ("Media", "Devices"), 40),
    LibrarySpec(
        "netshell.dll", "Network connections, adapters, Wi-Fi and cables", ("Network",), 60
    ),
    LibrarySpec("networkexplorer.dll", "Sharing, servers and LAN devices", ("Network",), 30),
    LibrarySpec("pnidui.dll", "Network status and tray icons", ("Network", "System"), 50),
    LibrarySpec("wpdshext.dll", "Portable devices: phones, cameras, cards", ("Devices",), 35),
    LibrarySpec("wiashext.dll", "Scanners and image capture devices", ("Devices",), 25),
    LibrarySpec("setupapi.dll", "Driver setup and internal hardware", ("Devices", "System"), 60),
    LibrarySpec(
        "dmdskres.dll", "Disk management, partitions and storage", ("Drives & Storage",), 20
    ),
    LibrarySpec(
        "dsuiext.dll", "Directory services: users, groups, domains", ("Users", "Network"), 40
    ),
    LibrarySpec(
        "accessibilitycpl.dll",
        "Accessibility: magnifier, on-screen keyboard",
        ("Accessibility",),
        30,
    ),
    LibrarySpec("sensorscpl.dll", "Sensors: location, gyroscope, light", ("Devices",), 15),
    LibrarySpec("powercpl.dll", "Power, battery, sleep and hibernation", ("Power",), 20),
    LibrarySpec("mstscax.dll", "Remote Desktop and external connections", ("Network",), 25),
    LibrarySpec("ieframe.dll", "Web navigation, favorites and security", ("Web", "Security"), 90),
    LibrarySpec("mmcndmgr.dll", "Management Console administrative icons", ("System",), 120),
    LibrarySpec(
        "compstui.dll", "Legacy printing, pages and UI settings", ("Devices", "Legacy"), 100
    ),
    LibrarySpec("pifmgr.dll", "Retro Windows 95/98 objects", ("Legacy",), 38),
    LibrarySpec("moricons.dll", "MS-DOS and Windows 3.1/NT legacy icons", ("Legacy",), 110),
)

ONLINE_SOURCES: tuple[tuple[SourceInfo, tuple[str, ...], int], ...] = (
    (
        SourceInfo(
            "iconify",
            "Iconify",
            "200k+ open-source icons from 150+ sets",
            Section.ONLINE,
            "Per set (shown per icon)",
            True,
        ),
        ("Folders", "Documents", "Media", "Network", "Devices", "Web", "Users"),
        400,
    ),
    (
        SourceInfo(
            "phosphor", "Phosphor", "Flexible icon family, six weights", Section.ONLINE, "MIT", True
        ),
        ("Folders", "Documents", "Media", "Devices", "Users", "Security"),
        300,
    ),
    (
        SourceInfo(
            "gh-windowsicons",
            "LaviMahal/WindowsIcons",
            "Windows-style icon pack (GitHub)",
            Section.ONLINE,
            "See repository",
            True,
        ),
        ("Folders", "System"),
        120,
    ),
    (
        SourceInfo(
            "gh-folder-icons",
            "sameerasw/folder-icons",
            "Colorful folder icons (GitHub)",
            Section.ONLINE,
            "See repository",
            True,
        ),
        ("Folders",),
        90,
    ),
)

LOCAL_SOURCES: tuple[tuple[SourceInfo, tuple[str, ...], int], ...] = (
    (
        SourceInfo("local-my-icons", "My Icons", r"D:\Icons", Section.LOCAL, "User provided"),
        ("Folders", "Media"),
        48,
    ),
)

_WORDS: dict[str, tuple[str, ...]] = {
    "Folders": ("folder", "library", "archive", "projects", "downloads", "pictures"),
    "Drives & Storage": ("drive", "disk", "ssd", "usb", "partition", "optical"),
    "Devices": ("printer", "monitor", "mouse", "keyboard", "camera", "phone", "headset"),
    "Media": ("music", "video", "playlist", "speaker", "microphone", "album"),
    "Network": ("network", "wifi", "ethernet", "server", "share", "globe"),
    "Security": ("shield", "lock", "key", "certificate", "warning"),
    "System": ("gear", "settings", "terminal", "window", "registry", "task"),
    "Users": ("user", "group", "domain", "contact", "team"),
    "Accessibility": ("magnifier", "narrator", "contrast", "keyboard-osk"),
    "Power": ("battery", "power", "sleep", "hibernate", "plug"),
    "Web": ("browser", "favorite", "bookmark", "link", "history"),
    "Documents": ("document", "text", "sheet", "pdf", "code", "note"),
    "Legacy": ("dos", "retro", "floppy", "joystick", "terminal-old"),
}


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.blake2s(text.encode(), digest_size=4).digest(), "big")


class MockIconSource:
    """IconSource implementation producing deterministic procedural icons."""

    def __init__(
        self,
        info: SourceInfo,
        categories: Sequence[str],
        count: int,
        kind: IconKind,
        location: str | None = None,
    ) -> None:
        self._info = info
        self._categories = tuple(categories)
        self._count = count
        self._kind = kind
        self._location = location or info.name

    @property
    def info(self) -> SourceInfo:
        return self._info

    @cached_property
    def _entries(self) -> tuple[IconEntry, ...]:
        out = []
        for i in range(self._count):
            seed = _seed(f"{self._info.id}:{i}")
            primary = self._categories[seed % len(self._categories)]
            cats = {primary}
            if len(self._categories) > 1 and seed % 5 == 0:
                cats.add(self._categories[(seed // 7) % len(self._categories)])
            words = _WORDS[primary]
            word = words[(seed // 3) % len(words)]
            res_id = 1 + i if self._info.section is Section.SYSTEM else None
            ref_kind = {
                Section.SYSTEM: RefKind.RESOURCE,
                Section.ONLINE: RefKind.REMOTE,
                Section.LOCAL: RefKind.FILE,
            }[self._info.section]
            location = (
                f"%SystemRoot%\\System32\\{self._location}"
                if self._info.section is Section.SYSTEM
                else f"{self._location}/{word}-{i}"
            )
            out.append(
                IconEntry(
                    id=f"{self._info.id}:{i}",
                    name=f"{word.replace('-', ' ').title()} {i + 1}",
                    source_id=self._info.id,
                    ref=IconRef(ref_kind, location, res_id),
                    categories=frozenset(cats),
                    tags=frozenset({word, *(c.lower() for c in cats)}),
                    license=self._info.license,
                    kind=self._kind,
                )
            )
        return tuple(out)

    def entries(self) -> Sequence[IconEntry]:
        return self._entries

    def render(self, entry: IconEntry, size: int):  # -> QImage
        from iconreplacer.ui.glyphs import render_mock_glyph

        return render_mock_glyph(entry, size)


def build_mock_sources(scale: float = 1.0) -> list[MockIconSource]:
    """All prototype sources. ``scale`` multiplies counts (e.g. for 10k tests)."""
    sources: list[MockIconSource] = []
    for lib in SYSTEM_LIBRARIES:
        info = SourceInfo(
            id=lib.file.lower(),
            name=lib.file,
            description=lib.description,
            section=Section.SYSTEM,
            license="Microsoft (referenced in place, not redistributed)",
        )
        sources.append(
            MockIconSource(
                info, lib.categories, max(1, round(lib.count * scale)), IconKind.FULL, lib.file
            )
        )
    for info, cats, count in ONLINE_SOURCES:
        sources.append(MockIconSource(info, cats, max(1, round(count * scale)), IconKind.GLYPH))
    for info, cats, count in LOCAL_SOURCES:
        sources.append(
            MockIconSource(
                info, cats, max(1, round(count * scale)), IconKind.FULL, info.description
            )
        )
    return sources
