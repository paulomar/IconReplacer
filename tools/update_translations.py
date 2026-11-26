"""Regenerate the translation template from all UI sources.

Usage: uv run python tools/update_translations.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "iconreplacer"
TS = PKG / "i18n" / "iconreplacer_en.ts"


def main() -> int:
    lupdate = shutil.which("pyside6-lupdate")
    if lupdate is None:
        print("pyside6-lupdate not found; run inside the project environment (uv run).")
        return 1
    sources = sorted(str(p) for p in PKG.rglob("*.py"))
    return subprocess.call([lupdate, *sources, "-no-obsolete", "-ts", str(TS)])


if __name__ == "__main__":
    sys.exit(main())
