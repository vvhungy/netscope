"""Listening ports table widget."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt

from ..core.connections import ListeningPort
from ..core.theme import get_color, get_palette, table_style


class ListeningPortsWidget(QWidget):
    """Table showing listening TCP/UDP ports."""

    def __init__(self):
        super().__init__()
        self._data: list[ListeningPort] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        p = get_palette()

        # Title
        self._title = QLabel("Listening Ports")
        self._title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        layout.addWidget(self._title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Port", "Protocol", "Address", "Process", "PID"])
        self.table.setStyleSheet(table_style())

        # Configure header
        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)

        layout.addWidget(self.table)

    def update_data(self, listening_ports: list[ListeningPort]) -> None:
        """Update table with new listening port data."""
        self._data = listening_ports
        p = get_palette()

        # Sort by port by default
        sorted_ports = sorted(listening_ports, key=lambda p: (p.port, p.protocol))

        self.table.setRowCount(len(sorted_ports))

        for row, port_info in enumerate(sorted_ports):
            # Port - highlight well-known ports
            port_item = QTableWidgetItem(str(port_info.port))
            port_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            port_item.setData(Qt.ItemDataRole.UserRole, port_info.port)
            if port_info.port < 1024:
                port_item.setForeground(Qt.GlobalColor.yellow)

            # Protocol
            proto_item = QTableWidgetItem(port_info.protocol.upper())
            proto_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # Store for sorting (TCP before UDP)
            proto_item.setData(Qt.ItemDataRole.UserRole, 0 if port_info.protocol == "tcp" else 1)

            # Address - show simplified display
            addr_display = port_info.address
            if addr_display == "0.0.0.0":
                addr_display = "0.0.0.0 (all)"
            elif addr_display == "::":
                addr_display = ":: (all)"
            elif addr_display == ":::":
                addr_display = ":: (all)"
            addr_item = QTableWidgetItem(addr_display)
            addr_item.setData(Qt.ItemDataRole.UserRole, port_info.address)

            # Process name
            proc_item = QTableWidgetItem(port_info.process_name)
            proc_item.setData(Qt.ItemDataRole.UserRole, port_info.process_name)

            # PID
            pid_text = str(port_info.pid) if port_info.pid is not None else "-"
            pid_item = QTableWidgetItem(pid_text)
            pid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pid_item.setData(Qt.ItemDataRole.UserRole, port_info.pid if port_info.pid else -1)

            self.table.setItem(row, 0, port_item)
            self.table.setItem(row, 1, proto_item)
            self.table.setItem(row, 2, addr_item)
            self.table.setItem(row, 3, proc_item)
            self.table.setItem(row, 4, pid_item)

    def refresh_theme(self) -> None:
        """Refresh colors for theme change."""
        p = get_palette()
        self._title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        self.table.setStyleSheet(table_style())
