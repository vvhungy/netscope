"""Bandwidth rate calculation and statistics."""

import time
from dataclasses import dataclass


@dataclass
class BandwidthStats:
    """Current bandwidth statistics."""
    lan_rx_rate: float = 0.0    # bytes/sec
    lan_tx_rate: float = 0.0
    inet_rx_rate: float = 0.0
    inet_tx_rate: float = 0.0
    lan_rx_total: int = 0       # bytes this session
    lan_tx_total: int = 0
    inet_rx_total: int = 0
    inet_tx_total: int = 0

    # VPN interface stats
    vpn_interfaces: list[str] = ()  # type: ignore[assignment]  # active tun*/wg* names
    vpn_rx_rate: float = 0.0
    vpn_tx_rate: float = 0.0
    vpn_rx_total: int = 0
    vpn_tx_total: int = 0

    @property
    def total_rx_rate(self) -> float:
        return self.lan_rx_rate + self.inet_rx_rate

    @property
    def total_tx_rate(self) -> float:
        return self.lan_tx_rate + self.inet_tx_rate

    @property
    def total_rx(self) -> int:
        return self.lan_rx_total + self.inet_rx_total

    @property
    def total_tx(self) -> int:
        return self.lan_tx_total + self.inet_tx_total

    def inet_rx_percent(self) -> float:
        total = self.total_rx_rate
        return (100 * self.inet_rx_rate / total) if total > 0 else 0.0

    def inet_tx_percent(self) -> float:
        total = self.total_tx_rate
        return (100 * self.inet_tx_rate / total) if total > 0 else 0.0


class BandwidthCalculator:
    """Tracks counters and computes rates."""

    def __init__(self):
        self._prev_counters: dict[str, int] | None = None
        self._prev_time: float | None = None
        self._totals: dict[str, int] = {}

    def update(self, counters: dict[str, int], current_time: float | None = None) -> BandwidthStats:
        """Update with new counter readings and return stats."""
        if current_time is None:
            current_time = time.monotonic()

        stats = BandwidthStats()

        if self._prev_counters is not None and self._prev_time is not None:
            dt = current_time - self._prev_time
            if dt > 0:
                # Compute rates from delta
                for key in counters:
                    delta = counters[key] - self._prev_counters.get(key, counters[key])
                    if delta < 0:
                        delta = 0  # counter reset
                    self._totals[key] = self._totals.get(key, 0) + delta

                    rate = delta / dt
                    if key == "lan_rx":
                        stats.lan_rx_rate = rate
                    elif key == "lan_tx":
                        stats.lan_tx_rate = rate
                    elif key == "inet_rx":
                        stats.inet_rx_rate = rate
                    elif key == "inet_tx":
                        stats.inet_tx_rate = rate

        # Set totals
        stats.lan_rx_total = self._totals.get("lan_rx", 0)
        stats.lan_tx_total = self._totals.get("lan_tx", 0)
        stats.inet_rx_total = self._totals.get("inet_rx", 0)
        stats.inet_tx_total = self._totals.get("inet_tx", 0)

        self._prev_counters = counters.copy()
        self._prev_time = current_time

        return stats

    def reset(self) -> None:
        """Reset all tracking state."""
        self._prev_counters = None
        self._prev_time = None
        self._totals = {}
