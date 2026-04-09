"""Historical bandwidth graph widget showing data from SQLite database."""


from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..core.history import DailyTotal, HistoryManager
from ..core.theme import button_style, get_color, get_palette
from ..core.utils import format_bytes


class HistoricalGraph(QWidget):
    """Graph showing historical bandwidth data from SQLite database."""

    RANGE_24H = "24h"
    RANGE_7D = "7d"
    RANGE_30D = "30d"

    def __init__(self):
        super().__init__()
        self._history: HistoryManager | None = None
        self._data: list = []
        self._range = self.RANGE_24H
        self._y_max = 1024

        self._setup_ui()
        self.setMinimumSize(400, 200)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        p = get_palette()

        # Header with title and range buttons
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("Historical Bandwidth")
        self._title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        header_layout.addWidget(self._title)

        header_layout.addStretch()

        # Range buttons
        self._btn_24h = QPushButton("24h")
        self._btn_24h.setCheckable(True)
        self._btn_24h.setChecked(True)
        self._btn_24h.clicked.connect(lambda: self._set_range(self.RANGE_24H))
        self._btn_24h.setStyleSheet(button_style())
        header_layout.addWidget(self._btn_24h)

        self._btn_7d = QPushButton("7d")
        self._btn_7d.setCheckable(True)
        self._btn_7d.clicked.connect(lambda: self._set_range(self.RANGE_7D))
        self._btn_7d.setStyleSheet(button_style())
        header_layout.addWidget(self._btn_7d)

        self._btn_30d = QPushButton("30d")
        self._btn_30d.setCheckable(True)
        self._btn_30d.clicked.connect(lambda: self._set_range(self.RANGE_30D))
        self._btn_30d.setStyleSheet(button_style())
        header_layout.addWidget(self._btn_30d)

        layout.addWidget(header)

        try:
            self._history = HistoryManager()
        except Exception:
            pass

        self._load_data()

    def _set_range(self, range_val: str) -> None:
        """Set the time range and reload data."""
        self._range = range_val

        # Update button states
        self._btn_24h.setChecked(range_val == self.RANGE_24H)
        self._btn_7d.setChecked(range_val == self.RANGE_7D)
        self._btn_30d.setChecked(range_val == self.RANGE_30D)

        self._load_data()
        self.update()

    def _load_data(self) -> None:
        """Load data from history database."""
        if not self._history:
            self._data = []
            return

        try:
            if self._range == self.RANGE_24H:
                # Get hourly stats for last 24 hours
                stats = self._history.get_hourly_stats(days=1)
                self._data = stats
            elif self._range == self.RANGE_7D:
                # Get hourly stats for last 7 days
                stats = self._history.get_hourly_stats(days=7)
                self._data = stats
            else:
                # Get daily totals for last 30 days
                totals = self._history.get_daily_totals(days=30)
                self._data = totals

            # Calculate Y-axis max
            if self._data:
                if self._range == self.RANGE_30D:
                    max_val = max(
                        max((d.inet_rx_total + d.inet_tx_total) for d in self._data),
                        1024
                    )
                else:
                    max_val = max(
                        max((d.inet_rx_total + d.inet_tx_total) for d in self._data),
                        1024
                    )
                self._y_max = max_val
        except Exception:
            self._data = []

    def refresh(self) -> None:
        """Refresh data from database."""
        self._load_data()
        self.update()

    def paintEvent(self, event) -> None:
        """Draw the graph."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p = get_palette()

        # Get drawing area
        margin_left = 70
        margin_right = 20
        margin_top = 40
        margin_bottom = 30

        graph_rect = self.rect().adjusted(
            margin_left, margin_top,
            -margin_right, -margin_bottom
        )

        # Draw background
        painter.fillRect(self.rect(), QColor(p.bg_primary))

        # Draw graph background and border
        painter.fillRect(graph_rect, QColor(p.graph_bg))
        border_pen = QPen(QColor(p.graph_border))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.drawRect(graph_rect)

        if not self._data:
            # No data message
            painter.setPen(QColor(p.text_secondary))
            painter.setFont(QFont("sans-serif", 10))
            painter.drawText(graph_rect, Qt.AlignmentFlag.AlignCenter, "No historical data")
            painter.end()
            return

        # Draw grid
        self._draw_grid(painter, graph_rect)

        # Draw data
        self._draw_bars(painter, graph_rect)

        # Draw Y-axis labels
        self._draw_y_axis(painter, graph_rect)

        # Draw X-axis labels
        self._draw_x_axis(painter, graph_rect)

        painter.end()

    def _draw_grid(self, painter: QPainter, rect) -> None:
        """Draw grid lines."""
        p = get_palette()
        pen = QPen(QColor(p.graph_border))
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        # Horizontal lines
        for i in range(5):
            y = rect.top() + (rect.height() * i / 4)
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))

    def _draw_bars(self, painter: QPainter, rect) -> None:
        """Draw bar chart for historical data."""
        if not self._data:
            return

        num_bars = len(self._data)
        bar_width = max(rect.width() / num_bars - 2, 4)

        y_scale = rect.height() / max(self._y_max, 1)

        # Get colors from theme
        rx_color = QColor(get_color("download"))
        tx_color = QColor(get_color("upload"))

        for i, item in enumerate(self._data):
            # Get values based on data type
            if isinstance(item, DailyTotal):
                rx_val = item.inet_rx_total
                tx_val = item.inet_tx_total
            else:  # HourlyStats
                rx_val = item.inet_rx_total
                tx_val = item.inet_tx_total

            x = rect.left() + (rect.width() * i / num_bars) + 1

            # Draw RX bar
            rx_height = min(rx_val * y_scale, rect.height())
            rx_rect = rect.adjusted(0, 0, 0, 0)
            rx_rect.setLeft(int(x))
            rx_rect.setRight(int(x + bar_width / 2))
            rx_rect.setTop(int(rect.bottom() - rx_height))

            painter.fillRect(rx_rect, rx_color)

            # Draw TX bar
            tx_height = min(tx_val * y_scale, rect.height())
            tx_rect = rect.adjusted(0, 0, 0, 0)
            tx_rect.setLeft(int(x + bar_width / 2))
            tx_rect.setRight(int(x + bar_width))
            tx_rect.setTop(int(rect.bottom() - tx_height))

            painter.fillRect(tx_rect, tx_color)

    def _draw_y_axis(self, painter: QPainter, rect) -> None:
        """Draw Y-axis labels."""
        p = get_palette()
        font = QFont("monospace", 8)
        painter.setFont(font)
        painter.setPen(QColor(p.text_secondary))

        # Top label
        painter.drawText(5, rect.top() + 4, format_bytes(int(self._y_max)))

        # Middle label
        painter.drawText(5, rect.top() + rect.height() // 2 + 4, format_bytes(int(self._y_max / 2)))

        # Bottom label
        painter.drawText(5, rect.bottom() + 4, "0 B")

    def _draw_x_axis(self, painter: QPainter, rect) -> None:
        """Draw X-axis labels."""
        p = get_palette()
        font = QFont("monospace", 7)
        painter.setFont(font)
        painter.setPen(QColor(p.text_secondary))

        if not self._data:
            return

        # Show a few time labels
        num_labels = min(5, len(self._data))
        step = max(len(self._data) // num_labels, 1)

        for i in range(0, len(self._data), step):
            item = self._data[i]
            x = rect.left() + (rect.width() * i / len(self._data))

            # Format label based on data type
            if isinstance(item, DailyTotal):
                label = item.date.strftime("%m/%d")
            else:  # HourlyStats
                label = item.hour.strftime("%m/%d %H:00")

            painter.drawText(int(x), rect.bottom() + 15, label)

    def refresh_theme(self) -> None:
        """Refresh colors for theme change."""
        p = get_palette()
        self._title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        self._btn_24h.setStyleSheet(button_style())
        self._btn_7d.setStyleSheet(button_style())
        self._btn_30d.setStyleSheet(button_style())
        self.update()
