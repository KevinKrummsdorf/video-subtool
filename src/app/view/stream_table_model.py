from __future__ import annotations
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from app import i18n
from app.i18n import t

class StreamTableModel(QAbstractTableModel):
    """TableModel nur für die Stream-Tabelle (reine View-Logik)."""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._headers = [
            t("tbl.abs"), t("tbl.rel"), t("tbl.codec"), t("tbl.lang"),
            t("tbl.title"), t("tbl.class"), t("tbl.default")
        ]
        i18n.bus.language_changed.connect(self._retranslate)

    def _retranslate(self, *_):
        self._headers = [
            t("tbl.abs"), t("tbl.rel"), t("tbl.codec"), t("tbl.lang"),
            t("tbl.title"), t("tbl.class"), t("tbl.default")
        ]
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(self._headers)-1)

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # type: ignore
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # type: ignore
        return len(self._headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # type: ignore
        if role != Qt.DisplayRole: return None
        if orientation == Qt.Horizontal: return self._headers[section]
        return str(section)

    def data(self, index, role=Qt.DisplayRole):  # type: ignore
        if not index.isValid(): return None
        if role == Qt.DisplayRole:
            return str(self.rows[index.row()][index.column()])
        return None
