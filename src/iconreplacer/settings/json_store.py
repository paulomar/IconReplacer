"""JSON-backed settings store: typed defaults, validation, atomic writes, corrupt recovery."""

from __future__ import annotations

import base64
import binascii
import contextlib
import json
import logging
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from iconreplacer.core import paths

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
THUMB_MIN, THUMB_MAX = 16, 256
THEMES = ("system", "light", "dark")


@dataclass(frozen=True)
class Spec:
    default: Any
    coerce: Callable[[Any], Any]


def _bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    raise ValueError("expected a boolean")


def _theme(v: Any) -> str:
    if isinstance(v, str) and v in THEMES:
        return v
    raise ValueError(f"expected one of {THEMES}")


def _str(v: Any) -> str:
    if isinstance(v, str):
        return v
    raise ValueError("expected a string")


def _geometry(v: Any) -> str | None:
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValueError("expected base64 text or null")
    try:
        base64.b64decode(v, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid base64") from exc
    return v


def _thumb(v: Any) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not THUMB_MIN <= v <= THUMB_MAX:
        raise ValueError(f"expected an integer in {THUMB_MIN}..{THUMB_MAX}")
    return v


def _str_list(v: Any) -> list[str]:
    if isinstance(v, list) and all(isinstance(i, str) for i in v):
        return list(v)
    raise ValueError("expected a list of strings")


def _abs_paths(v: Any) -> list[str]:
    items = _str_list(v)
    if not all(Path(i).is_absolute() for i in items):
        raise ValueError("expected absolute paths")
    return items


SPECS: dict[str, Spec] = {
    "network.allowed": Spec(True, _bool),
    "ui.theme": Spec("system", _theme),
    "ui.language": Spec("", _str),
    "ui.sources_visible": Spec(False, _bool),
    "ui.window_geometry": Spec(None, _geometry),
    "ui.thumb_size": Spec(48, _thumb),
    "sources.disabled": Spec([], _str_list),
    "sources.local_folders": Spec([], _abs_paths),
}


def _fresh(value: Any) -> Any:
    return list(value) if isinstance(value, list) else value


class JsonSettingsStore:
    """Implements the SettingsStore protocol on top of a JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else paths.settings_path()
        self._values: dict[str, Any] = {}
        self._load()

    # -- protocol ----------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        if key in self._values:
            return _fresh(self._values[key])
        spec = SPECS.get(key)
        if spec is not None:
            return _fresh(spec.default)
        return default

    def set(self, key: str, value: Any) -> None:
        spec = SPECS.get(key)
        if spec is not None:
            try:
                value = spec.coerce(value)
            except ValueError as exc:
                log.warning("Rejected invalid value for setting %s: %s", key, exc)
                return
        self._values[key] = _fresh(value)
        self.save()

    # -- persistence -------------------------------------------------------------
    def _load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except (OSError, UnicodeDecodeError) as exc:
            log.warning("Cannot read settings %s: %s", self.path, exc)
            self._quarantine()
            return
        try:
            doc = json.loads(raw)
            values = doc["values"]
            if not isinstance(values, dict):
                raise TypeError("values is not an object")
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("Corrupt settings file %s: %s", self.path, exc)
            self._quarantine()
            return
        for key, value in values.items():
            spec = SPECS.get(key)
            if spec is None:
                self._values[key] = value  # unknown keys are preserved untouched
                continue
            try:
                self._values[key] = spec.coerce(value)
            except ValueError as exc:
                log.warning("Invalid stored value for %s (%s); using the default", key, exc)

    def _quarantine(self) -> None:
        target = self.path.with_name(f"{self.path.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
        try:
            os.replace(self.path, target)
        except OSError as exc:
            log.warning("Could not move aside %s: %s", self.path, exc)

    def save(self) -> bool:
        """Atomically write the file; never raises. Returns False on failure."""
        doc = {"version": SCHEMA_VERSION, "values": self._values}
        tmp_name = ""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=self.path.parent, prefix=self.path.name + ".", suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
            return True
        except OSError as exc:
            log.warning("Could not save settings %s: %s", self.path, exc)
            if tmp_name:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_name)
            return False
