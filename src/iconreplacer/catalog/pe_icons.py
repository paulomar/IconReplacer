"""Read-only access to icon resources of PE files (DLL/EXE/.mun) via ctypes.

Modules are mapped with ``LoadLibraryExW(LOAD_LIBRARY_AS_DATAFILE |
LOAD_LIBRARY_AS_IMAGE_RESOURCE)``: no code runs, nothing is written. Icon groups
(``RT_GROUP_ICON``) are turned into in-memory ``.ico`` files by replacing each
``GRPICONDIRENTRY`` resource id with the matching ``RT_ICON`` payload offset.
"""

from __future__ import annotations

import contextlib
import ctypes
import struct
import sys
import threading
from dataclasses import dataclass

from iconreplacer.core.models import ICO_MAGIC

RT_ICON = 3
RT_GROUP_ICON = 14
LOAD_LIBRARY_AS_DATAFILE = 0x00000002
LOAD_LIBRARY_AS_IMAGE_RESOURCE = 0x00000020

IS_WINDOWS = sys.platform == "win32"

_GRP_HEADER = struct.Struct("<HHH")  # reserved, type, count
_GRP_ENTRY = struct.Struct("<BBBBHHIH")  # w, h, colors, reserved, planes, bpp, size, id
_ICO_ENTRY = struct.Struct("<BBBBHHII")  # w, h, colors, reserved, planes, bpp, size, offset


class PeIconError(OSError):
    """Raised when a module or resource cannot be read."""


@dataclass(frozen=True, slots=True)
class GroupImage:
    """One image of an icon group as declared by its directory."""

    width: int
    height: int
    bit_count: int
    size: int
    icon_id: int


if IS_WINDOWS:
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _ENUMRESNAMEPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
    )

    _k32.LoadLibraryExW.argtypes = (wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD)
    _k32.LoadLibraryExW.restype = wintypes.HMODULE
    _k32.FreeLibrary.argtypes = (wintypes.HMODULE,)
    _k32.FreeLibrary.restype = wintypes.BOOL
    _k32.EnumResourceNamesW.argtypes = (
        wintypes.HMODULE,
        ctypes.c_void_p,
        _ENUMRESNAMEPROC,
        ctypes.c_void_p,
    )
    _k32.EnumResourceNamesW.restype = wintypes.BOOL
    _k32.FindResourceW.argtypes = (wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p)
    _k32.FindResourceW.restype = ctypes.c_void_p
    _k32.LoadResource.argtypes = (wintypes.HMODULE, ctypes.c_void_p)
    _k32.LoadResource.restype = ctypes.c_void_p
    _k32.LockResource.argtypes = (ctypes.c_void_p,)
    _k32.LockResource.restype = ctypes.c_void_p
    _k32.SizeofResource.argtypes = (wintypes.HMODULE, ctypes.c_void_p)
    _k32.SizeofResource.restype = wintypes.DWORD


def _is_intresource(value: int | None) -> bool:
    return value is not None and (value >> 16) == 0


class PeModule:
    """A PE file mapped as a read-only resource image. Use as a context manager."""

    def __init__(self, path: str) -> None:
        if not IS_WINDOWS:
            raise PeIconError("PE resource access requires Windows")
        self.path = path
        self._lock = threading.RLock()
        handle = _k32.LoadLibraryExW(
            path, None, LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE
        )
        if not handle:
            raise PeIconError(ctypes.get_last_error(), f"cannot load {path}")
        self._handle: int | None = handle

    def __enter__(self) -> PeModule:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover - safety net
        with contextlib.suppress(Exception):
            self.close()

    @property
    def closed(self) -> bool:
        return self._handle is None

    def close(self) -> None:
        with self._lock:
            if self._handle:
                _k32.FreeLibrary(self._handle)
            self._handle = None

    def _require(self) -> int:
        if not self._handle:
            raise PeIconError(f"module closed: {self.path}")
        return self._handle

    def group_icon_ids(self) -> tuple[list[int], int]:
        """Integer ids of all RT_GROUP_ICON resources (sorted) and the number of
        string-named groups that were skipped."""
        ids: list[int] = []
        skipped = 0

        def _cb(_h, _type, name, _param) -> bool:
            nonlocal skipped
            if _is_intresource(name):
                ids.append(int(name))
            else:
                skipped += 1
            return True

        with self._lock:
            callback = _ENUMRESNAMEPROC(_cb)
            ok = _k32.EnumResourceNamesW(self._require(), RT_GROUP_ICON, callback, None)
        if not ok and not ids:
            # ERROR_RESOURCE_TYPE_NOT_FOUND (1813): module simply has no icons.
            return [], skipped
        return sorted(set(ids)), skipped

    def resource(self, res_type: int, res_id: int) -> bytes | None:
        """Raw bytes of an integer-identified resource, or None when absent."""
        with self._lock:
            h = self._require()
            info = _k32.FindResourceW(h, res_id, res_type)
            if not info:
                return None
            size = _k32.SizeofResource(h, info)
            loaded = _k32.LoadResource(h, info)
            if not loaded or not size:
                return None
            ptr = _k32.LockResource(loaded)
            if not ptr:
                return None
            return ctypes.string_at(ptr, size)

    def group_images(self, group_id: int) -> list[GroupImage]:
        data = self.resource(RT_GROUP_ICON, group_id)
        if data is None:
            raise PeIconError(f"icon group {group_id} not found in {self.path}")
        return parse_group(data)

    def ico_bytes(self, group_id: int) -> bytes:
        """Assemble a standalone .ico file from an icon group."""
        images = self.group_images(group_id)
        payloads: list[tuple[GroupImage, bytes]] = []
        for img in images:
            blob = self.resource(RT_ICON, img.icon_id)
            if blob:
                payloads.append((img, blob))
        if not payloads:
            raise PeIconError(f"icon group {group_id} has no readable images")
        return build_ico(payloads)


def parse_group(data: bytes) -> list[GroupImage]:
    """Parse a GRPICONDIR resource into its entries."""
    if len(data) < _GRP_HEADER.size:
        raise PeIconError("truncated icon group directory")
    _reserved, kind, count = _GRP_HEADER.unpack_from(data, 0)
    if kind != 1:
        raise PeIconError("not an icon group")
    out: list[GroupImage] = []
    off = _GRP_HEADER.size
    for _ in range(count):
        if off + _GRP_ENTRY.size > len(data):
            break
        w, h, _colors, _res, _planes, bpp, size, icon_id = _GRP_ENTRY.unpack_from(data, off)
        out.append(GroupImage(w or 256, h or 256, bpp, size, icon_id))
        off += _GRP_ENTRY.size
    return out


def _png_size(blob: bytes) -> tuple[int, int] | None:
    if blob.startswith(b"\x89PNG\r\n\x1a\n") and len(blob) >= 24:
        return struct.unpack(">II", blob[16:24])
    return None


def build_ico(payloads: list[tuple[GroupImage, bytes]]) -> bytes:
    """Build ICONDIR + ICONDIRENTRY[] + image data (PNG or DIB payloads)."""
    header = ICO_MAGIC + struct.pack("<H", len(payloads))
    offset = len(header) + _ICO_ENTRY.size * len(payloads)
    entries = bytearray()
    body = bytearray()
    for img, blob in payloads:
        w, h = img.width, img.height
        png = _png_size(blob)
        if png:
            w, h = png
        entries += _ICO_ENTRY.pack(
            0 if w >= 256 else w,
            0 if h >= 256 else h,
            0,
            0,
            1,
            img.bit_count,
            len(blob),
            offset,
        )
        body += blob
        offset += len(blob)
    return bytes(header) + bytes(entries) + bytes(body)
