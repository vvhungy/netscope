"""Main application window."""

import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import load_config
from ..core.alert_rules import get_alert_manager
from ..core.bandwidth import BandwidthStats
from ..core.data_cap import DataCapTracker
from ..core.history import HistoryManager
from ..core.iptables import IPTablesError, IPTablesManager
from ..core.process_bandwidth import ProcessBandwidthTracker
from ..core.traffic_blocker import TrafficBlocker
from ..core.utils import format_rate
from ..widgets import (
    BandwidthGraph,
    BandwidthPanel,
    DestinationsPanel,
    HistoricalGraph,
    ProcessBandwidthTable,
    ProcessTable,
)
from ..widgets.listening_ports import ListeningPortsWidget
from ..widgets.tray_icon import TrayIcon
from ..workers import BandwidthWorker, ConnectionWorker


def get_primary_interface() -> str:
    """Detect primary network interface."""
    try:
        out = subprocess.check_output(
            ["ip", "route", "get", "8.8.8.8"],
            text=True, stderr=subprocess.DEVNULL
        )
        parts = out.split()
        if "dev" in parts:
            return parts[parts.index("dev") + 1]
    except Exception:
        pass

    # Fallback: first non-loopback from /proc/net/dev
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if ":" in line:
                    name = line.split(":")[0].strip()
                    if name != "lo":
                        return name
    except Exception:
        pass

    return "eth0"


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, tray_icon: TrayIcon | None = None):
        super().__init__()
        self.setWindowTitle("NetScope")
        self.setMinimumSize(700, 500)

        self.config = load_config()

        # Determine interface
        if self.config["interface"] == "auto":
            self.interface = get_primary_interface()
        else:
            self.interface = self.config["interface"]

        self.iptables: IPTablesManager | None = None
        self.bw_worker: BandwidthWorker | None = None
        self.conn_worker: ConnectionWorker | None = None
        self.process_bandwidth_tracker = ProcessBandwidthTracker()

        # Data cap tracker
        self.data_cap_tracker = DataCapTracker(
            monthly_cap_gb=self.config.get("data_cap_gb", 100.0),
            enabled=self.config.get("data_cap_enabled", False),
            warn_50=self.config.get("data_cap_warn_50", True),
            warn_75=self.config.get("data_cap_warn_75", True),
            warn_90=self.config.get("data_cap_warn_90", True),
        )

        # Alert rules manager
        self._alert_manager = get_alert_manager()
        self._alert_manager.set_on_alert(self._on_alert_triggered)

        # Tray icon reference
        self.tray_icon = tray_icon

        # Connect tray icon signals
        if self.tray_icon:
            self.tray_icon.show_settings_requested.connect(self._on_settings_requested)

        # Track force quit state (vs minimize to tray)
        self._force_quit = False

        # Alert notification buffer: accumulate messages across ticks, flush after 3s quiet
        self._pending_alert_messages: list[str] = []
        self._alert_flush_timer = QTimer(self)
        self._alert_flush_timer.setSingleShot(True)
        self._alert_flush_timer.setInterval(3000)
        self._alert_flush_timer.timeout.connect(self._flush_alert_notifications)

        # History: write one sample per minute, refresh graph on same cadence
        self._history_manager = HistoryManager()
        self._last_stats: BandwidthStats | None = None
        self._history_write_timer = QTimer(self)
        self._history_write_timer.setInterval(60_000)
        self._history_write_timer.timeout.connect(self._write_history_sample)
        self._history_write_timer.start()
        self._history_refresh_timer = QTimer(self)
        self._history_refresh_timer.setInterval(60_000)
        self._history_refresh_timer.timeout.connect(self._refresh_historical_graph)
        self._history_refresh_timer.start()

        self._setup_ui()
        self._setup_menu()
        self._setup_workers()

        # Load saved theme preference and apply it
        from ..core.theme import Theme, ThemeMode
        saved_theme = self.config.get("theme", "system")
        mode_map = {"system": ThemeMode.SYSTEM, "dark": ThemeMode.DARK, "light": ThemeMode.LIGHT}
        Theme.set_mode(mode_map.get(saved_theme, ThemeMode.SYSTEM))

        # Update menu check mark to match saved preference
        if saved_theme in self._theme_actions:
            self._theme_actions[saved_theme].setChecked(True)

        # Apply theme to main window and all widgets
        self._refresh_all_themes()

        # Auto-update when OS switches color scheme (Qt 6.5+)
        try:
            from PyQt6.QtGui import QGuiApplication
            app = QGuiApplication.instance()
            if isinstance(app, QGuiApplication):
                app.styleHints().colorSchemeChanged.connect(self._on_system_color_scheme_changed)
        except Exception:
            pass

    def _setup_ui(self) -> None:
        """Initialize UI components."""
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header
        from ..core.theme import get_palette
        p = get_palette()
        self._header_label = QLabel(f"Interface: {self.interface}")
        self._header_label.setStyleSheet(f"font-size: 12px; color: {p.text_secondary};")
        layout.addWidget(self._header_label)

        # Main content in splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Bandwidth panel and graph
        self.bandwidth_panel = BandwidthPanel()
        self.bandwidth_graph = BandwidthGraph()

        # Combine panel and graph in a horizontal layout
        bw_container = QWidget()
        bw_layout = QHBoxLayout(bw_container)
        bw_layout.setContentsMargins(0, 0, 0, 0)
        bw_layout.addWidget(self.bandwidth_panel, 1)
        bw_layout.addWidget(self.bandwidth_graph, 1)

        splitter.addWidget(bw_container)

        # Historical bandwidth graph
        self.historical_graph = HistoricalGraph()
        splitter.addWidget(self.historical_graph)

        # Process bandwidth table
        self.process_bandwidth_table = ProcessBandwidthTable()

        # Traffic blocker
        self._traffic_blocker = TrafficBlocker()
        self.process_bandwidth_table.block_requested.connect(self._on_block_process)
        self.process_bandwidth_table.unblock_requested.connect(self._on_unblock_process)
        self.process_bandwidth_table.view_connections_requested.connect(self._on_view_process_connections)

        # Process connections table
        self.process_table = ProcessTable()
        self.process_table.view_connections_requested.connect(self._on_view_process_connections)

        # Listening ports widget
        self.listening_ports = ListeningPortsWidget()

        # Tab widget combining all process/port views
        self._process_tabs = QTabWidget()
        self._process_tabs.addTab(self.process_bandwidth_table, "Bandwidth")
        self._process_tabs.addTab(self.process_table, "Connections")
        self._process_tabs.addTab(self.listening_ports, "Listening Ports")

        # Destinations panel
        self.destinations_panel = DestinationsPanel()

        # Bottom horizontal splitter: process tabs left, destinations right
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.addWidget(self._process_tabs)
        bottom_splitter.addWidget(self.destinations_panel)
        bottom_splitter.setSizes([600, 300])

        splitter.addWidget(bottom_splitter)

        # Set initial sizes for vertical splitter
        splitter.setSizes([150, 150, 350])

        layout.addWidget(splitter, 1)

        # Status bar
        self.statusBar().showMessage("Initializing...")

    def _setup_workers(self) -> None:
        """Initialize background workers."""
        # Setup iptables
        self.iptables = IPTablesManager(
            interface=self.interface,
            lan_subnet=self.config["lan_subnet"]
        )

        try:
            self.iptables.setup()
            self.statusBar().showMessage(f"Monitoring {self.interface}")
        except IPTablesError as e:
            QMessageBox.critical(
                self,
                "IPTables Error",
                f"Failed to setup iptables rules:\n{e}\n\n"
                "Make sure you have sudo access."
            )
            self.close()
            return

        # Create workers
        self.bw_worker = BandwidthWorker(
            self.iptables,
            interval=self.config["update_interval"]
        )
        self.bw_worker.stats_ready.connect(self._on_bandwidth_stats)
        self.bw_worker.error_occurred.connect(self._on_worker_error)

        self.conn_worker = ConnectionWorker(
            interval=self.config["connection_interval"]
        )
        self.conn_worker.summary_ready.connect(self._on_connection_summary)
        self.conn_worker.listening_ports_ready.connect(self.listening_ports.update_data)
        self.conn_worker.error_occurred.connect(self._on_worker_error)

        # Start workers
        self.bw_worker.start()
        self.conn_worker.start()

    def _on_bandwidth_stats(self, stats: BandwidthStats) -> None:
        """Handle bandwidth stats update."""
        self._last_stats = stats
        self.bandwidth_panel.update_stats(stats)

        # Update bandwidth graph with total rates
        self.bandwidth_graph.update_data(stats.total_rx_rate, stats.total_tx_rate)

        # Update process bandwidth table
        process_stats = self.process_bandwidth_tracker.get_process_stats(
            total_rx_rate=stats.total_rx_rate,
            total_tx_rate=stats.total_tx_rate
        )
        self.process_bandwidth_table.update_data(process_stats)

        # Update data cap tracker with session totals
        self.data_cap_tracker.update_session_usage(
            rx_total=stats.total_rx,
            tx_total=stats.total_tx
        )

        # Update data cap display
        data_cap_status = self.data_cap_tracker.get_status()
        self.bandwidth_panel.update_data_cap(data_cap_status)

        # Check for new warnings
        warning = self.data_cap_tracker.get_new_warning(data_cap_status)
        if warning:
            self.statusBar().showMessage(warning, 5000)  # Show for 5 seconds

        # Check custom alert rules
        data_cap_percent = 0.0
        if data_cap_status.enabled and data_cap_status.monthly_cap_gb > 0:
            data_cap_percent = data_cap_status.percent_used

        self._alert_manager.check_rate_alerts(
            rx_rate=stats.total_rx_rate,
            tx_rate=stats.total_tx_rate,
            data_cap_percent=data_cap_percent
        )

        # Also check volume-based alerts
        self._alert_manager.update_volume_tracking(
            rx_bytes=stats.total_rx,
            tx_bytes=stats.total_tx
        )

        # Update status bar with total rate
        rx_str = format_rate(stats.total_rx_rate)
        tx_str = format_rate(stats.total_tx_rate)
        self.statusBar().showMessage(
            f"RX: {rx_str}  TX: {tx_str}  |  {self.interface}"
        )

        # Update tray icon if available
        if self.tray_icon:
            self.tray_icon.update_stats(
                rx_rate=stats.total_rx_rate,
                tx_rate=stats.total_tx_rate,
                lan_rx=stats.lan_rx_rate,
                lan_tx=stats.lan_tx_rate,
                inet_rx=stats.inet_rx_rate,
                inet_tx=stats.inet_tx_rate
            )
            # Update data cap in tray menu (always update, even if disabled)
            self.tray_icon.set_data_cap(data_cap_status.used_gb, data_cap_status.monthly_cap_gb, data_cap_status.enabled)

    def _on_connection_summary(
        self,
        process_connections: dict,
        service_ips: dict
    ) -> None:
        """Handle connection summary update."""
        self.process_table.update_data(process_connections)
        self.destinations_panel.update_data(service_ips)

    def _on_worker_error(self, error: str) -> None:
        """Handle worker error."""
        self.statusBar().showMessage(f"Error: {error}")

    def _write_history_sample(self) -> None:
        """Write current bandwidth totals to history DB (called every 60s)."""
        if self._last_stats is None:
            return
        s = self._last_stats
        self._history_manager.add_sample(
            lan_rx=int(s.lan_rx_total),
            lan_tx=int(s.lan_tx_total),
            inet_rx=int(s.inet_rx_total),
            inet_tx=int(s.inet_tx_total),
        )

    def _refresh_historical_graph(self) -> None:
        """Reload history DB data into the historical graph (called every 60s)."""
        self.historical_graph.refresh()

    def _on_alert_triggered(self, rule, message: str) -> None:
        """Handle alert rule triggered — buffer for grouped notification."""
        # Show immediately in status bar (per-rule, no grouping needed here)
        self.statusBar().showMessage(f"⚠️ {message}", 10000)

        # Accumulate for grouped desktop/tray notification
        self._pending_alert_messages.append(message)

        # (Re-)start the 3s quiet timer; flushes when no new alerts arrive
        self._alert_flush_timer.start()

    def _flush_alert_notifications(self) -> None:
        """Send one grouped notification for all buffered alert messages."""
        messages = self._pending_alert_messages
        self._pending_alert_messages = []

        if not messages:
            return

        # Tray notification (first message as title, rest in body for clarity)
        if self.tray_icon:
            if len(messages) == 1:
                self.tray_icon.show_notification("NetScope Alert", messages[0])
            else:
                self.tray_icon.show_notification(
                    f"NetScope: {len(messages)} alerts",
                    "\n".join(f"• {m}" for m in messages)
                )

    def _setup_menu(self) -> None:
        """Setup the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        # Export submenu
        export_menu = file_menu.addMenu("&Export")

        export_bandwidth = export_menu.addAction("Export &Bandwidth Data...")
        export_bandwidth.triggered.connect(self._on_export_bandwidth)

        export_connections = export_menu.addAction("Export &Connections...")
        export_connections.triggered.connect(self._on_export_connections)

        file_menu.addSeparator()

        quit_action = file_menu.addAction("&Quit")
        quit_action.triggered.connect(self.quit_app)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        speed_test_action = tools_menu.addAction("&Speed Test...")
        speed_test_action.triggered.connect(self._on_speed_test)

        # View menu
        view_menu = menubar.addMenu("&View")

        # Theme submenu
        theme_menu = view_menu.addMenu("&Theme")

        # Create theme action group (mutually exclusive)
        from PyQt6.QtGui import QActionGroup
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        # System theme
        system_action = theme_menu.addAction("&System")
        system_action.setCheckable(True)
        system_action.setChecked(True)  # Default
        system_action.setActionGroup(theme_group)
        system_action.triggered.connect(lambda: self._set_theme("system"))

        # Dark theme
        dark_action = theme_menu.addAction("&Dark")
        dark_action.setCheckable(True)
        dark_action.setActionGroup(theme_group)
        dark_action.triggered.connect(lambda: self._set_theme("dark"))

        # Light theme
        light_action = theme_menu.addAction("&Light")
        light_action.setCheckable(True)
        light_action.setActionGroup(theme_group)
        light_action.triggered.connect(lambda: self._set_theme("light"))

        # Store actions for updating check state
        self._theme_actions = {
            "system": system_action,
            "dark": dark_action,
            "light": light_action,
        }

        view_menu.addSeparator()

        # Refresh action
        refresh_action = view_menu.addAction("&Refresh")
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._on_refresh)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._on_about)

    def _set_theme(self, theme_name: str) -> None:
        """Set the application theme."""
        from ..core.theme import Theme, ThemeMode

        mode_map = {
            "system": ThemeMode.SYSTEM,
            "dark": ThemeMode.DARK,
            "light": ThemeMode.LIGHT,
        }

        Theme.set_mode(mode_map[theme_name])

        # Refresh all widgets with new theme
        self._refresh_all_themes()

        # Save preference
        from ..config import load_config, save_config
        config = load_config()
        config["theme"] = theme_name
        save_config(config)

    def _refresh_all_themes(self) -> None:
        """Refresh theme for all widgets."""
        # Refresh main window background
        from ..core.theme import get_palette
        p = get_palette()
        # Qualify with QMainWindow so the rule does NOT cascade to every child widget
        # (unqualified stylesheets override QPalette and Fusion rendering in descendants)
        self.setStyleSheet(f"QMainWindow {{ background-color: {p.bg_primary}; color: {p.text_primary}; }}")

        # Refresh header label
        if hasattr(self, '_header_label'):
            self._header_label.setStyleSheet(f"font-size: 12px; color: {p.text_secondary};")

        # Refresh widgets that have refresh_theme method
        for widget in [
            self.bandwidth_panel,
            self.bandwidth_graph,
            self.process_table,
            self.destinations_panel,
            self.process_bandwidth_table,
            self.historical_graph,
            self.listening_ports,
        ]:
            if widget and hasattr(widget, 'refresh_theme'):
                widget.refresh_theme()

    def _on_system_color_scheme_changed(self) -> None:
        """Handle OS color scheme change (e.g. user toggles dark mode in system settings)."""
        from ..core.theme import Theme, ThemeMode
        if Theme.get_mode() == ThemeMode.SYSTEM:
            Theme.apply_to_qapp()
            self._refresh_all_themes()

    def _on_refresh(self) -> None:
        """Force refresh of all data."""
        # Re-query bandwidth stats
        if hasattr(self, 'bandwidth_worker') and self.bandwidth_worker:
            self.bandwidth_worker.force_refresh()

        # Update status
        self.statusBar().showMessage("Refreshed", 2000)

    def _on_export_bandwidth(self) -> None:
        """Export bandwidth history data."""
        import typing
        from typing import Union

        from ..core.export import (
            export_bandwidth_csv,
            export_bandwidth_json,
            export_daily_totals_csv,
            export_daily_totals_json,
            export_hourly_stats_csv,
            export_hourly_stats_json,
            generate_export_filename,
        )
        from ..core.history import BandwidthSample, DailyTotal, HistoryManager, HourlyStats

        # Ask for format
        menu = QMenu(self)
        csv_action = menu.addAction("CSV Format")
        json_action = menu.addAction("JSON Format")
        menu.addSeparator()
        samples_action = menu.addAction("Raw Samples (last 24h)")
        hourly_action = menu.addAction("Hourly Stats (last 7 days)")
        daily_action = menu.addAction("Daily Totals (last 30 days)")

        action = menu.exec(self.cursor().pos())
        if not action:
            return

        # Determine what to export
        history = HistoryManager()
        data: Union[list[BandwidthSample], list[HourlyStats], list[DailyTotal]] = []
        data_type: str = ""

        if action == samples_action:
            data = history.get_recent_samples(hours=24)
            data_type = "samples"
        elif action == hourly_action:
            data = history.get_hourly_stats(days=7)
            data_type = "hourly"
        elif action == daily_action:
            data = history.get_daily_totals(days=30)
            data_type = "daily"
        elif action == csv_action or action == json_action:
            data = history.get_recent_samples(hours=24)
            data_type = "samples"
        else:
            return

        if not data:
            QMessageBox.information(self, "Export", "No data available to export.")
            return

        # Determine format
        is_csv = action == csv_action or action in [samples_action, hourly_action, daily_action]

        # Get save path
        ext = "csv" if is_csv else "json"
        default_name = generate_export_filename(f"netscope_{data_type}", ext)
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Bandwidth Data",
            default_name,
            f"{ext.upper()} Files (*.{ext})"
        )

        if not filepath:
            return

        filepath_path: Path = Path(filepath)

        try:
            if data_type == "samples":
                samples = typing.cast(list[BandwidthSample], data)
                if is_csv:
                    export_bandwidth_csv(samples, filepath_path)
                else:
                    export_bandwidth_json(samples, filepath_path)
            elif data_type == "hourly":
                hourly = typing.cast(list[HourlyStats], data)
                if is_csv:
                    export_hourly_stats_csv(hourly, filepath_path)
                else:
                    export_hourly_stats_json(hourly, filepath_path)
            elif data_type == "daily":
                daily = typing.cast(list[DailyTotal], data)
                if is_csv:
                    export_daily_totals_csv(daily, filepath_path)
                else:
                    export_daily_totals_json(daily, filepath_path)

            self.statusBar().showMessage(f"Exported to {filepath_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def _on_export_connections(self) -> None:
        """Export current connections."""
        from ..core.connections import ConnectionTracker
        from ..core.export import (
            export_connections_csv,
            export_connections_json,
            generate_export_filename,
        )

        if not self.conn_worker:
            return

        # Get current connections
        tracker = ConnectionTracker()
        connections = tracker.get_connections()

        if not connections:
            QMessageBox.information(self, "Export", "No connections to export.")
            return

        # Ask for format
        menu = QMenu(self)
        csv_action = menu.addAction("CSV Format")
        menu.addAction("JSON Format")

        action = menu.exec(self.cursor().pos())
        if not action:
            return

        is_csv = action == csv_action

        # Get save path
        ext = "csv" if is_csv else "json"
        default_name = generate_export_filename("netscope_connections", ext)
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Connections",
            default_name,
            f"{ext.upper()} Files (*.{ext})"
        )

        if not filepath:
            return

        filepath_path: Path = Path(filepath)

        try:
            if is_csv:
                export_connections_csv(connections, filepath_path)
            else:
                export_connections_json(connections, filepath_path)

            self.statusBar().showMessage(f"Exported to {filepath_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def _on_speed_test(self) -> None:
        """Open speed test dialog."""
        from ..widgets.speed_test_dialog import SpeedTestDialog

        dialog = SpeedTestDialog(self)
        dialog.exec()

    def _on_block_process(self, pid: int, process_name: str) -> None:
        """Block network access for a process."""
        if not self._traffic_blocker.is_available():
            QMessageBox.warning(
                self,
                "Cannot Block Process",
                "Traffic blocking requires sudo access.\n"
                "Please run NetScope with sudo or configure passwordless sudo."
            )
            return

        reply = QMessageBox.question(
            self,
            "Block Process",
            f"Block all network access for:\n\n{process_name} (PID: {pid})\n\n"
            "This will prevent the process from sending or receiving any network data.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, error = self._traffic_blocker.block_process(pid, process_name)
            if success:
                self.statusBar().showMessage(f"Blocked {process_name} (PID: {pid})", 5000)
                # Update table to show blocked status
                blocked_pids = {p.pid for p in self._traffic_blocker.get_blocked_processes()}
                self.process_bandwidth_table.set_blocked_pids(blocked_pids)
            else:
                QMessageBox.critical(self, "Block Failed", f"Failed to block process:\n{error}")

    def _on_unblock_process(self, pid: int, process_name: str) -> None:
        """Unblock network access for a process."""
        success, error = self._traffic_blocker.unblock_process(pid)

        if success:
            self.statusBar().showMessage(f"Unblocked {process_name} (PID: {pid})", 5000)
            # Update table
            blocked_pids = {p.pid for p in self._traffic_blocker.get_blocked_processes()}
            self.process_bandwidth_table.set_blocked_pids(blocked_pids)
        else:
            QMessageBox.critical(self, "Unblock Failed", f"Failed to unblock process:\n{error}")

    def _on_view_process_connections(self, process_name: str) -> None:
        """Switch to Connections tab and filter by process name."""
        self._process_tabs.setCurrentWidget(self.process_table)
        # ProcessTable doesn't have a filter bar, but we highlight via status bar
        self.statusBar().showMessage(f"Showing connections for: {process_name}", 5000)

    def _on_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About NetScope",
            "<h2>NetScope</h2>"
            "<p><b>Version 1.0.0</b></p>"
            "<p>Linux Network Monitor</p>"
            "<hr>"
            "<p>Features:</p>"
            "<ul>"
            "<li>Real-time bandwidth monitoring</li>"
            "<li>LAN/Internet traffic split</li>"
            "<li>Per-process connection tracking</li>"
            "<li>Data cap tracking</li>"
            "<li>Historical data storage</li>"
            "<li>Export to CSV/JSON</li>"
            "</ul>"
            "<hr>"
            "<p><small>Built with PyQt6</small></p>"
        )

    def closeEvent(self, event) -> None:
        """Handle window close - cleanup iptables."""
        # If tray icon exists and we're just hiding, minimize to tray
        if self.tray_icon and not self._force_quit:
            event.ignore()
            self.hide()
            self.tray_icon.update_window_visibility_state()
            return

        # Stop workers
        if self.bw_worker:
            self.bw_worker.stop()
            self.bw_worker.wait(2000)

        if self.conn_worker:
            self.conn_worker.stop()
            self.conn_worker.wait(2000)

        # Teardown iptables
        if self.iptables:
            try:
                self.iptables.teardown()
            except IPTablesError:
                pass

        event.accept()

    def quit_app(self) -> None:
        """Force quit the application (bypass minimize to tray)."""
        self._force_quit = True
        self.close()

    def _on_settings_requested(self) -> None:
        """Handle settings request from tray icon."""
        from ..widgets.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self)
        dialog.settings_saved.connect(self._on_settings_changed)
        dialog.exec()

    def _on_settings_changed(self, config: dict) -> None:
        """Handle settings changes from dialog."""
        # Update data cap display if changed
        if hasattr(self, 'tray_icon') and self.tray_icon:
            from ..core.data_cap import DataCapTracker
            # Re-create tracker with new settings
            self._data_cap_tracker = DataCapTracker(
                enabled=config.get("data_cap_enabled", False),
                monthly_cap_gb=config.get("data_cap_gb", 100.0),
                warn_50=config.get("data_cap_warn_50", True),
                warn_75=config.get("data_cap_warn_75", True),
                warn_90=config.get("data_cap_warn_90", True)
            )
