"""Per-user Explorer folder context-menu verb (static verb under HKCU).

Only ``HKCU\\Software\\Classes\\Directory\\shell\\IconReplacer`` (and its ``command``
subkey) is ever written. The real backend refuses any other path. On Windows 11
the entry appears under "Show more options" (classic menu).
"""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

VERB_KEY = r"Software\Classes\Directory\shell\IconReplacer"
COMMAND_KEY = VERB_KEY + r"\command"
VERB_TEXT = "Replace Icon"
_ALLOWED_KEYS = frozenset({VERB_KEY.lower(), COMMAND_KEY.lower()})


class RegistryBackend(Protocol):
    """Minimal registry surface (paths are relative to HKEY_CURRENT_USER)."""

    def read_values(self, key: str) -> dict[str, str] | None:
        """Return the string values of ``key`` or ``None`` if the key is absent."""

    def write_values(self, key: str, values: dict[str, str]) -> None:
        """Create ``key`` if needed and set the string values ("" is the default value)."""

    def delete_key(self, key: str) -> None:
        """Delete ``key`` (must have no subkeys); absent key is not an error."""


class WinregBackend:
    """Real HKCU backend, hard-locked to the IconReplacer verb keys."""

    @staticmethod
    def _check(key: str) -> None:
        if key.lower() not in _ALLOWED_KEYS:
            raise PermissionError(f"refusing to touch registry key: {key!r}")

    def read_values(self, key: str) -> dict[str, str] | None:
        import winreg

        self._check(key)
        try:
            handle = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ)
        except FileNotFoundError:
            return None
        values: dict[str, str] = {}
        with handle:
            i = 0
            while True:
                try:
                    name, data, _kind = winreg.EnumValue(handle, i)
                except OSError:
                    break
                values[name] = str(data)
                i += 1
        return values

    def write_values(self, key: str, values: dict[str, str]) -> None:
        import winreg

        self._check(key)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_WRITE) as handle:
            for name, data in values.items():
                winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, data)

    def delete_key(self, key: str) -> None:
        import winreg

        self._check(key)
        with contextlib.suppress(FileNotFoundError):
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)


class RegistrationState(Enum):
    NOT_REGISTERED = "not registered"
    REGISTERED = "registered"
    STALE = "stale"


@dataclass(frozen=True)
class RegistrationStatus:
    state: RegistrationState
    path: str | None = None  # launcher found in the registered command, if any

    def __str__(self) -> str:
        if self.path and self.state is not RegistrationState.NOT_REGISTERED:
            return f"{self.state.value} ({self.path})"
        return self.state.value


def _quote(path: str) -> str:
    return f'"{path}"'


def default_launcher() -> tuple[str, tuple[str, ...]]:
    """Return ``(executable, extra_args)`` used to start the app from Explorer."""
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve()), ()
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    return str(pythonw if pythonw.exists() else exe), ("-m", "iconreplacer")


def build_command(launcher: str, extra_args: tuple[str, ...] = ()) -> str:
    parts = [_quote(launcher), *extra_args, "--folder", '"%1"']
    return " ".join(parts)


def parse_launcher(command: str) -> str | None:
    """Extract the executable path from a stored command line."""
    command = command.strip()
    if not command:
        return None
    if command.startswith('"'):
        end = command.find('"', 1)
        return command[1:end] if end > 1 else None
    return command.split(" ", 1)[0]


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


class ShellRegistration:
    """Register, query and remove the folder verb. UI-agnostic."""

    def __init__(
        self,
        backend: RegistryBackend | None = None,
        launcher: str | None = None,
        extra_args: tuple[str, ...] | None = None,
    ) -> None:
        self._backend = backend or WinregBackend()
        if launcher is None:
            launcher, detected = default_launcher()
            extra_args = detected if extra_args is None else extra_args
        self.launcher = launcher
        self.extra_args = extra_args or ()

    @property
    def command(self) -> str:
        return build_command(self.launcher, self.extra_args)

    def status(self) -> RegistrationStatus:
        verb = self._backend.read_values(VERB_KEY)
        cmd = self._backend.read_values(COMMAND_KEY)
        if verb is None and cmd is None:
            return RegistrationStatus(RegistrationState.NOT_REGISTERED)
        stored = (cmd or {}).get("", "")
        registered = parse_launcher(stored)
        if (
            registered is not None
            and verb is not None
            and _same_path(registered, self.launcher)
            and stored.strip() == self.command
            and Path(registered).exists()
        ):
            return RegistrationStatus(RegistrationState.REGISTERED, registered)
        return RegistrationStatus(RegistrationState.STALE, registered)

    def register(self) -> None:
        self._backend.write_values(
            VERB_KEY, {"": VERB_TEXT, "MUIVerb": VERB_TEXT, "Icon": self.launcher}
        )
        self._backend.write_values(COMMAND_KEY, {"": self.command})

    def unregister(self) -> None:
        self._backend.delete_key(COMMAND_KEY)
        self._backend.delete_key(VERB_KEY)
