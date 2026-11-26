"""Virtualized icon grid: list model + filter proxy + delegate with pixmap cache."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Sequence

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QImage, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QListView,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from iconreplacer.core.models import IconEntry

ENTRY_ROLE = Qt.ItemDataRole.UserRole + 1
Renderer = Callable[[IconEntry, int], QImage]
MIN_THUMB, MAX_THUMB, DEFAULT_THUMB = 16, 256, 48
CAPTION_H = 18


class IconListModel(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[IconEntry] = []

    def set_entries(self, entries: Sequence[IconEntry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._entries)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        e = self._entries[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return e.name
        if role == Qt.ItemDataRole.ToolTipRole:
            rid = f",{e.ref.resource_id}" if e.ref.resource_id is not None else ""
            return f"{e.name}\n{e.ref.location}{rid}"
        if role == ENTRY_ROLE:
            return e
        return None


class IconFilterProxy(QSortFilterProxyModel):
    """Combines source, category, search text and availability filters."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source_id: str | None = None
        self._category: str | None = None
        self._search = ""
        self._available: frozenset[str] | None = None
        self._search_exempt: frozenset[str] = frozenset()

    def _change(self, attr: str, value) -> None:
        if getattr(self, attr) == value:
            return
        self.beginFilterChange()
        setattr(self, attr, value)
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_source(self, source_id: str | None) -> None:
        self._change("_source_id", source_id)

    def set_category(self, category: str | None) -> None:
        self._change("_category", category)

    def set_search(self, text: str) -> None:
        self._change("_search", text.casefold().strip())

    def set_available_sources(self, ids: frozenset[str] | None) -> None:
        self._change("_available", ids)

    def set_search_exempt(self, ids: frozenset[str]) -> None:
        """Sources whose entries are already the result of a remote query for the search text."""
        self._change("_search_exempt", frozenset(ids))

    def filterAcceptsRow(self, row: int, parent) -> bool:
        e: IconEntry = self.sourceModel().index(row, 0, parent).data(ENTRY_ROLE)
        if self._available is not None and e.source_id not in self._available:
            return False
        if self._source_id is not None and e.source_id != self._source_id:
            return False
        if self._category is not None and self._category not in e.categories:
            return False
        if e.source_id in self._search_exempt:
            return True
        return not self._search or e.matches(self._search)


class IconDelegate(QStyledItemDelegate):
    CACHE_LIMIT = 4000

    def __init__(self, renderer: Renderer, parent=None) -> None:
        super().__init__(parent)
        self._renderer = renderer
        self._size = DEFAULT_THUMB
        self._cache: OrderedDict[tuple[str, str, int], QPixmap] = OrderedDict()

    @property
    def thumb_size(self) -> int:
        return self._size

    def set_thumb_size(self, size: int) -> None:
        self._size = max(MIN_THUMB, min(MAX_THUMB, int(size)))

    def cell_size(self) -> QSize:
        w = max(self._size, 64) + 16
        return QSize(w, self._size + CAPTION_H + 14)

    def pixmap(self, entry: IconEntry, size: int) -> QPixmap:
        key = (entry.source_id, entry.id, size)
        pm = self._cache.get(key)
        if pm is None:
            pm = QPixmap.fromImage(self._renderer(entry, size))
            self._cache[key] = pm
            if len(self._cache) > self.CACHE_LIMIT:
                self._cache.popitem(last=False)
        else:
            self._cache.move_to_end(key)
        return pm

    def clear_cache(self, source_ids: set[str] | None = None) -> None:
        """Drop cached thumbnails (all, or only those of ``source_ids``)."""
        if source_ids is None:
            self._cache.clear()
            return
        for key in [k for k in self._cache if k[0] in source_ids]:
            del self._cache[key]

    def sizeHint(self, option, index) -> QSize:
        return self.cell_size()

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        entry: IconEntry = index.data(ENTRY_ROLE)
        r: QRect = option.rect
        painter.save()
        pal = option.palette
        if option.state & QStyle.StateFlag.State_Selected:
            c = pal.color(QPalette.ColorRole.Highlight)
            c.setAlpha(70)
            painter.setPen(pal.color(QPalette.ColorRole.Highlight))
            painter.setBrush(c)
            painter.drawRoundedRect(r.adjusted(2, 2, -2, -2), 6, 6)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal.color(QPalette.ColorRole.AlternateBase))
            painter.drawRoundedRect(r.adjusted(2, 2, -2, -2), 6, 6)
        s = self._size
        x = r.x() + (r.width() - s) // 2
        painter.drawPixmap(QRect(x, r.y() + 7, s, s), self.pixmap(entry, s))
        painter.setPen(pal.color(QPalette.ColorRole.Text))
        font = painter.font()
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1.5))
        painter.setFont(font)
        text_rect = QRect(r.x() + 4, r.y() + 9 + s, r.width() - 8, CAPTION_H)
        elided = painter.fontMetrics().elidedText(
            entry.name, Qt.TextElideMode.ElideRight, text_rect.width()
        )
        painter.drawText(
            text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, elided
        )
        painter.restore()


class IconGrid(QWidget):
    """Grid view with an explicit empty state."""

    entry_selected = Signal(object)  # IconEntry | None

    def __init__(self, renderer: Renderer, parent=None) -> None:
        super().__init__(parent)
        self.model = IconListModel(self)
        self.proxy = IconFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.delegate = IconDelegate(renderer, self)

        self.view = QListView()
        self.view.setViewMode(QListView.ViewMode.IconMode)
        self.view.setResizeMode(QListView.ResizeMode.Adjust)
        self.view.setMovement(QListView.Movement.Static)
        self.view.setUniformItemSizes(True)
        self.view.setLayoutMode(QListView.LayoutMode.Batched)
        self.view.setBatchSize(400)
        self.view.setWrapping(True)
        self.view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setMouseTracking(True)
        self.view.setModel(self.proxy)
        self.view.setItemDelegate(self.delegate)
        self.view.selectionModel().currentChanged.connect(self._on_current)

        self.empty = QLabel(self.tr("No icons match"))
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setObjectName("muted")

        self.stack = QStackedWidget()
        self.stack.addWidget(self.view)
        self.stack.addWidget(self.empty)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)

        self.proxy.modelReset.connect(self._update_empty)
        self.proxy.rowsInserted.connect(self._update_empty)
        self.proxy.rowsRemoved.connect(self._update_empty)
        self.proxy.layoutChanged.connect(self._update_empty)
        self.set_thumb_size(DEFAULT_THUMB)

    def set_entries(self, entries: Sequence[IconEntry]) -> None:
        self.model.set_entries(entries)
        self._update_empty()

    def current_entry(self) -> IconEntry | None:
        idx = self.view.currentIndex()
        return idx.data(ENTRY_ROLE) if idx.isValid() else None

    def select_entry_id(self, entry_id: str) -> bool:
        for row in range(self.proxy.rowCount()):
            idx = self.proxy.index(row, 0)
            if idx.data(ENTRY_ROLE).id == entry_id:
                self.view.setCurrentIndex(idx)
                return True
        return False

    def set_thumb_size(self, size: int) -> None:
        self.delegate.set_thumb_size(size)
        self.view.setGridSize(self.delegate.cell_size())
        self.view.setIconSize(QSize(self.delegate.thumb_size, self.delegate.thumb_size))
        self.view.doItemsLayout()

    def visible_count(self) -> int:
        return self.proxy.rowCount()

    def columns(self) -> int:
        cell = self.delegate.cell_size().width()
        return max(1, self.view.viewport().width() // cell)

    def is_empty_state(self) -> bool:
        return self.stack.currentWidget() is self.empty

    def select_row(self, row: int) -> None:
        idx = self.proxy.index(row, 0)
        self.view.setCurrentIndex(idx)

    def _update_empty(self, *_args) -> None:
        self.stack.setCurrentWidget(self.empty if self.proxy.rowCount() == 0 else self.view)
        if self.proxy.rowCount() == 0:
            self.entry_selected.emit(None)

    def _on_current(self, current, _previous) -> None:
        self.entry_selected.emit(current.data(ENTRY_ROLE) if current.isValid() else None)
