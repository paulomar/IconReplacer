"""Per-folder failure details for folder actions."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from iconreplacer.core.models import ActionResult

# Fixed English reasons produced by the folder icon service (registered for lupdate).
_REASONS = (
    QT_TRANSLATE_NOOP("Reasons", "No target folder."),
    QT_TRANSLATE_NOOP("Reasons", "Nothing to undo."),
    QT_TRANSLATE_NOOP("Reasons", "The folder does not exist."),
    QT_TRANSLATE_NOOP("Reasons", "The path is not a folder."),
    QT_TRANSLATE_NOOP("Reasons", "The folder cannot be accessed."),
    QT_TRANSLATE_NOOP("Reasons", "The folder cannot be written."),
    QT_TRANSLATE_NOOP("Reasons", "Drive and share roots are not supported."),
    QT_TRANSLATE_NOOP("Reasons", "System and program folders are protected."),
    QT_TRANSLATE_NOOP("Reasons", "The user profile folder itself is protected."),
    QT_TRANSLATE_NOOP("Reasons", "Symbolic links and junctions are not supported."),
    QT_TRANSLATE_NOOP("Reasons", "The path goes through a symbolic link or junction."),
)
_PREPARE_PREFIX = "The icon could not be prepared: "
QT_TRANSLATE_NOOP("Reasons", "The icon could not be prepared: %1")
_FAILED_MARK = "Failed: "


def translate_reason(text: str) -> str:
    """Translate a known fixed reason; unknown text (OS errors, details) is kept verbatim."""
    text = text.strip()
    if text in _REASONS:
        return QCoreApplication.translate("Reasons", text)
    if text.startswith(_PREPARE_PREFIX):
        detail = text[len(_PREPARE_PREFIX) :]
        return QCoreApplication.translate("Reasons", "The icon could not be prepared: %1").replace(
            "%1", detail
        )
    return text


def _key(path: Path | str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(os.fspath(path))))


def _resolved_key(path: Path) -> str:
    try:
        return _key(Path(path).resolve(strict=False))
    except OSError:
        return _key(path)


def _label(folder: Path) -> str:
    return Path(folder).name or str(folder)


def failed_folders(folders: Sequence[Path], result: ActionResult) -> list[tuple[Path, str]]:
    """(folder, English reason) for every target not listed in ``result.affected``.

    Reasons are taken from the service message ``"… Failed: <name>: <reason>; …"``; when the
    message does not have that shape every failed folder gets the whole message.
    """
    done = {_key(p) for p in result.affected}
    failed = [f for f in folders if _key(f) not in done and _resolved_key(f) not in done]
    if not failed:
        return []
    message = result.message
    at = message.find(_FAILED_MARK)
    if at < 0:
        return [(f, message) for f in failed]
    rest = message[at + len(_FAILED_MARK) :]
    out: list[tuple[Path, str]] = []
    for i, folder in enumerate(failed):
        prefix = f"{_label(folder)}: "
        if not rest.startswith(prefix):
            return [(f, message) for f in failed]
        rest = rest[len(prefix) :]
        if i + 1 < len(failed):
            nxt = rest.find(f"; {_label(failed[i + 1])}: ")
            if nxt < 0:
                return [(f, message) for f in failed]
            out.append((folder, rest[:nxt]))
            rest = rest[nxt + 2 :]
        else:
            out.append((folder, rest))
    return out


class FailureDetailsDialog(QDialog):
    def __init__(self, failures: Sequence[tuple[Path, str]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Some folders were not changed"))
        self.setMinimumSize(560, 260)
        lay = QVBoxLayout(self)
        intro = QLabel(self.tr("These folders could not be changed:"))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.table = QTreeWidget()
        self.table.setRootIsDecorated(False)
        self.table.setHeaderLabels([self.tr("Folder"), self.tr("Reason")])
        for folder, reason in failures:
            item = QTreeWidgetItem([str(folder), translate_reason(reason)])
            item.setToolTip(0, str(folder))
            item.setToolTip(1, translate_reason(reason))
            self.table.addTopLevelItem(item)
        hdr = self.table.header()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(0, 280)
        lay.addWidget(self.table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def rows(self) -> list[tuple[str, str]]:
        return [
            (self.table.topLevelItem(i).text(0), self.table.topLevelItem(i).text(1))
            for i in range(self.table.topLevelItemCount())
        ]
