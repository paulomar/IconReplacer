"""Decides whether a folder may receive a custom icon.

Environment variables are read on every call so tests can redirect them.
"""

from __future__ import annotations

import contextlib
import os
import stat
import uuid
from pathlib import Path

# Environment variables naming trees that must never be customized.
PROTECTED_TREES: tuple[str, ...] = (
    "SystemRoot",
    "windir",
    "ProgramFiles",
    "ProgramFiles(x86)",
    "ProgramW6432",
    "ProgramData",
)
# Only the folder itself is protected; its subfolders are allowed.
PROTECTED_EXACT: tuple[str, ...] = ("USERPROFILE",)

_NAME_SURROGATE_BIT = 0x20000000  # IsReparseTagNameSurrogate: symlinks, junctions


class UnsafeFolderError(Exception):
    """The folder must not be modified; ``str(exc)`` is a short English reason."""


def _norm(path: Path) -> str:
    return os.path.normcase(str(path)).rstrip("\\/")


def _resolve_env(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    try:
        return Path(os.path.abspath(value)).resolve(strict=False)
    except OSError:
        return Path(os.path.abspath(value))


def _is_within(path: Path, root: Path) -> bool:
    p, r = _norm(path), _norm(root)
    return p == r or p.startswith(r + "\\")


def _is_link(path: str) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    if attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        return bool(getattr(st, "st_reparse_tag", 0) & _NAME_SURROGATE_BIT)
    return False


def _check_no_links(absolute: str) -> None:
    current = absolute
    while True:
        if _is_link(current):
            raise UnsafeFolderError(
                "Symbolic links and junctions are not supported."
                if current == absolute
                else "The path goes through a symbolic link or junction."
            )
        parent = os.path.dirname(current)
        if parent == current:
            return
        current = parent


def _check_writable(folder: Path) -> None:
    probe = folder / f".iconreplacer-probe-{uuid.uuid4().hex}.tmp"
    try:
        with open(probe, "xb"):
            pass
    except OSError as exc:
        raise UnsafeFolderError("The folder cannot be written.") from exc
    with contextlib.suppress(OSError):
        probe.unlink()


def check_folder(folder: str | os.PathLike[str], *, check_write: bool = True) -> Path:
    """Return the resolved folder path or raise ``UnsafeFolderError``."""
    absolute = os.path.abspath(os.fspath(folder))  # collapses ".." without following links
    if not os.path.lexists(absolute):
        raise UnsafeFolderError("The folder does not exist.")
    _check_no_links(absolute)
    if not os.path.isdir(absolute):
        raise UnsafeFolderError("The path is not a folder.")
    try:
        resolved = Path(absolute).resolve(strict=True)  # expands 8.3 short names
    except OSError as exc:
        raise UnsafeFolderError("The folder cannot be accessed.") from exc

    if resolved.parent == resolved:
        raise UnsafeFolderError("Drive and share roots are not supported.")
    for name in PROTECTED_TREES:
        root = _resolve_env(name)
        if root is not None and _is_within(resolved, root):
            raise UnsafeFolderError("System and program folders are protected.")
    for name in PROTECTED_EXACT:
        root = _resolve_env(name)
        if root is not None and _norm(resolved) == _norm(root):
            raise UnsafeFolderError("The user profile folder itself is protected.")
    if check_write:
        _check_writable(resolved)
    return resolved
