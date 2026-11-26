"""Fast packaging tests (no PyInstaller run)."""

from __future__ import annotations

import hashlib
import struct
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for sub in ("packaging", "tools"):
    if str(ROOT / sub) not in sys.path:
        sys.path.insert(0, str(ROOT / sub))

import entry_cli  # noqa: E402
import make_app_icon  # noqa: E402
import make_version_info  # noqa: E402
import payload  # noqa: E402

import build_release  # noqa: E402
from iconreplacer import version as v  # noqa: E402
from iconreplacer.core import paths  # noqa: E402
from iconreplacer.shell import registration  # noqa: E402


def test_version_info_content():
    text = make_version_info.render("IconReplacer.exe")
    quad = ", ".join(str(n) for n in v.VERSION)
    assert f"filevers=({quad})" in text and f"prodvers=({quad})" in text
    assert f"StringStruct('FileVersion', '{v.FULL_VERSION}')" in text
    assert f"StringStruct('ProductVersion', '{v.FULL_VERSION}')" in text
    assert "StringStruct('CompanyName', 'IconReplacer contributors')" in text
    assert "StringStruct('ProductName', 'IconReplacer')" in text
    assert "StringStruct('OriginalFilename', 'IconReplacer.exe')" in text
    assert "MIT" in text
    compile(text, "version_info", "exec")  # valid Python


def test_package_data_is_generic_and_complete(tmp_path):
    pkg = tmp_path / "pkg"
    (pkg / "catalog" / "data").mkdir(parents=True)
    (pkg / "i18n").mkdir()
    (pkg / "__pycache__").mkdir()
    for rel in ("a.py", "catalog/data/x.json", "i18n/x_en.qm", "__pycache__/a.pyc", "m.pyc"):
        (pkg / rel).write_bytes(b"x")
    pairs = {(Path(s).name, d) for s, d in payload.collect_package_data(pkg)}
    assert pairs == {
        ("x.json", "iconreplacer/catalog/data"),
        ("x_en.qm", "iconreplacer/i18n"),
    }


def test_real_package_data_contains_json_and_ts_or_qm():
    pairs = payload.collect_package_data(ROOT / "src" / "iconreplacer")
    names = {Path(s).suffix for s, _ in pairs}
    assert ".json" in names
    assert not any(s.endswith(".py") for s, _ in pairs)


@pytest.mark.parametrize(
    ("name", "keep"),
    [
        ("PySide6/Qt/plugins/platforms/qwindows.dll", True),
        ("PySide6/Qt/plugins/platforms/qminimal.dll", False),
        ("PySide6/Qt/plugins/imageformats/qsvg.dll", True),
        ("PySide6/Qt/plugins/imageformats/qgif.dll", False),
        ("PySide6/Qt/plugins/styles/qmodernwindowsstyle.dll", True),
        ("PySide6/Qt/plugins/generic/qtuiotouchplugin.dll", False),
        ("PySide6/opengl32sw.dll", False),
        ("PySide6/Qt6Svg.dll", True),
    ],
)
def test_qt_trimming_rules(name, keep):
    assert payload.keep_toc_entry(name) is keep


def test_icon_generator_writes_multisize_ico(tmp_path):
    out = make_app_icon.build(tmp_path / "app.ico")
    data = out.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 1)
    sizes = set()
    for i in range(count):
        w, h = struct.unpack_from("<BB", data, 6 + 16 * i)
        sizes.add((w or 256, h or 256))
    assert {(s, s) for s in (16, 32, 48, 64, 128, 256)} <= sizes
    image = make_app_icon.render(64)
    assert image.pixelColor(32, 32).alpha() > 0
    assert image.pixelColor(0, 0).alpha() == 0


def test_stage_and_zip_layout(tmp_path, monkeypatch):
    built = tmp_path / "IconReplacer"
    (built / "_internal").mkdir(parents=True)
    (built / "_internal" / "x.dll").write_bytes(b"d")
    (built / "IconReplacer.exe").write_bytes(b"e")
    (built / "iconreplacer-cli.exe").write_bytes(b"c")
    extras = {}
    for name in build_release.EXTRA_FILES:
        f = tmp_path / f"src-{name}"
        f.write_text(name)
        extras[name] = f
    monkeypatch.setattr(build_release, "EXTRA_FILES", extras)

    staged = build_release.stage(built, tmp_path / "stage", "1.2.3.4")
    assert staged.name == "IconReplacer-1.2.3.4-win64"
    zip_path = build_release.make_zip(staged, tmp_path / "out" / "IconReplacer-1.2.3.4-win64.zip")
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    top = "IconReplacer-1.2.3.4-win64/"
    assert {n.split("/")[0] + "/" for n in names} == {top}
    for expected in (
        "IconReplacer.exe",
        "iconreplacer-cli.exe",
        "_internal/x.dll",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "README-PORTABLE.txt",
    ):
        assert top + expected in names

    checksum = build_release.write_checksum(zip_path)
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    assert checksum.read_text(encoding="utf-8") == f"{digest} *{zip_path.name}\n"


def test_release_files_exist_and_notices_content():
    for src in build_release.EXTRA_FILES.values():
        assert src.is_file(), src
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for word in ("LGPL-3.0", "Qt", "dynamically linked", "Python", "PyInstaller", "Microsoft"):
        assert word in notices


def _fake_frozen(monkeypatch, exe: Path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))


def test_frozen_app_dir_and_data_root(tmp_path, monkeypatch):
    exe = tmp_path / "IconReplacer.exe"
    exe.write_bytes(b"")
    _fake_frozen(monkeypatch, exe)
    monkeypatch.delenv(paths.ENV_HOME, raising=False)
    paths.reset_cache()
    try:
        assert paths.app_dir() == tmp_path.resolve()
        assert paths.data_root() == tmp_path / "data"
    finally:
        paths.reset_cache()


def test_frozen_registration_command_points_to_gui_exe(tmp_path, monkeypatch):
    cli = tmp_path / "App Dir" / "iconreplacer-cli.exe"
    cli.parent.mkdir()
    cli.write_bytes(b"")
    _fake_frozen(monkeypatch, cli)
    gui_path = str(cli.resolve().with_name("IconReplacer.exe"))

    # GUI exe: launcher is the running exe.
    gui = tmp_path / "App Dir" / "IconReplacer.exe"
    gui.write_bytes(b"")
    _fake_frozen(monkeypatch, gui)
    launcher, extra = registration.default_launcher()
    assert registration.build_command(launcher, extra) == f'"{gui_path}" --folder "%1"'

    # Console companion: patched to the sibling GUI exe.
    _fake_frozen(monkeypatch, cli)
    launcher, extra = entry_cli.gui_launcher()
    assert registration.build_command(launcher, extra) == f'"{gui_path}" --folder "%1"'
