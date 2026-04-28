"""Process connections table widget."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QHeaderView,
    QLabel,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.connections import Connection
from ..core.theme import get_palette, table_style


class ProcessTable(QWidget):
    """Table showing per-process connection counts."""

    # Signals
    block_requested = pyqtSignal(int, str)   # pid (0 if unknown), process_name
    unblock_requested = pyqtSignal(int, str)
    view_connections_requested = pyqtSignal(str)  # process_name

    def __init__(self):
        super().__init__()
        self._data: dict[str, list[Connection]] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        p = get_palette()

        # Title
        title = QLabel("Process Connections")
        title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        layout.addWidget(title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Process", "Internet", "LAN", "Services"])
        self.table.setStyleSheet(table_style())

        # Configure header
        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)

        # Context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

    def _show_context_menu(self, position) -> None:
        """Show context menu for selected row."""
        row = self.table.rowAt(position.y())
        if row < 0:
            return

        name_item = self.table.item(row, 0)
        if not name_item:
            return

        process_name = name_item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)

        copy_action = menu.addAction("Copy Process Name")
        if copy_action:
            copy_action.triggered.connect(
                lambda: self._copy_to_clipboard(process_name)
            )

        view_action = menu.addAction("View in Connections Tab")
        if view_action:
            view_action.triggered.connect(
                lambda: self.view_connections_requested.emit(process_name)
            )

        viewport = self.table.viewport()
        if viewport:
            menu.exec(viewport.mapToGlobal(position))

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard."""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def update_data(self, process_connections: dict[str, list[Connection]]) -> None:
        """Update table with new connection data."""
        self._data = process_connections

        # Save sort state
        header = self.table.horizontalHeader()
        sort_col = header.sortIndicatorSection() if header else -1
        sort_order = header.sortIndicatorOrder() if header else Qt.SortOrder.AscendingOrder

        self.table.setSortingEnabled(False)

        # Sort by internet connection count descending
        sorted_procs = sorted(
            process_connections.items(),
            key=lambda kv: sum(1 for c in kv[1] if not c.is_private),
            reverse=True
        )

        self.table.setRowCount(len(sorted_procs))

        for row, (name, conns) in enumerate(sorted_procs):
            inet_count = sum(1 for c in conns if not c.is_private)
            lan_count = sum(1 for c in conns if c.is_private)

            # Get unique services
            services = set()
            for c in conns:
                if c.service:
                    services.add(c.service)

            # Process name
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, name)  # For sorting

            # Internet count
            inet_item = QTableWidgetItem(str(inet_count) if inet_count else "-")
            inet_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            inet_item.setData(Qt.ItemDataRole.UserRole, inet_count)
            if inet_count > 0:
                inet_item.setForeground(Qt.GlobalColor.darkBlue)

            # LAN count
            lan_item = QTableWidgetItem(str(lan_count) if lan_count else "-")
            lan_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            lan_item.setData(Qt.ItemDataRole.UserRole, lan_count)

            # Services
            services_item = QTableWidgetItem(", ".join(sorted(services)[:3]))
            if len(services) > 3:
                services_item.setText(services_item.text() + f" +{len(services) - 3}")

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, inet_item)
            self.table.setItem(row, 2, lan_item)
            self.table.setItem(row, 3, services_item)

        # Restore sort state
        self.table.setSortingEnabled(True)
        if sort_col >= 0:
            self.table.sortByColumn(sort_col, sort_order)

    def refresh_theme(self) -> None:
        """Refresh colors for theme change."""
        p = get_palette()
        self.table.setStyleSheet(table_style())
        self.findChild(QLabel).setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {p.text_primary};"
        )
