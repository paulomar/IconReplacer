"""Storage locations: override > portable (next to the app) > %LOCALAPPDATA%.

Nothing is created outside the selected data root, and only on demand.
"""

from __future__ import annotations

import contextlib
import os
import sys
import uuid
from functools import cache
from pathlib import Path

ENV_HOME = "ICONREPLACER_HOME"
APP_FOLDER = "IconReplacer"


def app_dir() -> Path:
    """Directory of the frozen executable, or the repository root in development."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _is_writable(directory: Path) -> bool:
    probe = directory / f".write-probe-{uuid.uuid4().hex}"
    try:
        probe.write_bytes(b"")
    except OSError:
        return False
    with contextlib.suppress(OSError):
        probe.unlink()
    return True


@cache
def data_root() -> Path:
    override = os.environ.get(ENV_HOME)
    if override:
        return Path(override)
    base = app_dir()
    if base.is_dir() and _is_writable(base):
        return base / "data"
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / APP_FOLDER


def reset_cache() -> None:
    """Forget the memoized root (tests / environment changes)."""
    data_root.cache_clear()


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return _ensure(data_root()) / "settings.json"


def cache_dir(name: str | None = None) -> Path:
    if name is not None and (not name or any(c in name for c in '\\/:*?"<>|') or ".." in name):
        raise ValueError(f"invalid cache name: {name!r}")
    root = data_root() / "cache"
    return _ensure(root / name if name else root)


def log_dir() -> Path:
    return _ensure(data_root() / "logs")
