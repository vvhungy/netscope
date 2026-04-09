"""Process connections table widget."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.connections import Connection
from ..core.theme import get_palette, table_style


class ProcessTable(QWidget):
    """Table showing per-process connection counts."""

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

        layout.addWidget(self.table)

    def update_data(self, process_connections: dict[str, list[Connection]]) -> None:
        """Update table with new connection data."""
        self._data = process_connections

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

    def refresh_theme(self) -> None:
        """Refresh colors for theme change."""
        p = get_palette()
        self.table.setStyleSheet(table_style())
        self.findChild(QLabel).setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {p.text_primary};"
        )
