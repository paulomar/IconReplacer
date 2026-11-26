"""Regenerate the translation template, or compile translations.

Usage:
    uv run python tools/update_translations.py             # .py -> iconreplacer_en.ts
    uv run python tools/update_translations.py --release   # every .ts -> .qm (git-ignored)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "iconreplacer"
I18N = PKG / "i18n"
TS = I18N / "iconreplacer_en.ts"


def update() -> int:
    lupdate = shutil.which("pyside6-lupdate")
    if lupdate is None:
        print("pyside6-lupdate not found; run inside the project environment (uv run).")
        return 1
    sources = sorted(str(p) for p in PKG.rglob("*.py"))
    return subprocess.call([lupdate, *sources, "-no-obsolete", "-ts", str(TS)])


def release() -> int:
    lrelease = shutil.which("pyside6-lrelease")
    if lrelease is None:
        print("pyside6-lrelease not found; run inside the project environment (uv run).")
        return 1
    status = 0
    for ts in sorted(I18N.glob("iconreplacer_*.ts")):
        status |= subprocess.call([lrelease, str(ts), "-qm", str(ts.with_suffix(".qm"))])
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--release", action="store_true", help="compile .ts files into .qm")
    args = parser.parse_args(argv)
    return release() if args.release else update()


if __name__ == "__main__":
    sys.exit(main())
