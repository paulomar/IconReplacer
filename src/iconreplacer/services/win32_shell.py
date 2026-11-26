"""Minimal ctypes bindings to kernel32/shell32 used by the folder icon service.

Every call declares argtypes/restype and turns failures into ``OSError``.
Nothing here requests elevation or touches the registry.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes as wt
from pathlib import Path

FILE_ATTRIBUTE_READONLY = 0x0001
FILE_ATTRIBUTE_HIDDEN = 0x0002
FILE_ATTRIBUTE_SYSTEM = 0x0004
FILE_ATTRIBUTE_DIRECTORY = 0x0010
FILE_ATTRIBUTE_ARCHIVE = 0x0020
FILE_ATTRIBUTE_NORMAL = 0x0080
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
FILE_ATTRIBUTE_NOT_CONTENT_INDEXED = 0x2000
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

# Bits that SetFileAttributesW can change and that we snapshot/restore.
SETTABLE_ATTRIBUTES = (
    FILE_ATTRIBUTE_READONLY
    | FILE_ATTRIBUTE_HIDDEN
    | FILE_ATTRIBUTE_SYSTEM
    | FILE_ATTRIBUTE_ARCHIVE
    | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED
)

FCSM_ICONFILE = 0x00000010
FCS_FORCEWRITE = 0x00000002

SHCNE_UPDATEDIR = 0x00001000
SHCNE_UPDATEITEM = 0x00002000
SHCNF_PATHW = 0x0005
SHCNF_FLUSHNOWAIT = 0x3000


class SHFOLDERCUSTOMSETTINGS(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("dwMask", wt.DWORD),
        ("pvid", ctypes.c_void_p),
        ("pszWebViewTemplate", wt.LPWSTR),
        ("cchWebViewTemplate", wt.DWORD),
        ("pszWebViewTemplateVersion", wt.LPWSTR),
        ("pszInfoTip", wt.LPWSTR),
        ("cchInfoTip", wt.DWORD),
        ("pclsid", ctypes.c_void_p),
        ("dwFlags", wt.DWORD),
        ("pszIconFile", wt.LPWSTR),
        ("cchIconFile", wt.DWORD),
        ("iIconIndex", ctypes.c_int),
        ("pszLogo", wt.LPWSTR),
        ("cchLogo", wt.DWORD),
    ]


def _bind():
    if sys.platform != "win32":  # pragma: no cover - Windows-only tool
        raise OSError("IconReplacer folder icons require Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    get_attrs = kernel32.GetFileAttributesW
    get_attrs.argtypes = [wt.LPCWSTR]
    get_attrs.restype = wt.DWORD

    set_attrs = kernel32.SetFileAttributesW
    set_attrs.argtypes = [wt.LPCWSTR, wt.DWORD]
    set_attrs.restype = wt.BOOL

    custom = shell32.SHGetSetFolderCustomSettings
    custom.argtypes = [ctypes.POINTER(SHFOLDERCUSTOMSETTINGS), wt.LPCWSTR, wt.DWORD]
    custom.restype = ctypes.c_long  # HRESULT, checked manually

    notify = shell32.SHChangeNotify
    notify.argtypes = [wt.LONG, wt.UINT, wt.LPCVOID, wt.LPCVOID]
    notify.restype = None
    return get_attrs, set_attrs, custom, notify


_GET_ATTRS, _SET_ATTRS, _CUSTOM_SETTINGS, _CHANGE_NOTIFY = _bind()


def _last_error(path: str | os.PathLike[str]) -> OSError:
    code = ctypes.get_last_error()
    return OSError(0, ctypes.FormatError(code).strip(), str(path), code)


def get_attributes(path: str | os.PathLike[str]) -> int:
    value = _GET_ATTRS(str(path))
    if value == INVALID_FILE_ATTRIBUTES:
        raise _last_error(path)
    return int(value)


def set_attributes(path: str | os.PathLike[str], attributes: int) -> None:
    value = attributes & SETTABLE_ATTRIBUTES or FILE_ATTRIBUTE_NORMAL
    if not _SET_ATTRS(str(path), value):
        raise _last_error(path)


def set_folder_icon(folder: str | os.PathLike[str], icon_file: str, index: int) -> None:
    """Write IconResource through SHGetSetFolderCustomSettings (FCS_FORCEWRITE)."""
    settings = SHFOLDERCUSTOMSETTINGS()
    settings.dwSize = ctypes.sizeof(SHFOLDERCUSTOMSETTINGS)
    settings.dwMask = FCSM_ICONFILE
    settings.pszIconFile = icon_file
    settings.cchIconFile = 0
    settings.iIconIndex = index
    hr = _CUSTOM_SETTINGS(ctypes.byref(settings), str(folder), FCS_FORCEWRITE)
    if hr < 0:
        code = hr & 0xFFFFFFFF
        raise OSError(0, ctypes.FormatError(code).strip() or f"HRESULT 0x{code:08X}", str(folder))


def notify_updated(folder: str | os.PathLike[str]) -> None:
    """Tell Explorer that the folder (and its icon) changed."""
    path = ctypes.c_wchar_p(str(folder))
    _CHANGE_NOTIFY(SHCNE_UPDATEITEM, SHCNF_PATHW | SHCNF_FLUSHNOWAIT, path, None)
    _CHANGE_NOTIFY(SHCNE_UPDATEDIR, SHCNF_PATHW | SHCNF_FLUSHNOWAIT, path, None)


class Win32Shell:
    """Injectable facade over the bindings (tests may substitute parts)."""

    def get_attributes(self, path: Path) -> int:
        return get_attributes(path)

    def set_attributes(self, path: Path, attributes: int) -> None:
        set_attributes(path, attributes)

    def set_folder_icon(self, folder: Path, icon_file: str, index: int) -> None:
        set_folder_icon(folder, icon_file, index)

    def notify_updated(self, folder: Path) -> None:
        notify_updated(folder)
