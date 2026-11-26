"""Source navigation sidebar and category chips."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QButtonGroup,
    QStyle,
    QStyledItemDelegate,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from iconreplacer.catalog.registry import SourceRegistry
from iconreplacer.core.contracts import DynamicIconSource, IconSource
from iconreplacer.core.models import CATEGORIES, Section, SourceState
from iconreplacer.ui.flow_layout import FlowLayout, flow_size_policy
from iconreplacer.ui.strings import category_label, section_label

SOURCE_ROLE = Qt.ItemDataRole.UserRole + 10
DESC_ROLE = Qt.ItemDataRole.UserRole + 11
COUNT_ROLE = Qt.ItemDataRole.UserRole + 12
BADGE_ROLE = Qt.ItemDataRole.UserRole + 13  # (state value, text) while not ready
ERROR_COLOR = "#F46A6A"
ALL_ID = "__all__"


class _SourceDelegate(QStyledItemDelegate):
    """Two-line item: name + count, then a muted description."""

    def sizeHint(self, option, index) -> QSize:
        if index.data(DESC_ROLE):
            return QSize(200, 40)
        return QSize(200, 26)

    def paint(self, painter, option, index) -> None:
        desc = index.data(DESC_ROLE)
        if not desc and index.data(SOURCE_ROLE) is None:  # section header
            super().paint(painter, option, index)
            return
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else None
        option_text = option.text
        option.text = ""
        if style:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter, option.widget)
        option.text = option_text
        painter.save()
        pal = option.palette
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        group = QPalette.ColorGroup.Normal if enabled else QPalette.ColorGroup.Disabled
        r: QRect = option.rect.adjusted(6, 3, -8, -3)
        count = index.data(COUNT_ROLE)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        main_color = pal.color(
            group, QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        )
        muted = QColor(main_color)
        muted.setAlpha(170 if selected else 120)
        f = QFont(option.font)
        painter.setFont(f)
        painter.setPen(main_color)
        top = QRect(r.x(), r.y(), r.width(), 18)
        painter.drawText(
            top, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, option_text
        )
        badge = index.data(BADGE_ROLE)
        if badge:
            state, text = badge
            painter.setPen(QColor(ERROR_COLOR) if state == SourceState.ERROR.value else muted)
            painter.drawText(top, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)
        elif count is not None:
            painter.setPen(muted)
            painter.drawText(
                top, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{count:,}"
            )
        if desc:
            f2 = QFont(option.font)
            f2.setPointSizeF(max(7.0, f.pointSizeF() - 1.5))
            painter.setFont(f2)
            painter.setPen(muted)
            bottom = QRect(r.x(), r.y() + 18, r.width(), 16)
            painter.drawText(
                bottom,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                painter.fontMetrics().elidedText(desc, Qt.TextElideMode.ElideRight, bottom.width()),
            )
        painter.restore()


class SourceSidebar(QTreeWidget):
    source_selected = Signal(object)  # source_id | None (All)

    def __init__(self, registry: SourceRegistry, parent=None) -> None:
        super().__init__(parent)
        self._registry = registry
        self._items: dict[str, QTreeWidgetItem] = {}
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(10)
        self.setItemDelegate(_SourceDelegate(self))
        self.setMinimumWidth(190)
        self.currentItemChanged.connect(self._on_current)
        self.rebuild()

    def rebuild(self) -> None:
        self.blockSignals(True)
        self.clear()
        self._items.clear()
        total = len(self._registry.all_entries())
        all_item = QTreeWidgetItem([self.tr("All sources")])
        all_item.setData(0, SOURCE_ROLE, ALL_ID)
        all_item.setData(0, COUNT_ROLE, total)
        self.addTopLevelItem(all_item)
        self._items[ALL_ID] = all_item
        for section in (Section.SYSTEM, Section.ONLINE, Section.LOCAL):
            header = QTreeWidgetItem([section_label(section).upper()])
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            f = header.font(0)
            f.setBold(True)
            f.setPointSizeF(max(7.0, f.pointSizeF() - 1))
            header.setFont(0, f)
            self.addTopLevelItem(header)
            for src in self._registry.sources(section):
                info = src.info
                item = QTreeWidgetItem(header, [info.name])
                item.setData(0, SOURCE_ROLE, info.id)
                item.setData(0, DESC_ROLE, info.description)
                self._items[info.id] = item
                self._update_item(item, src)
            header.setExpanded(True)
        self.setCurrentItem(all_item)
        self.blockSignals(False)

    def _state_text(self, state: SourceState) -> str:
        return {
            SourceState.LOADING: self.tr("Loading…"),
            SourceState.OFFLINE: self.tr("Offline"),
            SourceState.ERROR: self.tr("Error"),
        }.get(state, "")

    def _update_item(self, item: QTreeWidgetItem, src: IconSource) -> None:
        info = src.info
        item.setData(0, COUNT_ROLE, len(src.entries()))
        tip = "\n".join((info.name, info.description, info.license))
        badge = None
        if isinstance(src, DynamicIconSource):
            state = src.state()
            if state is not SourceState.READY:
                badge = (state.value, self._state_text(state))
            if state is SourceState.ERROR:
                tip += "\n" + self.tr("Error: %1").replace("%1", src.last_error() or "?")
        item.setData(0, BADGE_ROLE, badge)
        item.setToolTip(0, tip)

    def refresh_sources(self, source_ids=None) -> None:
        """Update counts, state badges and tooltips (all sources, or only ``source_ids``)."""
        for sid, item in self._items.items():
            if sid == ALL_ID:
                continue
            if source_ids is None or sid in source_ids:
                self._update_item(item, self._registry.get(sid))
        self._items[ALL_ID].setData(0, COUNT_ROLE, len(self._registry.all_entries()))
        self.viewport().update()

    def badge(self, source_id: str) -> str:
        data = self._items[source_id].data(0, BADGE_ROLE)
        return data[1] if data else ""

    def set_available(self, available: set[str]) -> None:
        for sid, item in self._items.items():
            if sid == ALL_ID:
                continue
            item.setDisabled(sid not in available)

    def count_shown(self, source_id: str) -> int:
        return int(self._items[source_id].data(0, COUNT_ROLE))

    def select_source(self, source_id: str | None) -> None:
        self.setCurrentItem(self._items[source_id or ALL_ID])

    def _on_current(self, current: QTreeWidgetItem | None, _prev) -> None:
        if current is None:
            return
        sid = current.data(0, SOURCE_ROLE)
        if sid is None:
            return
        self.source_selected.emit(None if sid == ALL_ID else sid)


class CategoryChips(QWidget):
    """Exclusive category chips that wrap onto extra lines in narrow windows."""

    category_selected = Signal(object)  # category | None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(flow_size_policy())
        lay = FlowLayout(self, spacing=6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str | None, QToolButton] = {}
        for cat in (None, *CATEGORIES):
            b = QToolButton()
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setText(self.tr("All") if cat is None else category_label(cat).replace("&", "&&"))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=cat: self.category_selected.emit(c))
            self.group.addButton(b)
            lay.addWidget(b)
            self.buttons[cat] = b
        self.buttons[None].setChecked(True)

    def select(self, category: str | None) -> None:
        self.buttons[category].click()
