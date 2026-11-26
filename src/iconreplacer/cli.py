"""Command-line parsing for IconReplacer."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from iconreplacer.version import FULL_VERSION, PRODUCT_NAME


@dataclass(frozen=True)
class CliOptions:
    folders: tuple[Path, ...] = field(default_factory=tuple)
    shell_action: str | None = None  # "register" | "unregister" | "status"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="iconreplacer", description="Replace folder icons.")
    parser.add_argument(
        "--folder",
        action="append",
        default=[],
        metavar="PATH",
        help="Target folder (repeat for batch mode).",
    )
    shell = parser.add_mutually_exclusive_group()
    shell.add_argument(
        "--register",
        dest="shell_action",
        action="store_const",
        const="register",
        help="Add the per-user Explorer 'Replace Icon' folder verb.",
    )
    shell.add_argument(
        "--unregister",
        dest="shell_action",
        action="store_const",
        const="unregister",
        help="Remove the Explorer folder verb.",
    )
    shell.add_argument(
        "--status",
        dest="shell_action",
        action="store_const",
        const="status",
        help="Print the Explorer verb registration status (exit 0 if registered).",
    )
    parser.add_argument("--version", action="version", version=f"{PRODUCT_NAME} {FULL_VERSION}")
    return parser


def run_shell_action(action: str, registration=None) -> int:
    """Run ``--register/--unregister/--status``; prints the result, returns the exit code."""
    from iconreplacer.shell.registration import RegistrationState, ShellRegistration

    reg = registration or ShellRegistration()
    try:
        if action == "register":
            reg.register()
        elif action == "unregister":
            reg.unregister()
        status = reg.status()
    except OSError as exc:
        print(f"error: {exc}")
        return 1
    print(status)
    if action == "register":
        return 0 if status.state is RegistrationState.REGISTERED else 1
    if action == "unregister":
        return 0 if status.state is RegistrationState.NOT_REGISTERED else 1
    return 0 if status.state is RegistrationState.REGISTERED else 1


def parse_args(argv: list[str] | None = None) -> CliOptions:
    """Parse ``argv``. ``--version`` prints and raises ``SystemExit(0)``."""
    ns = build_parser().parse_args(argv)
    seen: dict[str, Path] = {}
    for raw in ns.folder:
        p = Path(raw)
        seen.setdefault(str(p).lower(), p)  # de-duplicate, Windows paths are case-insensitive
    return CliOptions(folders=tuple(seen.values()), shell_action=ns.shell_action)
