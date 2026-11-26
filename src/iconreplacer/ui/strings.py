"""Translatable labels for data-driven names (registered for lupdate)."""

from __future__ import annotations

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication

from iconreplacer.core.models import Section

_CATEGORY_LABELS = (
    QT_TRANSLATE_NOOP("Categories", "Folders"),
    QT_TRANSLATE_NOOP("Categories", "Drives & Storage"),
    QT_TRANSLATE_NOOP("Categories", "Devices"),
    QT_TRANSLATE_NOOP("Categories", "Media"),
    QT_TRANSLATE_NOOP("Categories", "Network"),
    QT_TRANSLATE_NOOP("Categories", "Security"),
    QT_TRANSLATE_NOOP("Categories", "System"),
    QT_TRANSLATE_NOOP("Categories", "Users"),
    QT_TRANSLATE_NOOP("Categories", "Accessibility"),
    QT_TRANSLATE_NOOP("Categories", "Power"),
    QT_TRANSLATE_NOOP("Categories", "Web"),
    QT_TRANSLATE_NOOP("Categories", "Documents"),
    QT_TRANSLATE_NOOP("Categories", "Legacy"),
)

_SECTION_LABELS = {
    Section.SYSTEM: QT_TRANSLATE_NOOP("Sections", "System libraries"),
    Section.ONLINE: QT_TRANSLATE_NOOP("Sections", "Online sources"),
    Section.LOCAL: QT_TRANSLATE_NOOP("Sections", "Local folders"),
}


def category_label(name: str) -> str:
    return QCoreApplication.translate("Categories", name)


def section_label(section: Section) -> str:
    return QCoreApplication.translate("Sections", _SECTION_LABELS[section])
