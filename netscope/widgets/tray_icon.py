"""System tray icon with live bandwidth graph."""

from collections import deque

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow, QMenu, QMessageBox, QSystemTrayIcon

from ..core.theme import get_color, get_palette

# Try to load icon from resources
try:
    from ..resources import get_tray_icon
    _HAS_RESOURCE_ICONS = True
except ImportError:
    _HAS_RESOURCE_ICONS = False


class TrayIcon(QSystemTrayIcon):
    """System tray icon showing real-time bandwidth activity."""

    # Signals
    show_settings_requested = pyqtSignal()
    monitoring_toggled = pyqtSignal(bool)  # enabled/disabled

    # Icon size for system tray
    ICON_SIZE = 22

    # Number of data points for sparkline graph
    HISTORY_LENGTH = 30

    # Activity thresholds (bytes/sec) for color indication
    LOW_THRESHOLD = 100 * 1024       # 100 KB/s
    MEDIUM_THRESHOLD = 1024 * 1024   # 1 MB/s
    HIGH_THRESHOLD = 10 * 1024 * 1024  # 10 MB/s

    def __init__(self, main_window: QMainWindow, parent=None):
        super().__init__(parent)

        self.main_window = main_window
        self._monitoring_enabled = True

        # Bandwidth history for sparkline
        self._rx_history: deque[float] = deque(maxlen=self.HISTORY_LENGTH)
        self._tx_history: deque[float] = deque(maxlen=self.HISTORY_LENGTH)

        # Current stats
        self._current_rx_rate = 0.0
        self._current_tx_rate = 0.0
        self._current_lan_rx = 0.0
        self._current_lan_tx = 0.0
        self._current_inet_rx = 0.0
        self._current_inet_tx = 0.0

        # Animation state
        self._animation_frame = 0
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate_icon)

        # Data cap tracking (can be set externally)
        self._data_cap_gb: float = 0  # 0 means no cap
        self._data_used_gb: float = 0.0

        # Initialize history with zeros
        for _ in range(self.HISTORY_LENGTH):
            self._rx_history.append(0.0)
            self._tx_history.append(0.0)

        # Setup tray icon
        self._setup_icon()
        self._setup_menu()

        # Connect activation signal (click on tray icon)
        self.activated.connect(self._on_activated)

        # Check if system tray is available
        if not self.isSystemTrayAvailable():
            print("[warning] System tray is not available on this system")

    def _setup_icon(self) -> None:
        """Initialize the tray icon."""
        if _HAS_RESOURCE_ICONS:
            icon = get_tray_icon()
            if not icon.isNull():
                self.setIcon(icon)
            else:
                pixmap = self._create_icon(0, 0)
                self.setIcon(QIcon(pixmap))
        else:
            pixmap = self._create_icon(0, 0)
            self.setIcon(QIcon(pixmap))
        self.setToolTip("NetScope\nInitializing...")

    def _setup_menu(self) -> None:
        """Setup the context menu."""
        menu = QMenu()

        # Show/Hide main window action
        self._show_hide_action = menu.addAction("Hide Main Window")
        self._show_hide_action.setCheckable(True)
        self._show_hide_action.setChecked(True)
        self._show_hide_action.triggered.connect(self._toggle_main_window)

        menu.addSeparator()

        # Enable/Disable monitoring action
        self._monitoring_action = menu.addAction("Monitoring Enabled")
        self._monitoring_action.setCheckable(True)
        self._monitoring_action.setChecked(True)
        self._monitoring_action.triggered.connect(self._toggle_monitoring)

        # Data cap display (if configured)
        self._data_cap_action = menu.addAction("Data Cap: -- / --")
        self._data_cap_action.setEnabled(False)

        menu.addSeparator()

        # Settings action
        settings_action = menu.addAction("Settings...")
        settings_action.triggered.connect(self._on_settings)

        # About action
        about_action = menu.addAction("About")
        about_action.triggered.connect(self._on_about)

        menu.addSeparator()

        # Quit action
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._on_quit)

        self.setContextMenu(menu)

    def update_stats(self, rx_rate: float, tx_rate: float,
                     lan_rx: float = 0.0, lan_tx: float = 0.0,
                     inet_rx: float = 0.0, inet_tx: float = 0.0) -> None:
        """Update the tray icon with current rates.

        Args:
            rx_rate: Download rate in bytes/sec
            tx_rate: Upload rate in bytes/sec
            lan_rx: LAN download rate in bytes/sec
            lan_tx: LAN upload rate in bytes/sec
            inet_rx: Internet download rate in bytes/sec
            inet_tx: Internet upload rate in bytes/sec
        """
        self._current_rx_rate = rx_rate
        self._current_tx_rate = tx_rate
        self._current_lan_rx = lan_rx
        self._current_lan_tx = lan_tx
        self._current_inet_rx = inet_rx
        self._current_inet_tx = inet_tx

        # Add to history
        self._rx_history.append(rx_rate)
        self._tx_history.append(tx_rate)

        # Update icon and tooltip
        self.update_icon()

        # Start animation if there's activity
        if (rx_rate > self.LOW_THRESHOLD or tx_rate > self.LOW_THRESHOLD):
            if not self._animation_timer.isActive():
                self._animation_timer.start(100)  # 10 FPS animation
        else:
            self._animation_timer.stop()
            self._animation_frame = 0

    def update_icon(self) -> None:
        """Redraw the icon with mini bandwidth graph."""
        pixmap = self._create_icon(self._current_rx_rate, self._current_tx_rate)
        self.setIcon(QIcon(pixmap))

        # Update tooltip
        self._update_tooltip()

    def set_data_cap(self, used_gb: float, total_gb: float, enabled: bool = True) -> None:
        """Update data cap display.

        Args:
            used_gb: Data used in GB
            total_gb: Total data cap in GB
            enabled: Whether data cap tracking is enabled
        """
        self._data_used_gb = used_gb
        self._data_cap_gb = total_gb

        if not enabled:
            self._data_cap_action.setText("Data Cap: Disabled")
        elif total_gb > 0:
            percent = (used_gb / total_gb * 100) if total_gb > 0 else 0
            self._data_cap_action.setText(f"Data Cap: {used_gb:.1f} / {total_gb:.0f} GB ({percent:.0f}%)")
        else:
            self._data_cap_action.setText("Data Cap: Not configured")

    def show_notification(self, title: str, message: str,
                          icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information) -> None:
        """Show a balloon notification from tray.

        Args:
            title: Notification title
            message: Notification message
            icon: Icon type (Information, Warning, Critical)
        """
        if self.supportsMessages():
            self.showMessage(title, message, icon, 5000)  # 5 second timeout

    def _create_icon(self, rx_rate: float, tx_rate: float) -> QPixmap:
        """Create a dynamic icon with mini bandwidth graph.

        Creates a 22x22 pixel icon with:
        - A small sparkline graph showing last 30 data points
        - Green line for download, orange for upload
        - Subtle animation effect when data is flowing
        """
        p = get_palette()
        size = self.ICON_SIZE
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background circle
        margin = 1
        painter.setBrush(QBrush(QColor(p.bg_secondary)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)

        # Draw sparkline graph
        self._draw_sparkline(painter, rx_rate, tx_rate, size)

        # Draw activity indicator (animated dot)
        if rx_rate > 0 or tx_rate > 0:
            self._draw_activity_indicator(painter, rx_rate, tx_rate, size)

        painter.end()
        return pixmap

    def _draw_sparkline(self, painter: QPainter, rx_rate: float, tx_rate: float, size: int) -> None:
        """Draw a mini sparkline graph on the icon."""
        # Graph area (leave margin for circle)
        margin = 3
        graph_width = size - 2 * margin
        graph_height = size - 2 * margin - 4  # Leave space for activity indicator

        # Find max value for scaling
        max_rx = max(self._rx_history) if self._rx_history else 1
        max_tx = max(self._tx_history) if self._tx_history else 1
        max_val = max(max_rx, max_tx, 1)  # Avoid division by zero

        # Calculate point positions
        points_rx = []
        points_tx = []

        for i, (rx, tx) in enumerate(zip(self._rx_history, self._tx_history)):
            x = margin + (i * graph_width) / (self.HISTORY_LENGTH - 1)

            # Scale to graph height
            y_rx = margin + graph_height - (rx / max_val) * graph_height * 0.8
            y_tx = margin + graph_height - (tx / max_val) * graph_height * 0.8

            points_rx.append((x, y_rx))
            points_tx.append((x, y_tx))

        # Get colors from theme
        upload_color = QColor(get_color("upload"))
        download_color = QColor(get_color("download"))

        # Draw upload line (orange) - draw first so download is on top
        if len(points_tx) >= 2:
            pen = QPen(upload_color)
            pen.setWidthF(1.0)
            painter.setPen(pen)

            for i in range(1, len(points_tx)):
                painter.drawLine(
                    int(points_tx[i-1][0]), int(points_tx[i-1][1]),
                    int(points_tx[i][0]), int(points_tx[i][1])
                )

        # Draw download line (green)
        if len(points_rx) >= 2:
            pen = QPen(download_color)
            pen.setWidthF(1.0)
            painter.setPen(pen)

            for i in range(1, len(points_rx)):
                painter.drawLine(
                    int(points_rx[i-1][0]), int(points_rx[i-1][1]),
                    int(points_rx[i][0]), int(points_rx[i][1])
                )

    def _draw_activity_indicator(self, painter: QPainter, rx_rate: float, tx_rate: float, size: int) -> None:
        """Draw an animated activity indicator dot."""
        # Position at bottom of icon
        center_x = size // 2
        center_y = size - 4

        # Determine color based on activity level
        total_rate = rx_rate + tx_rate
        if total_rate >= self.HIGH_THRESHOLD:
            color = QColor(get_color("error"))
        elif total_rate >= self.MEDIUM_THRESHOLD:
            color = QColor(get_color("warning"))
        else:
            color = QColor(get_color("success"))

        # Animation: pulsing effect
        base_radius = 2
        pulse = abs(self._animation_frame % 6 - 3) * 0.5
        radius = base_radius + pulse

        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            int(center_x - radius),
            int(center_y - radius),
            int(radius * 2),
            int(radius * 2)
        )

    def _animate_icon(self) -> None:
        """Animate the icon when there's activity."""
        self._animation_frame = (self._animation_frame + 1) % 60
        self.update_icon()

    def _update_tooltip(self) -> None:
        """Update the tray icon tooltip with current stats."""
        rx_str = self._format_rate(self._current_rx_rate)
        tx_str = self._format_rate(self._current_tx_rate)
        lan_rx_str = self._format_rate(self._current_lan_rx)
        lan_tx_str = self._format_rate(self._current_lan_tx)
        inet_rx_str = self._format_rate(self._current_inet_rx)
        inet_tx_str = self._format_rate(self._current_inet_tx)

        tooltip = (
            f"NetScope\n"
            f"↓ {rx_str}  ↑ {tx_str}\n"
            f"LAN: ↓ {lan_rx_str}  ↑ {lan_tx_str}\n"
            f"Internet: ↓ {inet_rx_str}  ↑ {inet_tx_str}"
        )

        self.setToolTip(tooltip)

    def _format_rate(self, bps: float) -> str:
        """Format bytes/sec as human readable."""
        if bps < 1024:
            return f"{bps:.0f} B/s"
        elif bps < 1024 ** 2:
            return f"{bps/1024:.1f} KB/s"
        elif bps < 1024 ** 3:
            return f"{bps/1024**2:.1f} MB/s"
        else:
            return f"{bps/1024**3:.1f} GB/s"

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (click)."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Left click: toggle main window
            self._toggle_main_window()
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            # Middle click: toggle monitoring
            self._toggle_monitoring()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Double click: show main window and bring to front
            self.main_window.show()
            self.main_window.activateWindow()
            self.main_window.raise_()
            self._show_hide_action.setChecked(True)
            self._show_hide_action.setText("Hide Main Window")

    def _toggle_main_window(self) -> None:
        """Toggle main window visibility."""
        if self.main_window.isVisible():
            self.main_window.hide()
            self._show_hide_action.setChecked(False)
            self._show_hide_action.setText("Show Main Window")
        else:
            self.main_window.show()
            self.main_window.activateWindow()
            self._show_hide_action.setChecked(True)
            self._show_hide_action.setText("Hide Main Window")

    def _toggle_monitoring(self) -> None:
        """Toggle monitoring on/off."""
        self._monitoring_enabled = not self._monitoring_enabled
        self._monitoring_action.setChecked(self._monitoring_enabled)

        if self._monitoring_enabled:
            self._monitoring_action.setText("Monitoring Enabled")
        else:
            self._monitoring_action.setText("Monitoring Disabled")

        self.monitoring_toggled.emit(self._monitoring_enabled)

    def _on_settings(self) -> None:
        """Open settings dialog."""
        self.show_settings_requested.emit()

    def _on_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self.main_window,
            "About NetScope",
            "<h2>NetScope</h2>"
            "<p><b>Version 1.0.0</b></p>"
            "<p>Linux Network Monitor</p>"
            "<hr>"
            "<p>Real-time bandwidth monitoring with:</p>"
            "<ul>"
            "<li>LAN/Internet traffic split</li>"
            "<li>Per-process connection tracking</li>"
            "<li>Data cap tracking</li>"
            "<li>Historical data storage</li>"
            "</ul>"
            "<hr>"
            "<p><small>Built with PyQt6</small></p>"
        )

    def _on_quit(self) -> None:
        """Quit the application."""
        # Stop animation timer
        self._animation_timer.stop()

        # Force quit the main window (bypass minimize-to-tray)
        if hasattr(self.main_window, 'quit_app'):
            self.main_window.quit_app()
        else:
            self.main_window.close()

        # Quit application
        QApplication.quit()

    def update_window_visibility_state(self) -> None:
        """Update menu state based on current window visibility."""
        is_visible = self.main_window.isVisible()
        self._show_hide_action.setChecked(is_visible)
        self._show_hide_action.setText("Hide Main Window" if is_visible else "Show Main Window")

    def cleanup(self) -> None:
        """Clean up resources before exit."""
        self._animation_timer.stop()
        self.hide()
        self.setContextMenu(None)
