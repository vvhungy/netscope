"""Speed test dialog for measuring network throughput."""

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..core.speed_test import SpeedTest, SpeedTestResult


class SpeedTestWorker(QThread):
    """Background worker for running speed tests."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(object)  # SpeedTestResult

    def __init__(self, use_cli: bool = True, test_download: bool = True, test_upload: bool = True):
        super().__init__()
        self._use_cli = use_cli
        self._test_download = test_download
        self._test_upload = test_upload
        self._speed_test = SpeedTest()

    def run(self) -> None:
        """Run the speed test."""
        result = self._speed_test.run(
            use_cli=self._use_cli,
            test_download=self._test_download,
            test_upload=self._test_upload,
            progress_callback=self._on_progress
        )
        self.finished.emit(result)

    def _on_progress(self, message: str) -> None:
        """Handle progress update."""
        self.progress.emit(message)

    def stop(self) -> None:
        """Stop the speed test."""
        self._speed_test.stop()
        self.wait(2000)


class SpeedTestDialog(QDialog):
    """Dialog for running network speed tests."""

    # Test method options
    METHOD_AUTO = "auto"
    METHOD_CLI = "cli"
    METHOD_HTTP = "http"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Speed Test")
        self.setMinimumSize(400, 400)
        self.setModal(True)

        self._worker: SpeedTestWorker | None = None
        self._speed_test = SpeedTest()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Network Speed Test")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Test method selection
        method_group = QGroupBox("Test Method")
        method_layout = QHBoxLayout(method_group)

        method_layout.addWidget(QLabel("Method:"))

        self._method_combo = QComboBox()
        self._method_combo.addItem("Auto (CLI with HTTP fallback)", self.METHOD_AUTO)
        self._method_combo.addItem("speedtest-cli only", self.METHOD_CLI)
        self._method_combo.addItem("HTTP test only", self.METHOD_HTTP)
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)
        method_layout.addWidget(self._method_combo)

        method_layout.addStretch()
        layout.addWidget(method_group)

        # Status label
        self._status_label = QLabel("Click 'Start Test' to begin")
        self._status_label.setStyleSheet("color: #888;")
        layout.addWidget(self._status_label)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # Indeterminate
        self._progress.hide()
        layout.addWidget(self._progress)

        # Results group
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)

        # Download result
        dl_layout = QHBoxLayout()
        dl_layout.addWidget(QLabel("Download:"))
        self._download_label = QLabel("-- Mbps")
        self._download_label.setStyleSheet("font-weight: bold; color: #4ade80;")
        dl_layout.addWidget(self._download_label)
        dl_layout.addStretch()
        results_layout.addLayout(dl_layout)

        # Upload result
        ul_layout = QHBoxLayout()
        ul_layout.addWidget(QLabel("Upload:"))
        self._upload_label = QLabel("-- Mbps")
        self._upload_label.setStyleSheet("font-weight: bold; color: #f97316;")
        ul_layout.addWidget(self._upload_label)
        ul_layout.addStretch()
        results_layout.addLayout(ul_layout)

        # Ping result
        ping_layout = QHBoxLayout()
        ping_layout.addWidget(QLabel("Ping:"))
        self._ping_label = QLabel("-- ms")
        self._ping_label.setStyleSheet("font-weight: bold;")
        ping_layout.addWidget(self._ping_label)
        ping_layout.addStretch()
        results_layout.addLayout(ping_layout)

        # Server info
        self._server_label = QLabel("Server: --")
        self._server_label.setStyleSheet("color: #666;")
        results_layout.addWidget(self._server_label)

        layout.addWidget(results_group)

        # Error label
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #ef4444;")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        # Info label
        has_cli = self._speed_test.has_speedtest_cli()
        if has_cli:
            info_text = "<small>✓ speedtest-cli available</small>"
            info_color = "#22c55e"
        else:
            info_text = "<small>✗ speedtest-cli not found (HTTP test only)</small>"
            info_color = "#f97316"
            # Disable CLI options if not available
            self._method_combo.model().item(1).setEnabled(False)

        self._info_label = QLabel(info_text)
        self._info_label.setStyleSheet(f"color: {info_color};")
        layout.addWidget(self._info_label)

        # Buttons
        btn_layout = QHBoxLayout()

        self._start_btn = QPushButton("Start Test")
        self._start_btn.clicked.connect(self._start_test)
        btn_layout.addWidget(self._start_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self._close_btn)

        layout.addLayout(btn_layout)

    def _on_method_changed(self, index: int) -> None:
        """Handle test method selection change."""
        method = self._method_combo.currentData()
        # Update info based on selection
        if method == self.METHOD_CLI and not self._speed_test.has_speedtest_cli():
            self._status_label.setText("speedtest-cli not available")
            self._status_label.setStyleSheet("color: #f97316;")
        else:
            self._status_label.setText("Click 'Start Test' to begin")
            self._status_label.setStyleSheet("color: #888;")

    def _start_test(self) -> None:
        """Start the speed test."""
        method = self._method_combo.currentData()

        # Determine use_cli based on method
        if method == self.METHOD_CLI:
            use_cli = True
        elif method == self.METHOD_HTTP:
            use_cli = False
        else:  # Auto
            use_cli = True  # Will fallback to HTTP if CLI fails

        self._start_btn.setEnabled(False)
        self._progress.show()
        self._error_label.hide()
        self._status_label.setText("Running speed test...")

        # Clear previous results
        self._download_label.setText("-- Mbps")
        self._upload_label.setText("-- Mbps")
        self._ping_label.setText("-- ms")
        self._server_label.setText("Server: --")

        # Create and start worker
        self._worker = SpeedTestWorker(
            use_cli=use_cli,
            test_download=True,
            test_upload=True
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, message: str) -> None:
        """Handle progress update."""
        self._status_label.setText(message)

    def _on_finished(self, result: SpeedTestResult) -> None:
        """Handle speed test completion."""
        self._progress.hide()
        self._start_btn.setEnabled(True)

        if result.error:
            self._error_label.setText(f"Error: {result.error}")
            self._error_label.show()
            self._status_label.setText("Test failed")
        else:
            self._download_label.setText(f"{result.download_mbps:.1f} Mbps")
            self._upload_label.setText(f"{result.upload_mbps:.1f} Mbps")
            self._ping_label.setText(f"{result.ping_ms:.0f} ms")
            self._server_label.setText(f"Server: {result.server}")
            self._status_label.setText("Test complete")

        self._worker = None

    def closeEvent(self, event) -> None:
        """Handle dialog close."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
        super().closeEvent(event)
