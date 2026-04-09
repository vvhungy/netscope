"""Background worker for bandwidth monitoring."""

import time

from PyQt6.QtCore import QThread, pyqtSignal

from ..core.bandwidth import BandwidthCalculator
from ..core.iptables import IPTablesManager


class BandwidthWorker(QThread):
    """Thread that polls iptables counters and emits bandwidth stats."""

    stats_ready = pyqtSignal(object)  # BandwidthStats
    error_occurred = pyqtSignal(str)  # error message

    def __init__(self, iptables: IPTablesManager, interval: float = 1.0):
        super().__init__()
        self.iptables = iptables
        self.interval = interval
        self.calculator = BandwidthCalculator()
        self._running = False

    def run(self) -> None:
        """Main worker loop."""
        self._running = True
        self.calculator.reset()

        while self._running:
            try:
                counters = self.iptables.read_counters()
                stats = self.calculator.update(counters)
                self.stats_ready.emit(stats)
            except Exception as e:
                self.error_occurred.emit(str(e))

            time.sleep(self.interval)

    def stop(self) -> None:
        """Request the worker to stop."""
        self._running = False
