"""Slow end-to-end release build. Run with: uv run pytest -m build -o addopts=''"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

pytestmark = pytest.mark.build


def test_full_release_build():
    import build_release

    assert build_release.main([]) == 0
    zip_path = ROOT / "dist" / f"{build_release.folder_name()}.zip"
    assert zip_path.is_file()
    assert zip_path.with_name(zip_path.name + ".sha256").is_file()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    top = build_release.folder_name() + "/"
    assert top + "IconReplacer.exe" in names
    assert top + "iconreplacer-cli.exe" in names
