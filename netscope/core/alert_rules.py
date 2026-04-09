"""Custom alert rules for bandwidth thresholds."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from .notifications import get_notification_manager


class AlertType(Enum):
    """Type of alert threshold."""
    RATE_THRESHOLD = "rate"         # bytes/sec threshold
    VOLUME_THRESHOLD = "volume"     # bytes in time period
    DATA_CAP_PERCENT = "cap_percent"  # percentage of data cap


class AlertDirection(Enum):
    """Direction of traffic to monitor."""
    DOWNLOAD = "download"
    UPLOAD = "upload"
    BOTH = "both"


@dataclass
class AlertRule:
    """A single alert rule configuration."""
    id: str
    name: str
    enabled: bool = True
    alert_type: AlertType = AlertType.RATE_THRESHOLD
    direction: AlertDirection = AlertDirection.BOTH
    threshold: float = 0.0  # bytes/sec or bytes or percentage
    period_minutes: int = 60  # For volume thresholds, the time period
    cooldown_minutes: int = 30  # Minimum time between alerts
    notify_desktop: bool = True
    notify_tray: bool = True

    # Runtime state
    _last_triggered: datetime = field(default_factory=lambda: datetime.min, repr=False)
    _period_start: datetime = field(default_factory=lambda: datetime.now(), repr=False)
    _period_bytes: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "alert_type": self.alert_type.value,
            "direction": self.direction.value,
            "threshold": self.threshold,
            "period_minutes": self.period_minutes,
            "cooldown_minutes": self.cooldown_minutes,
            "notify_desktop": self.notify_desktop,
            "notify_tray": self.notify_tray,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AlertRule":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            enabled=data.get("enabled", True),
            alert_type=AlertType(data.get("alert_type", "rate")),
            direction=AlertDirection(data.get("direction", "both")),
            threshold=data.get("threshold", 0.0),
            period_minutes=data.get("period_minutes", 60),
            cooldown_minutes=data.get("cooldown_minutes", 30),
            notify_desktop=data.get("notify_desktop", True),
            notify_tray=data.get("notify_tray", True),
        )


class AlertRulesManager:
    """Manages custom alert rules and triggers notifications."""

    CONFIG_FILE = Path.home() / ".config" / "netscope" / "alert_rules.json"

    def __init__(self):
        self._rules: list[AlertRule] = []
        self._on_alert_callback: Optional[Callable[[AlertRule, str], None]] = None
        self._load_rules()

    def _load_rules(self) -> None:
        """Load rules from config file."""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE) as f:
                    data = json.load(f)
                    self._rules = [AlertRule.from_dict(r) for r in data.get("rules", [])]
            except (json.JSONDecodeError, OSError, KeyError):
                self._rules = []
        else:
            # Create default rules
            self._rules = [
                AlertRule(
                    id="high-download-rate",
                    name="High Download Rate",
                    alert_type=AlertType.RATE_THRESHOLD,
                    direction=AlertDirection.DOWNLOAD,
                    threshold=50 * 1024 * 1024,  # 50 MB/s
                    enabled=False,
                ),
                AlertRule(
                    id="high-upload-rate",
                    name="High Upload Rate",
                    alert_type=AlertType.RATE_THRESHOLD,
                    direction=AlertDirection.UPLOAD,
                    threshold=20 * 1024 * 1024,  # 20 MB/s
                    enabled=False,
                ),
                AlertRule(
                    id="hourly-volume",
                    name="Hourly Volume Alert",
                    alert_type=AlertType.VOLUME_THRESHOLD,
                    direction=AlertDirection.BOTH,
                    threshold=500 * 1024 * 1024,  # 500 MB
                    period_minutes=60,
                    enabled=False,
                ),
            ]
            self._save_rules()

    def _save_rules(self) -> None:
        """Save rules to config file."""
        self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, "w") as f:
            json.dump({
                "rules": [r.to_dict() for r in self._rules]
            }, f, indent=2)

    def get_rules(self) -> list[AlertRule]:
        """Get all alert rules."""
        return self._rules.copy()

    def add_rule(self, rule: AlertRule) -> None:
        """Add a new alert rule."""
        self._rules.append(rule)
        self._save_rules()

    def update_rule(self, rule: AlertRule) -> None:
        """Update an existing rule."""
        for i, r in enumerate(self._rules):
            if r.id == rule.id:
                self._rules[i] = rule
                self._save_rules()
                return

    def remove_rule(self, rule_id: str) -> None:
        """Remove a rule by ID."""
        self._rules = [r for r in self._rules if r.id != rule_id]
        self._save_rules()

    def set_on_alert(self, callback: Callable[[AlertRule, str], None]) -> None:
        """Set callback for when an alert is triggered."""
        self._on_alert_callback = callback

    def check_rate_alerts(
        self,
        rx_rate: float,
        tx_rate: float,
        data_cap_percent: float = 0.0
    ) -> list[tuple[AlertRule, str]]:
        """Check all rate-based alerts against current rates.

        Args:
            rx_rate: Current download rate in bytes/sec
            tx_rate: Current upload rate in bytes/sec
            data_cap_percent: Current data cap usage percentage

        Returns:
            List of (rule, message) tuples for triggered alerts
        """
        now = datetime.now()
        triggered = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            # Check cooldown
            if now - rule._last_triggered < timedelta(minutes=rule.cooldown_minutes):
                continue

            should_trigger = False
            message = ""

            if rule.alert_type == AlertType.RATE_THRESHOLD:
                # Get relevant rate
                if rule.direction == AlertDirection.DOWNLOAD:
                    rate = rx_rate
                    dir_name = "Download"
                elif rule.direction == AlertDirection.UPLOAD:
                    rate = tx_rate
                    dir_name = "Upload"
                else:
                    rate = rx_rate + tx_rate
                    dir_name = "Total"

                if rate >= rule.threshold:
                    should_trigger = True
                    message = f"{rule.name}: {dir_name} rate {self._format_rate(rate)} exceeds {self._format_rate(rule.threshold)}"

            elif rule.alert_type == AlertType.DATA_CAP_PERCENT:
                if data_cap_percent >= rule.threshold:
                    should_trigger = True
                    message = f"{rule.name}: Data cap usage at {data_cap_percent:.1f}% (threshold: {rule.threshold}%)"

            if should_trigger:
                rule._last_triggered = now
                triggered.append((rule, message))

                # Send notifications
                if rule.notify_desktop:
                    try:
                        nm = get_notification_manager()
                        if nm.is_available():
                            nm.notify("NetScope Alert", message)
                    except Exception:
                        pass

                if self._on_alert_callback:
                    self._on_alert_callback(rule, message)

        return triggered

    def update_volume_tracking(
        self,
        rx_bytes: int,
        tx_bytes: int
    ) -> list[tuple[AlertRule, str]]:
        """Update volume tracking and check volume-based alerts.

        Call this periodically (e.g., every second) with cumulative byte counts.

        Args:
            rx_bytes: Cumulative download bytes since boot
            tx_bytes: Cumulative upload bytes since boot

        Returns:
            List of (rule, message) tuples for triggered alerts
        """
        now = datetime.now()
        triggered = []

        for rule in self._rules:
            if not rule.enabled or rule.alert_type != AlertType.VOLUME_THRESHOLD:
                continue

            # Check cooldown
            if now - rule._last_triggered < timedelta(minutes=rule.cooldown_minutes):
                continue

            # Check if period has elapsed
            if now - rule._period_start >= timedelta(minutes=rule.period_minutes):
                # Calculate volume for the period
                if rule.direction == AlertDirection.DOWNLOAD:
                    volume = rule._period_bytes
                    dir_name = "Download"
                elif rule.direction == AlertDirection.UPLOAD:
                    volume = rule._period_bytes
                    dir_name = "Upload"
                else:
                    volume = rule._period_bytes
                    dir_name = "Total"

                if volume >= rule.threshold:
                    message = f"{rule.name}: {dir_name} volume {self._format_bytes(volume)} exceeds {self._format_bytes(rule.threshold)} in {rule.period_minutes} minutes"
                    rule._last_triggered = now
                    triggered.append((rule, message))

                    # Send notifications
                    if rule.notify_desktop:
                        try:
                            nm = get_notification_manager()
                            if nm.is_available():
                                nm.notify("NetScope Alert", message)
                        except Exception:
                            pass

                    if self._on_alert_callback:
                        self._on_alert_callback(rule, message)

                # Reset period
                rule._period_start = now
                rule._period_bytes = 0.0

        return triggered

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

    def _format_bytes(self, bytes_val: float) -> str:
        """Format bytes as human readable."""
        if bytes_val < 1024:
            return f"{bytes_val:.0f} B"
        elif bytes_val < 1024 ** 2:
            return f"{bytes_val/1024:.1f} KB"
        elif bytes_val < 1024 ** 3:
            return f"{bytes_val/1024**2:.1f} MB"
        else:
            return f"{bytes_val/1024**3:.1f} GB"


# Global instance
_alert_manager: AlertRulesManager | None = None


def get_alert_manager() -> AlertRulesManager:
    """Get the global alert rules manager."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertRulesManager()
    return _alert_manager
