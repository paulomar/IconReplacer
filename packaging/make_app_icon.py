"""Paint the original IconReplacer application icon (folder + sparkle) into an ICO.

No third-party artwork is used: everything is drawn with QPainter primitives.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from iconreplacer.converter.ico import STANDARD_SIZES, build_ico  # noqa: E402
from iconreplacer.ui.app_icon import render  # noqa: E402


def build(path: Path, sizes: tuple[int, ...] = STANDARD_SIZES) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_ico({s: render(s) for s in sizes}))
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "app.ico"
    print(build(out))
