"""Desktop notifications for NetScope."""

import subprocess
import shutil
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class NotificationConfig:
    """Notification preferences."""
    enabled: bool = True
    data_cap_50: bool = False
    data_cap_75: bool = True
    data_cap_90: bool = True
    high_bandwidth: bool = False
    high_bandwidth_threshold_mbps: float = 100.0
    new_process: bool = False


class NotificationManager:
    """Manages desktop notifications."""

    def __init__(self, app_name: str = "NetScope"):
        self.app_name = app_name
        self._notify_send = shutil.which("notify-send")
        self._last_notification: dict[str, float] = {}
        self._throttle_seconds = 300  # 5 minutes

    def is_available(self) -> bool:
        """Check if notifications are available."""
        return self._notify_send is not None

    def _can_send(self, notification_type: str) -> bool:
        """Check if we can send this notification type (throttling)."""
        now = time.time()
        last_sent = self._last_notification.get(notification_type, 0)

        if now - last_sent < self._throttle_seconds:
            return False

        self._last_notification[notification_type] = now
        return True

    def notify(
        self,
        title: str,
        message: str,
        urgency: str = "normal",
        icon: Optional[str] = None,
        timeout: int = 5000
    ) -> bool:
        """
        Send a desktop notification.

        Args:
            title: Notification title
            message: Notification body
            urgency: "low", "normal", or "critical"
            icon: Icon name or path
            timeout: Timeout in milliseconds

        Returns:
            True if notification was sent successfully
        """
        if not self._notify_send:
            return False

        try:
            cmd = [
                self._notify_send,
                "-a", self.app_name,
                "-u", urgency,
                "-t", str(timeout),
            ]

            if icon:
                cmd.extend(["-i", icon])

            cmd.extend([title, message])

            subprocess.run(cmd, capture_output=True, check=False)
            return True
        except Exception:
            return False

    def notify_data_cap(
        self,
        percent: float,
        remaining_gb: float,
        warning_level: str
    ) -> bool:
        """
        Send data cap warning notification.

        Args:
            percent: Percentage of cap used
            remaining_gb: Remaining GB
            warning_level: "50%", "75%", "90%", "100%"
        """
        if not self._can_send(f"data_cap_{warning_level}"):
            return False

        urgency = "critical" if percent >= 100 else (
            "normal" if percent >= 75 else "low"
        )

        if percent >= 100:
            title = "Data Cap Exceeded!"
            message = f"You have exceeded your monthly data cap."
        else:
            title = f"Data Cap Warning: {percent:.0f}%"
            message = f"{remaining_gb:.1f} GB remaining this month."

        return self.notify(title, message, urgency=urgency, icon="network-error")

    def notify_high_bandwidth(
        self,
        rate_mbps: float,
        process: Optional[str] = None
    ) -> bool:
        """
        Send high bandwidth usage notification.

        Args:
            rate_mbps: Current bandwidth in Mbps
            process: Process name causing high usage (optional)
        """
        if not self._can_send("high_bandwidth"):
            return False

        title = "High Bandwidth Usage"
        if process:
            message = f"{process} is using {rate_mbps:.1f} Mbps"
        else:
            message = f"Current usage: {rate_mbps:.1f} Mbps"

        return self.notify(title, message, urgency="normal", icon="network-transmit")

    def notify_new_process(
        self,
        process_name: str,
        connection_count: int
    ) -> bool:
        """
        Send notification about new process using network.

        Args:
            process_name: Name of the new process
            connection_count: Number of connections
        """
        if not self._can_send(f"new_process_{process_name}"):
            return False

        title = "New Network Activity"
        message = f"{process_name} started using the network ({connection_count} connections)"

        return self.notify(title, message, urgency="low", icon="network-wired")

    def notify_startup(self) -> bool:
        """Send startup notification."""
        return self.notify(
            "NetScope Started",
            "Network monitoring is active",
            urgency="low",
            icon="network-monitor"
        )

    def notify_shutdown(self) -> bool:
        """Send shutdown notification."""
        return self.notify(
            "NetScope Stopped",
            "Network monitoring has stopped",
            urgency="low",
            icon="network-offline"
        )


# Global instance
_notification_manager: NotificationManager | None = None


def get_notification_manager() -> NotificationManager:
    """Get the global notification manager instance."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
