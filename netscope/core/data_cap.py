"""Data cap tracking and alerting."""

from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
import json
from typing import Optional


@dataclass
class DataCapStatus:
    """Current status of data cap tracking."""
    enabled: bool
    monthly_cap_gb: float
    used_gb: float
    remaining_gb: float
    percent_used: float
    days_remaining: int
    projected_usage_gb: float  # based on current rate
    will_exceed: bool
    warning_level: str  # "none", "50%", "75%", "90%", "100%"


class DataCapTracker:
    """Tracks monthly data usage against a cap with persistence."""

    USAGE_FILE = Path.home() / ".config" / "netscope" / "usage.json"

    def __init__(
        self,
        monthly_cap_gb: float = 100.0,
        enabled: bool = False,
        warn_50: bool = True,
        warn_75: bool = True,
        warn_90: bool = True,
    ):
        self.monthly_cap_gb = monthly_cap_gb
        self.enabled = enabled
        self.warn_50 = warn_50
        self.warn_75 = warn_75
        self.warn_90 = warn_90

        # Usage tracking
        self._current_month: str = self._get_current_month()
        self._total_rx: int = 0  # persisted RX bytes
        self._total_tx: int = 0  # persisted TX bytes
        self._session_rx: int = 0  # session RX bytes from iptables
        self._session_tx: int = 0  # session TX bytes from iptables
        self._last_updated: Optional[str] = None

        # Rate tracking for projection
        self._start_time: Optional[datetime] = None
        self._start_rx: int = 0
        self._start_tx: int = 0

        # Warning tracking (to avoid repeated warnings)
        self._last_warning_level: str = "none"

        # Load persisted data
        self._load()

    def _get_current_month(self) -> str:
        """Get current month string in YYYY-MM format."""
        return datetime.now().strftime("%Y-%m")

    def _days_remaining_in_month(self) -> int:
        """Calculate days remaining in current month."""
        today = date.today()
        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)
        return (next_month - today).days

    def _load(self) -> None:
        """Load persisted usage data from file."""
        if self.USAGE_FILE.exists():
            try:
                with open(self.USAGE_FILE) as f:
                    data = json.load(f)

                stored_month = data.get("month", "")
                if stored_month == self._current_month:
                    # Same month, load persisted totals
                    self._total_rx = data.get("total_rx", 0)
                    self._total_tx = data.get("total_tx", 0)
                    self._last_updated = data.get("last_updated")
                else:
                    # Month changed, reset totals (old month data discarded)
                    self._total_rx = 0
                    self._total_tx = 0
                    self._last_updated = None
            except (json.JSONDecodeError, OSError, KeyError):
                # Invalid file, start fresh
                self._total_rx = 0
                self._total_tx = 0
                self._last_updated = None

    def _save(self) -> None:
        """Persist usage data to file."""
        self.USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Include session totals in persisted totals
        total_rx = self._total_rx + self._session_rx
        total_tx = self._total_tx + self._session_tx

        data = {
            "month": self._current_month,
            "total_rx": total_rx,
            "total_tx": total_tx,
            "last_updated": datetime.now().isoformat(),
        }

        try:
            with open(self.USAGE_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass  # Silently fail if can't write

    def update_session_usage(self, rx_total: int, tx_total: int) -> None:
        """Update session usage from iptables counters.

        Args:
            rx_total: Total RX bytes from iptables (session total)
            tx_total: Total TX bytes from iptables (session total)
        """
        # Check if month changed
        current_month = self._get_current_month()
        if current_month != self._current_month:
            # Month changed, persist old data and reset
            self._save()
            self._current_month = current_month
            self._total_rx = 0
            self._total_tx = 0
            self._session_rx = 0
            self._session_tx = 0
            self._start_time = None
            self._last_warning_level = "none"

        # Track session usage
        self._session_rx = rx_total
        self._session_tx = tx_total

        # Track for rate projection
        if self._start_time is None:
            self._start_time = datetime.now()
            self._start_rx = rx_total
            self._start_tx = tx_total

        # Persist periodically
        self._save()

    def get_status(self) -> DataCapStatus:
        """Get current data cap status."""
        if not self.enabled:
            return DataCapStatus(
                enabled=False,
                monthly_cap_gb=self.monthly_cap_gb,
                used_gb=0.0,
                remaining_gb=self.monthly_cap_gb,
                percent_used=0.0,
                days_remaining=self._days_remaining_in_month(),
                projected_usage_gb=0.0,
                will_exceed=False,
                warning_level="none",
            )

        # Calculate total usage (persisted + session)
        total_bytes = self._total_rx + self._total_tx + self._session_rx + self._session_tx
        total_gb = total_bytes / (1024 ** 3)

        # Calculate remaining
        remaining_gb = max(0.0, self.monthly_cap_gb - total_gb)
        percent_used = min(100.0, (total_gb / self.monthly_cap_gb) * 100) if self.monthly_cap_gb > 0 else 100.0

        # Calculate projected usage based on rate
        days_remaining = self._days_remaining_in_month()
        projected_gb = total_gb

        if self._start_time and days_remaining > 0:
            elapsed = (datetime.now() - self._start_time).total_seconds()
            if elapsed > 60:  # Need at least 1 minute of data
                session_bytes = (self._session_rx + self._session_tx) - (self._start_rx + self._start_tx)
                rate_per_second = session_bytes / elapsed
                seconds_remaining = days_remaining * 24 * 3600
                projected_additional = (rate_per_second * seconds_remaining) / (1024 ** 3)
                projected_gb = total_gb + projected_additional

        will_exceed = projected_gb > self.monthly_cap_gb

        # Determine warning level
        warning_level = "none"
        if percent_used >= 100:
            warning_level = "100%"
        elif percent_used >= 90 and self.warn_90:
            warning_level = "90%"
        elif percent_used >= 75 and self.warn_75:
            warning_level = "75%"
        elif percent_used >= 50 and self.warn_50:
            warning_level = "50%"

        return DataCapStatus(
            enabled=True,
            monthly_cap_gb=self.monthly_cap_gb,
            used_gb=total_gb,
            remaining_gb=remaining_gb,
            percent_used=percent_used,
            days_remaining=days_remaining,
            projected_usage_gb=projected_gb,
            will_exceed=will_exceed,
            warning_level=warning_level,
        )

    def set_cap(self, cap_gb: float) -> None:
        """Set the monthly data cap in GB."""
        self.monthly_cap_gb = max(0.0, cap_gb)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable data cap tracking."""
        self.enabled = enabled

    def set_warnings(self, warn_50: bool, warn_75: bool, warn_90: bool) -> None:
        """Configure warning thresholds."""
        self.warn_50 = warn_50
        self.warn_75 = warn_75
        self.warn_90 = warn_90

    def reset_month(self) -> None:
        """Reset current month's usage (for manual reset)."""
        self._total_rx = 0
        self._total_tx = 0
        self._session_rx = 0
        self._session_tx = 0
        self._start_time = None
        self._last_warning_level = "none"
        self._save()

    def get_new_warning(self, status: DataCapStatus) -> Optional[str]:
        """Check if there's a new warning to show.

        Returns warning message if warning level increased, None otherwise.
        """
        if status.warning_level == "none":
            self._last_warning_level = "none"
            return None

        # Check if warning level increased
        levels = ["none", "50%", "75%", "90%", "100%"]
        current_idx = levels.index(status.warning_level)
        last_idx = levels.index(self._last_warning_level)

        if current_idx > last_idx:
            self._last_warning_level = status.warning_level
            return self._format_warning(status)

        return None

    def _format_warning(self, status: DataCapStatus) -> str:
        """Format a warning message for display."""
        if status.warning_level == "100%":
            return f"Data cap exceeded! Used {status.used_gb:.1f} GB of {status.monthly_cap_gb:.0f} GB."
        elif status.warning_level == "90%":
            return f"Data cap warning: {status.percent_used:.0f}% used ({status.used_gb:.1f} GB of {status.monthly_cap_gb:.0f} GB)."
        elif status.warning_level == "75%":
            return f"Data cap at {status.percent_used:.0f}% ({status.used_gb:.1f} GB of {status.monthly_cap_gb:.0f} GB)."
        elif status.warning_level == "50%":
            return f"Data cap at {status.percent_used:.0f}% ({status.used_gb:.1f} GB of {status.monthly_cap_gb:.0f} GB)."
        return ""
