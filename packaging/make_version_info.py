"""Render a PyInstaller VSVersionInfo file from ``iconreplacer.version``."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from iconreplacer import version as v  # noqa: E402

COMPANY = "IconReplacer contributors"
COPYRIGHT = "Copyright (c) 2026 IconReplacer contributors. MIT License."


def render(original_filename: str = "IconReplacer.exe", description: str | None = None) -> str:
    quad = ", ".join(str(n) for n in v.VERSION)
    text = v.FULL_VERSION
    desc = description or v.PRODUCT_NAME
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({quad}),
    prodvers=({quad}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', '{COMPANY}'),
          StringStruct('FileDescription', '{desc}'),
          StringStruct('FileVersion', '{text}'),
          StringStruct('InternalName', '{v.PRODUCT_NAME}'),
          StringStruct('LegalCopyright', '{COPYRIGHT}'),
          StringStruct('OriginalFilename', '{original_filename}'),
          StringStruct('ProductName', '{v.PRODUCT_NAME}'),
          StringStruct('ProductVersion', '{text}')
        ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def write(path: Path, original_filename: str = "IconReplacer.exe", description: str | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(original_filename, description), encoding="utf-8")
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "version_info.txt"
    print(write(out))
