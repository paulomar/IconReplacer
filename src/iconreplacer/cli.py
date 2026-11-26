"""Command-line parsing for IconReplacer."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from iconreplacer.version import FULL_VERSION, PRODUCT_NAME


@dataclass(frozen=True)
class CliOptions:
    folders: tuple[Path, ...] = field(default_factory=tuple)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="iconreplacer", description="Replace folder icons.")
    parser.add_argument(
        "--folder",
        action="append",
        default=[],
        metavar="PATH",
        help="Target folder (repeat for batch mode).",
    )
    parser.add_argument("--version", action="version", version=f"{PRODUCT_NAME} {FULL_VERSION}")
    return parser


def parse_args(argv: list[str] | None = None) -> CliOptions:
    """Parse ``argv``. ``--version`` prints and raises ``SystemExit(0)``."""
    ns = build_parser().parse_args(argv)
    seen: dict[str, Path] = {}
    for raw in ns.folder:
        p = Path(raw)
        seen.setdefault(str(p).lower(), p)  # de-duplicate, Windows paths are case-insensitive
    return CliOptions(folders=tuple(seen.values()))
