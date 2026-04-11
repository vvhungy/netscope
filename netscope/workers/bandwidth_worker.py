"""Background worker for bandwidth monitoring."""

import time

from PyQt6.QtCore import QThread, pyqtSignal

from ..core.bandwidth import BandwidthCalculator, BandwidthStats
from ..core.iptables import IPTablesManager


def _read_proc_net_dev() -> dict[str, dict[str, int]]:
    """Parse /proc/net/dev into {iface: {rx_bytes, tx_bytes, ...}}."""
    ifaces: dict[str, dict[str, int]] = {}
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if ":" not in line:
                    continue
                name, rest = line.split(":", 1)
                name = name.strip()
                parts = rest.split()
                if len(parts) >= 10:
                    ifaces[name] = {
                        "rx_bytes": int(parts[0]),
                        "tx_bytes": int(parts[8]),
                    }
    except OSError:
        pass
    return ifaces


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
        self._prev_vpn: dict[str, int] | None = None
        self._prev_vpn_time: float | None = None
        self._vpn_totals: dict[str, int] = {}

    def _compute_vpn_stats(self, stats: BandwidthStats, now: float) -> None:
        """Read /proc/net/dev for tun*/wg* and fill VPN fields on stats."""
        current = _read_proc_net_dev()
        vpn_names = sorted(
            n for n in current
            if n.startswith(("tun", "wg"))
        )
        stats.vpn_interfaces = vpn_names

        if not vpn_names:
            self._prev_vpn = None
            self._prev_vpn_time = None
            return

        # Sum current bytes across VPN interfaces
        cur_rx = sum(current[n]["rx_bytes"] for n in vpn_names)
        cur_tx = sum(current[n]["tx_bytes"] for n in vpn_names)

        if self._prev_vpn is not None and self._prev_vpn_time is not None:
            dt = now - self._prev_vpn_time
            if dt > 0:
                d_rx = max(cur_rx - self._prev_vpn.get("rx_bytes", cur_rx), 0)
                d_tx = max(cur_tx - self._prev_vpn.get("tx_bytes", cur_tx), 0)
                self._vpn_totals["rx"] = self._vpn_totals.get("rx", 0) + d_rx
                self._vpn_totals["tx"] = self._vpn_totals.get("tx", 0) + d_tx
                stats.vpn_rx_rate = d_rx / dt
                stats.vpn_tx_rate = d_tx / dt

        stats.vpn_rx_total = self._vpn_totals.get("rx", 0)
        stats.vpn_tx_total = self._vpn_totals.get("tx", 0)

        self._prev_vpn = {"rx_bytes": cur_rx, "tx_bytes": cur_tx}
        self._prev_vpn_time = now

    def run(self) -> None:
        """Main worker loop."""
        self._running = True
        self.calculator.reset()

        while self._running:
            try:
                counters = self.iptables.read_counters()
                stats = self.calculator.update(counters)
                self._compute_vpn_stats(stats, time.monotonic())
                self.stats_ready.emit(stats)
            except Exception as e:
                self.error_occurred.emit(str(e))

            time.sleep(self.interval)

    def stop(self) -> None:
        """Request the worker to stop."""
        self._running = False
