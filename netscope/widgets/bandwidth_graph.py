from collections import deque

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..core.theme import get_color, get_palette
from ..core.utils import format_rate


class BandwidthGraph(QWidget):
    """Real-time rolling graph showing bandwidth history over last 60 seconds."""

    def __init__(self, history_seconds: int = 60):
        super().__init__()
        self.history_seconds = history_seconds

        # History deques for bandwidth data (bytes/sec)
        self._rx_history: deque[float] = deque(maxlen=history_seconds)
        self._tx_history: deque[float] = deque(maxlen=history_seconds)

        # Initialize with zeros
        for _ in range(history_seconds):
            self._rx_history.append(0)
            self._tx_history.append(0)

        # Current rates for display
        self._current_rx = 0.0
        self._current_tx = 0.0

        # Y-axis max (auto-scaling)
        self._y_max: float = 1024  # Start at 1 KB/s minimum

        self._setup_ui()

        # Minimum size for the graph
        self.setMinimumSize(300, 150)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        p = get_palette()

        # Title
        self._title = QLabel("Bandwidth History (60s)")
        self._title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        layout.addWidget(self._title)

    def update_data(self, rx_rate: float, tx_rate: float) -> None:
        """Add a new data point to the graph.

        Args:
            rx_rate: Download rate in bytes/sec
            tx_rate: Upload rate in bytes/sec
        """
        self._rx_history.append(rx_rate)
        self._tx_history.append(tx_rate)
        self._current_rx = rx_rate
        self._current_tx = tx_rate

        # Auto-scale Y-axis
        max_val = max(max(self._rx_history), max(self._tx_history), 1024)
        # Smooth scaling - grow immediately, shrink slowly
        if max_val > self._y_max:
            self._y_max = max_val
        else:
            # Slow decay towards actual max
            self._y_max = max(max_val, self._y_max * 0.98)

        self.update()  # Trigger repaint

    def paintEvent(self, event) -> None:
        """Draw the graph using QPainter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        p = get_palette()

        # Get drawing area (excluding title area)
        title_height = 24
        margin_left = 60  # Space for Y-axis labels
        margin_right = 10
        margin_top = 10 + title_height
        margin_bottom = 25  # Space for X-axis labels

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

        # Draw grid lines
        self._draw_grid(painter, graph_rect)

        # Draw the data lines
        rx_color = QColor(get_color("download"))
        tx_color = QColor(get_color("upload"))
        self._draw_line(painter, graph_rect, self._rx_history, rx_color, "RX")
        self._draw_line(painter, graph_rect, self._tx_history, tx_color, "TX")

        # Draw current rates overlay
        self._draw_overlay(painter, graph_rect)

        # Draw Y-axis labels
        self._draw_y_axis(painter, graph_rect)

        # Draw X-axis labels
        self._draw_x_axis(painter, graph_rect)

        painter.end()

    def _draw_grid(self, painter: QPainter, rect) -> None:
        """Draw grid lines for readability."""
        p = get_palette()
        pen = QPen(QColor(p.graph_border))
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        # Horizontal lines (5 divisions)
        for i in range(6):
            y = rect.top() + (rect.height() * i / 5)
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))

        # Vertical lines (every 10 seconds)
        num_lines = self.history_seconds // 10
        for i in range(1, num_lines):
            x = rect.left() + (rect.width() * i / num_lines)
            painter.drawLine(int(x), rect.top(), int(x), rect.bottom())

    def _draw_line(self, painter: QPainter, rect, data: deque, color: QColor, label: str) -> None:
        """Draw a single data line on the graph.

        Args:
            painter: QPainter instance
            rect: Graph rectangle
            data: Deque of data points
            color: Line color
            label: Line label for legend
        """
        if len(data) < 2:
            return

        # Create gradient fill under the line
        gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        gradient.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 160))
        gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 40))

        # Build polygon for fill
        points = []
        points.append((rect.left(), rect.bottom()))  # Start at bottom-left

        y_scale = rect.height() / max(self._y_max, 1)

        for i, value in enumerate(data):
            x = rect.left() + (rect.width() * i / (len(data) - 1))
            y = rect.bottom() - min(value * y_scale, rect.height())
            points.append((x, y))

        points.append((rect.right(), rect.bottom()))  # End at bottom-right

        # Draw fill
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QPolygon
        polygon = QPolygon([QPoint(int(x), int(y)) for x, y in points])
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(polygon)

        # Draw line on top
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)

        for i in range(1, len(data)):
            x1 = rect.left() + (rect.width() * (i - 1) / (len(data) - 1))
            y1 = rect.bottom() - min(data[i - 1] * y_scale, rect.height())
            x2 = rect.left() + (rect.width() * i / (len(data) - 1))
            y2 = rect.bottom() - min(data[i] * y_scale, rect.height())
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    def _draw_overlay(self, painter: QPainter, rect) -> None:
        """Draw current rate values as overlay with a semi-transparent backdrop."""
        font = QFont("monospace", 9)
        painter.setFont(font)

        # Semi-transparent dark backdrop ensures WCAG AA contrast for text in all themes
        backdrop_x = rect.left() + 3
        backdrop_y = rect.top() + 2
        painter.setBrush(QBrush(QColor(0, 0, 0, 120)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(backdrop_x, backdrop_y, 110, 36, 3, 3)

        # RX rate (download color)
        painter.setPen(QColor(get_color("download")))
        rx_text = f"RX: {format_rate(self._current_rx)}"
        painter.drawText(rect.left() + 7, rect.top() + 15, rx_text)

        # TX rate (upload color)
        painter.setPen(QColor(get_color("upload")))
        tx_text = f"TX: {format_rate(self._current_tx)}"
        painter.drawText(rect.left() + 7, rect.top() + 30, tx_text)

    def _draw_y_axis(self, painter: QPainter, rect) -> None:
        """Draw Y-axis labels."""
        p = get_palette()
        font = QFont("monospace", 8)
        painter.setFont(font)
        painter.setPen(QColor(p.text_secondary))

        # Top label (max)
        max_label = format_rate(self._y_max)
        painter.drawText(5, rect.top() + 4, max_label)

        # Middle label
        mid_label = format_rate(self._y_max / 2)
        painter.drawText(5, rect.top() + rect.height() // 2 + 4, mid_label)

        # Bottom label
        painter.drawText(5, rect.bottom() + 4, "0 B/s")

    def _draw_x_axis(self, painter: QPainter, rect) -> None:
        """Draw X-axis labels."""
        p = get_palette()
        font = QFont("monospace", 8)
        painter.setFont(font)
        painter.setPen(QColor(p.text_secondary))

        # "now" on the right
        painter.drawText(rect.right() - 25, rect.bottom() + 15, "now")

        # Time labels on the left
        painter.drawText(rect.left() - 5, rect.bottom() + 15, f"-{self.history_seconds}s")

    def refresh_theme(self) -> None:
        """Refresh colors for theme change."""
        p = get_palette()
        self._title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        self.update()  # Trigger repaint
