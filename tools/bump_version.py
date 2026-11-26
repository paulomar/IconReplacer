"""Bump the IconReplacer version in src/iconreplacer/version.py.

Usage: python tools/bump_version.py {build|patch|minor|major} [--file PATH]

BUILD always increases by one and never resets. ``patch`` / ``minor`` /
``major`` additionally bump that part and reset the lower SemVer parts.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "src" / "iconreplacer" / "version.py"
PARTS = ("build", "patch", "minor", "major")

_TUPLE_RE = re.compile(r"VERSION: tuple\[int, int, int, int\] = \((\d+), (\d+), (\d+), (\d+)\)")
_STR_RE = re.compile(r'__version__ = "[^"]+"')


def bump(version: tuple[int, int, int, int], part: str) -> tuple[int, int, int, int]:
    """Return the next version for ``part``; BUILD is incremented for every part."""
    if part not in PARTS:
        raise ValueError(f"unknown part: {part!r}")
    major, minor, patch, build = version
    build += 1
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "major":
        major, minor, patch = major + 1, 0, 0
    return (major, minor, patch, build)


def read_version(text: str) -> tuple[int, int, int, int]:
    match = _TUPLE_RE.search(text)
    if not match:
        raise ValueError("VERSION tuple not found")
    a, b, c, d = (int(g) for g in match.groups())
    return (a, b, c, d)


def rewrite(text: str, version: tuple[int, int, int, int]) -> str:
    dotted = ".".join(str(p) for p in version)
    text = _TUPLE_RE.sub(
        f"VERSION: tuple[int, int, int, int] = ({', '.join(map(str, version))})", text
    )
    return _STR_RE.sub(f'__version__ = "{dotted}"', text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=PARTS)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    args = parser.parse_args(argv)
    text = args.file.read_text(encoding="utf-8")
    new = bump(read_version(text), args.part)
    args.file.write_text(rewrite(text, new), encoding="utf-8")
    print(".".join(map(str, new)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
