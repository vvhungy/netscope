"""Process bandwidth table widget showing per-process bandwidth usage."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.process_bandwidth import ProcessBandwidthStats
from ..core.theme import get_color, get_palette, table_style


def format_bytes(b: float) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def format_rate(bps: float) -> str:
    """Format bytes/sec as human-readable rate."""
    return format_bytes(bps) + "/s"


def get_usage_color(rate: float) -> str:
    """Get semantic color name based on bandwidth usage level."""
    if rate > 10 * 1024 * 1024:  # > 10 MB/s - very high
        return "error"
    elif rate > 1 * 1024 * 1024:  # > 1 MB/s - high
        return "warning"
    elif rate > 100 * 1024:  # > 100 KB/s - medium
        return "warning"
    elif rate > 10 * 1024:  # > 10 KB/s - low
        return "success"
    else:
        return "text_secondary"


class ProcessBandwidthTable(QWidget):
    """Table showing per-process bandwidth usage."""

    COLUMN_PROCESS = 0
    COLUMN_PID = 1
    COLUMN_RX_RATE = 2
    COLUMN_TX_RATE = 3
    COLUMN_TOTAL = 4
    COLUMN_CONNECTIONS = 5

    # Signals
    block_requested = pyqtSignal(int, str)  # pid, process_name
    unblock_requested = pyqtSignal(int, str)  # pid, process_name

    def __init__(self, max_rows: int = 20):
        super().__init__()
        self._max_rows = max_rows
        self._data: list[ProcessBandwidthStats] = []
        self._blocked_pids: set[int] = set()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        p = get_palette()

        # Title
        self._title = QLabel("Process Bandwidth")
        self._title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        layout.addWidget(self._title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Process", "PID", "RX Rate", "TX Rate", "Total", "Connections"
        ])

        # Configure header
        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(self.COLUMN_PROCESS, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(self.COLUMN_PID, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(self.COLUMN_RX_RATE, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(self.COLUMN_TX_RATE, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(self.COLUMN_TOTAL, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(self.COLUMN_CONNECTIONS, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)

        # Enable context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Apply theme style
        self.table.setStyleSheet(table_style())

        layout.addWidget(self.table)

    def _show_context_menu(self, position) -> None:
        """Show context menu for selected row."""
        row = self.table.rowAt(position.y())
        if row < 0:
            return

        # Get process info from the row
        pid_item = self.table.item(row, self.COLUMN_PID)
        name_item = self.table.item(row, self.COLUMN_PROCESS)

        if not pid_item or not name_item:
            return

        pid = pid_item.data(Qt.ItemDataRole.UserRole)
        process_name = name_item.data(Qt.ItemDataRole.UserRole)

        # Create context menu
        menu = QMenu(self)

        is_blocked = pid in self._blocked_pids

        if is_blocked:
            unblock_action = menu.addAction("🚫 Unblock Network Access")
            if unblock_action:
                unblock_action.triggered.connect(lambda: self.unblock_requested.emit(pid, process_name))
        else:
            block_action = menu.addAction("🚫 Block Network Access")
            if block_action:
                block_action.triggered.connect(lambda: self.block_requested.emit(pid, process_name))

        menu.addSeparator()
        copy_action = menu.addAction("📋 Copy Process Name")
        if copy_action:
            copy_action.triggered.connect(lambda: self._copy_to_clipboard(process_name))

        # Show menu
        viewport = self.table.viewport()
        if viewport:
            menu.exec(viewport.mapToGlobal(position))

    def _copy_to_clipboard(self, text: str) -> None:
        """Copy text to clipboard."""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def set_blocked_pids(self, pids: set[int]) -> None:
        """Set the set of blocked PIDs for visual indication."""
        self._blocked_pids = pids

    def update_data(self, process_stats: list[ProcessBandwidthStats]) -> None:
        """Update table with new per-process bandwidth data.

        Args:
            process_stats: List of ProcessBandwidthStats, should be sorted by rate
        """
        self._data = process_stats[:self._max_rows]

        # Disable sorting while updating for performance
        self.table.setSortingEnabled(False)

        self.table.setRowCount(len(self._data))

        for row, stats in enumerate(self._data):
            # Check if blocked
            is_blocked = stats.pid in self._blocked_pids

            # Get color based on usage or blocked status
            if is_blocked:
                color = get_color("error")
            else:
                color_key = get_usage_color(stats.total_rate)
                color = get_color(color_key)
            text_color = QColor(color)

            # Process name (with blocked indicator)
            name = stats.process_name
            if is_blocked:
                name = f"🚫 {name}"
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, stats.process_name)
            name_item.setForeground(text_color)
            name_item.setToolTip(f"PID: {stats.pid}" + (" (BLOCKED)" if is_blocked else ""))

            # PID
            pid_item = QTableWidgetItem(str(stats.pid))
            pid_item.setData(Qt.ItemDataRole.UserRole, stats.pid)
            pid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # RX Rate
            rx_item = QTableWidgetItem(format_rate(stats.rx_rate))
            rx_item.setData(Qt.ItemDataRole.UserRole, stats.rx_rate)
            rx_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            # TX Rate
            tx_item = QTableWidgetItem(format_rate(stats.tx_rate))
            tx_item.setData(Qt.ItemDataRole.UserRole, stats.tx_rate)
            tx_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            # Total
            total_item = QTableWidgetItem(format_rate(stats.total_rate))
            total_item.setData(Qt.ItemDataRole.UserRole, stats.total_rate)
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            total_item.setForeground(text_color)

            # Connections
            conn_item = QTableWidgetItem(str(stats.connection_count))
            conn_item.setData(Qt.ItemDataRole.UserRole, stats.connection_count)
            conn_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, self.COLUMN_PROCESS, name_item)
            self.table.setItem(row, self.COLUMN_PID, pid_item)
            self.table.setItem(row, self.COLUMN_RX_RATE, rx_item)
            self.table.setItem(row, self.COLUMN_TX_RATE, tx_item)
            self.table.setItem(row, self.COLUMN_TOTAL, total_item)
            self.table.setItem(row, self.COLUMN_CONNECTIONS, conn_item)

        # Re-enable sorting
        self.table.setSortingEnabled(True)

    def clear_data(self) -> None:
        """Clear all data from the table."""
        self._data = []
        self.table.setRowCount(0)

    def refresh_theme(self) -> None:
        """Refresh colors for theme change."""
        p = get_palette()
        self._title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        self.table.setStyleSheet(table_style())
        # Re-render data with new colors
        if self._data:
            self.update_data(self._data)
