"""Safety rules for target folders (only tmp_path folders are touched)."""

from __future__ import annotations

import _winapi
import os
import subprocess
from pathlib import Path

import pytest

from iconreplacer.services.folder_safety import UnsafeFolderError, check_folder


@pytest.fixture
def fake_env(tmp_path, monkeypatch):
    """Point every protected environment variable at folders inside tmp_path."""
    roots = {}
    for var, name in [
        ("SystemRoot", "Windows"),
        ("windir", "Windows"),
        ("ProgramFiles", "Program Files"),
        ("ProgramFiles(x86)", "Program Files (x86)"),
        ("ProgramW6432", "Program Files"),
        ("ProgramData", "ProgramData"),
        ("USERPROFILE", "Users-me"),
    ]:
        path = tmp_path / name
        path.mkdir(exist_ok=True)
        monkeypatch.setenv(var, str(path))
        roots[var] = path
    return roots


def _refused(path, match):
    with pytest.raises(UnsafeFolderError, match=match):
        check_folder(path)


def test_plain_folder_is_allowed_and_resolved(tmp_path, fake_env):
    folder = tmp_path / "plain"
    folder.mkdir()
    assert check_folder(tmp_path / "plain" / ".." / "plain") == folder.resolve()
    assert [p.name for p in folder.iterdir()] == []  # write probe cleaned up


def test_missing_folder(tmp_path, fake_env):
    _refused(tmp_path / "nope", "does not exist")


def test_file_is_not_a_folder(tmp_path, fake_env):
    file = tmp_path / "f.txt"
    file.write_text("x")
    _refused(file, "not a folder")


def test_drive_root():
    _refused(Path(os.environ.get("SYSTEMDRIVE", "C:") + "\\"), "root")


@pytest.mark.parametrize("var", ["SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"])
def test_protected_trees_and_subfolders(fake_env, var):
    root = fake_env[var]
    sub = root / "Sub"
    sub.mkdir()
    _refused(root, "protected")
    _refused(sub, "protected")


def test_dot_dot_into_system_folder(fake_env):
    win = fake_env["SystemRoot"]
    (win / "Temp").mkdir()
    _refused(Path(f"{win}\\..\\{win.name}\\Temp"), "protected")


def test_profile_root_refused_but_subfolder_allowed(fake_env):
    profile = fake_env["USERPROFILE"]
    docs = profile / "Documents"
    docs.mkdir()
    _refused(profile, "profile")
    assert check_folder(docs) == docs.resolve()


def test_junction_refused(tmp_path, fake_env):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    _winapi.CreateJunction(str(target), str(link))
    try:
        _refused(link, "junction")
        inner = target / "inner"
        inner.mkdir()
        _refused(link / "inner", "junction")
    finally:
        os.rmdir(link)


def test_unicode_folder_allowed(tmp_path, fake_env):
    folder = tmp_path / "Fotos ñandú 写真 🎉"
    folder.mkdir()
    assert check_folder(folder) == folder.resolve()


def test_unwritable_folder_refused(tmp_path, fake_env):
    folder = tmp_path / "locked"
    folder.mkdir()
    deny = ["icacls", str(folder), "/deny", "*S-1-1-0:(WD,AD)"]
    subprocess.run(deny, check=True, capture_output=True)
    try:
        _refused(folder, "cannot be written")
    finally:
        subprocess.run(
            ["icacls", str(folder), "/remove:d", "*S-1-1-0"], check=True, capture_output=True
        )
    assert check_folder(folder) == folder.resolve()
