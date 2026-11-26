"""Spike: what SHGetSetFolderCustomSettings writes (tmp_path folders only)."""

from __future__ import annotations

import os
import shutil

import pytest

from iconreplacer.services import win32_shell as w


@pytest.fixture
def work(tmp_path):
    yield tmp_path
    for root, dirs, files in os.walk(tmp_path):
        for name in dirs + files:
            w.set_attributes(os.path.join(root, name), w.FILE_ATTRIBUTE_NORMAL)
    shutil.rmtree(tmp_path, ignore_errors=True)


def _ini(folder):
    return (folder / "desktop.ini").read_bytes()


def test_relative_icon_path_is_written_verbatim(work):
    folder = work / "rel"
    folder.mkdir()
    w.set_folder_icon(folder, ".iconreplacer\\icon.ico", 0)
    assert _ini(folder) == b"[.ShellClassInfo]\r\nIconResource=.iconreplacer\\icon.ico,0\r\n"


def test_env_var_location_is_not_expanded(work):
    folder = work / "res"
    folder.mkdir()
    w.set_folder_icon(folder, "%SystemRoot%\\System32\\shell32.dll", -4)
    assert b"IconResource=%SystemRoot%\\System32\\shell32.dll,-4" in _ini(folder)


def test_api_sets_explorer_attributes(work):
    folder = work / "attrs"
    folder.mkdir()
    w.set_folder_icon(folder, ".iconreplacer\\icon.ico", 0)
    ini_attrs = w.get_attributes(folder / "desktop.ini")
    assert ini_attrs & w.FILE_ATTRIBUTE_HIDDEN
    assert ini_attrs & w.FILE_ATTRIBUTE_SYSTEM
    assert w.get_attributes(folder) & w.FILE_ATTRIBUTE_READONLY


def test_errors_raise_oserror(work):
    with pytest.raises(OSError):
        w.get_attributes(work / "missing")
    with pytest.raises(OSError):
        w.set_attributes(work / "missing", 0)


def test_notify_does_not_fail(work):
    w.notify_updated(work)
