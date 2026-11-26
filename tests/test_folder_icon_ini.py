"""Pure tests for the line-preserving desktop.ini editor (no file I/O)."""

from __future__ import annotations

from iconreplacer.services.folder_icon_service import ICON_KEYS, IniDocument

SAMPLE = (
    "[.ShellClassInfo]\r\n"
    "LocalizedResourceName=@%SystemRoot%\\system32\\shell32.dll,-21770\r\n"
    "IconFile=old.ico\r\n"
    "IconIndex=3\r\n"
    "\r\n"
    "[ViewState]\r\n"
    "Mode=\r\n"
    "Vid=\r\n"
    "FolderType=Pictures\r\n"
)


def test_round_trip_ascii_unchanged():
    data = SAMPLE.encode("ascii")
    assert IniDocument.parse(data).to_bytes() == data


def test_round_trip_utf16_and_utf8_bom():
    utf16 = b"\xff\xfe" + SAMPLE.replace("Pictures", "Fotos ñ").encode("utf-16-le")
    assert IniDocument.parse(utf16).to_bytes() == utf16
    utf8 = b"\xef\xbb\xbf" + SAMPLE.encode("utf-8")
    assert IniDocument.parse(utf8).to_bytes() == utf8


def test_set_replaces_value_and_keeps_other_sections():
    doc = IniDocument.parse(SAMPLE.encode("ascii"))
    doc.set(".shellclassinfo", "IconResource", "a.dll,-1")
    doc.set(".ShellClassInfo", "IconResource", "b.dll,-2")
    text = doc.text
    assert text.count("IconResource=") == 1
    assert "IconResource=b.dll,-2\r\n" in text
    assert "LocalizedResourceName=@%SystemRoot%" in text
    assert text.endswith("[ViewState]\r\nMode=\r\nVid=\r\nFolderType=Pictures\r\n")
    assert doc.get(".ShellClassInfo", "iconresource") == "b.dll,-2"


def test_set_creates_section_in_empty_document():
    doc = IniDocument.parse(None)
    doc.set(".ShellClassInfo", "IconResource", ".iconreplacer\\icon.ico,0")
    assert doc.to_bytes() == b"[.ShellClassInfo]\r\nIconResource=.iconreplacer\\icon.ico,0\r\n"


def test_set_appends_section_to_file_without_trailing_newline():
    doc = IniDocument.parse(b"[ViewState]\nMode=")
    doc.set(".ShellClassInfo", "IconResource", "x,0")
    assert doc.text == "[ViewState]\nMode=\n[.ShellClassInfo]\nIconResource=x,0\n"


def test_non_ascii_value_upgrades_ansi_to_utf16():
    doc = IniDocument.parse(SAMPLE.encode("ascii"))
    doc.set(".ShellClassInfo", "IconResource", "D:\\Iconos ñ\\a.dll,-5")
    data = doc.to_bytes()
    assert data.startswith(b"\xff\xfe")
    assert "Iconos ñ" in data[2:].decode("utf-16-le")


def test_remove_icon_keys_keeps_other_keys():
    doc = IniDocument.parse(SAMPLE.encode("ascii"))
    assert doc.remove(".ShellClassInfo", ICON_KEYS)
    assert "IconFile" not in doc.text and "IconIndex" not in doc.text
    assert "LocalizedResourceName" in doc.text
    assert doc.has_keys()


def test_remove_last_key_drops_section():
    doc = IniDocument.parse(b"[.ShellClassInfo]\r\nIconResource=x,0\r\n")
    assert doc.remove(".ShellClassInfo", ICON_KEYS)
    assert doc.text == ""
    assert not doc.has_keys()
    assert not doc.remove(".ShellClassInfo", ICON_KEYS)


def test_comments_are_not_keys():
    doc = IniDocument.parse(b"; comment=1\r\n[.ShellClassInfo]\r\n# x=y\r\n")
    assert not doc.has_keys()
