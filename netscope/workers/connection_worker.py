"""Background worker for connection tracking."""

import time

from PyQt6.QtCore import QThread, pyqtSignal

from ..core.connections import ConnectionTracker


class ConnectionWorker(QThread):
    """Thread that polls /proc for TCP connections."""

    connections_ready = pyqtSignal(list)  # list[Connection]
    summary_ready = pyqtSignal(dict, dict)  # process_connections, service_ips
    error_occurred = pyqtSignal(str)

    def __init__(self, interval: float = 2.0):
        super().__init__()
        self.interval = interval
        self.tracker = ConnectionTracker()
        self._running = False

    def run(self) -> None:
        """Main worker loop."""
        self._running = True

        while self._running:
            try:
                conns = self.tracker.get_connections()
                self.connections_ready.emit(conns)

                proc_conns, service_ips = self.tracker.get_summary()
                self.summary_ready.emit(proc_conns, service_ips)
            except Exception as e:
                self.error_occurred.emit(str(e))

            time.sleep(self.interval)

    def stop(self) -> None:
        """Request the worker to stop."""
        self._running = False
