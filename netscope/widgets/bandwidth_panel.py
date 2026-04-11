"""Bandwidth display panel with progress bars."""


from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ..core.bandwidth import BandwidthStats
from ..core.data_cap import DataCapStatus
from ..core.theme import get_color, get_palette
from ..core.utils import format_bytes, format_rate


class SpeedBar(QWidget):
    """A single speed indicator with label, bar, and rate display."""

    def __init__(self, label: str, color_key: str = "download"):
        super().__init__()
        self._color_key = color_key
        self._setup_ui(label)

    def _setup_ui(self, label: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        p = get_palette()

        # Direction label
        self.label = QLabel(label)
        self.label.setFixedWidth(50)
        self.label.setStyleSheet(f"font-weight: bold; color: {p.text_primary};")

        # Progress bar
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)  # Use 0-1000 for finer granularity
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(16)
        self._update_bar_style()

        # Rate label
        self.rate_label = QLabel("0 B/s")
        self.rate_label.setFixedWidth(100)
        self.rate_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.rate_label.setStyleSheet(f"color: {p.text_primary};")

        # Total label
        self.total_label = QLabel("total: 0 B")
        self.total_label.setStyleSheet(f"color: {p.text_secondary};")

        layout.addWidget(self.label)
        layout.addWidget(self.bar, 1)
        layout.addWidget(self.rate_label)
        layout.addWidget(self.total_label)

    def _update_bar_style(self) -> None:
        """Update bar style with current theme color."""
        color = get_color(self._color_key)
        p = get_palette()
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {p.border};
                border-radius: 3px;
                background-color: {p.bg_tertiary};
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)

    def update_speed(self, rate: float, total: int, max_rate: float) -> None:
        """Update display with new rate and total."""
        self.rate_label.setText(format_rate(rate))
        self.total_label.setText(f"total: {format_bytes(total)}")

        # Scale bar to max rate (or 1KB minimum)
        scale = max(max_rate, 1024)
        value = int(1000 * min(rate / scale, 1.0))
        self.bar.setValue(value)

    def refresh_theme(self) -> None:
        """Refresh colors for theme change."""
        self._update_bar_style()
        p = get_palette()
        self.label.setStyleSheet(f"font-weight: bold; color: {p.text_primary};")
        self.rate_label.setStyleSheet(f"color: {p.text_primary};")
        self.total_label.setStyleSheet(f"color: {p.text_secondary};")


class BandwidthPanel(QWidget):
    """Panel displaying LAN and Internet bandwidth with progress bars."""

    def __init__(self):
        super().__init__()
        self._max_rate = 1024 * 100  # 100 KB initial scale
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        p = get_palette()

        # Title
        title = QLabel("Bandwidth")
        title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        layout.addWidget(title)

        # LAN section
        lan_frame = QFrame()
        lan_frame.setFrameShape(QFrame.Shape.StyledPanel)
        lan_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 6px;
            }}
        """)
        lan_layout = QVBoxLayout(lan_frame)
        lan_layout.setSpacing(4)

        lan_label = QLabel("LAN")
        lan_label.setStyleSheet(f"color: {get_color('lan')}; font-weight: bold;")
        lan_layout.addWidget(lan_label)

        self.lan_rx = SpeedBar("▼ RX", "lan")
        self.lan_tx = SpeedBar("▲ TX", "lan")
        lan_layout.addWidget(self.lan_rx)
        lan_layout.addWidget(self.lan_tx)

        layout.addWidget(lan_frame)

        # Internet section
        inet_frame = QFrame()
        inet_frame.setFrameShape(QFrame.Shape.StyledPanel)
        inet_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 6px;
            }}
        """)
        inet_layout = QVBoxLayout(inet_frame)
        inet_layout.setSpacing(4)

        inet_label = QLabel("INTERNET")
        inet_label.setStyleSheet(f"color: {get_color('internet')}; font-weight: bold;")
        inet_layout.addWidget(inet_label)

        self.inet_rx = SpeedBar("▼ RX", "internet")
        self.inet_tx = SpeedBar("▲ TX", "internet")
        inet_layout.addWidget(self.inet_rx)
        inet_layout.addWidget(self.inet_tx)

        layout.addWidget(inet_frame)

        # VPN section (initially hidden)
        self.vpn_frame = QFrame()
        self.vpn_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.vpn_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 6px;
            }}
        """)
        vpn_layout = QVBoxLayout(self.vpn_frame)
        vpn_layout.setSpacing(4)

        self._vpn_label = QLabel("VPN")
        self._vpn_label.setStyleSheet(f"color: {get_color('vpn')}; font-weight: bold;")
        vpn_layout.addWidget(self._vpn_label)

        self.vpn_rx = SpeedBar("▼ RX", "vpn")
        self.vpn_tx = SpeedBar("▲ TX", "vpn")
        vpn_layout.addWidget(self.vpn_rx)
        vpn_layout.addWidget(self.vpn_tx)

        self.vpn_frame.hide()
        layout.addWidget(self.vpn_frame)

        # Summary row
        summary_layout = QHBoxLayout()
        self.rx_summary = QLabel("RX: —")
        self.tx_summary = QLabel("TX: —")
        self.rx_summary.setStyleSheet(f"color: {p.text_primary};")
        self.tx_summary.setStyleSheet(f"color: {p.text_primary};")
        summary_layout.addWidget(self.rx_summary)
        summary_layout.addStretch()
        summary_layout.addWidget(self.tx_summary)
        layout.addLayout(summary_layout)

        # Data cap section (initially hidden)
        self.data_cap_frame = QFrame()
        self.data_cap_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.data_cap_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 6px;
            }}
        """)
        data_cap_layout = QVBoxLayout(self.data_cap_frame)
        data_cap_layout.setSpacing(4)

        # Data cap header
        data_cap_header = QHBoxLayout()
        self.data_cap_label = QLabel("DATA CAP")
        self.data_cap_label.setStyleSheet(f"color: {get_color('warning')}; font-weight: bold;")
        data_cap_header.addWidget(self.data_cap_label)

        self.data_cap_days = QLabel("")
        self.data_cap_days.setStyleSheet(f"color: {p.text_secondary};")
        self.data_cap_days.setAlignment(Qt.AlignmentFlag.AlignRight)
        data_cap_header.addWidget(self.data_cap_days)
        data_cap_layout.addLayout(data_cap_header)

        # Data cap progress bar
        self.data_cap_bar = QProgressBar()
        self.data_cap_bar.setRange(0, 1000)  # 0-1000 for finer granularity
        self.data_cap_bar.setValue(0)
        self.data_cap_bar.setTextVisible(False)
        self.data_cap_bar.setFixedHeight(16)
        self._update_data_cap_bar_style(get_color("success"))
        data_cap_layout.addWidget(self.data_cap_bar)

        # Data cap info row
        data_cap_info = QHBoxLayout()
        self.data_cap_usage = QLabel("0 GB / 100 GB (0%)")
        self.data_cap_usage.setStyleSheet(f"color: {p.text_primary};")
        data_cap_info.addWidget(self.data_cap_usage)
        data_cap_info.addStretch()
        self.data_cap_projected = QLabel("")
        self.data_cap_projected.setStyleSheet(f"color: {p.text_secondary};")
        data_cap_info.addWidget(self.data_cap_projected)
        data_cap_layout.addLayout(data_cap_info)

        # Initially hidden
        self.data_cap_frame.hide()
        layout.addWidget(self.data_cap_frame)

        # Store frames for theme refresh
        self._lan_frame = lan_frame
        self._inet_frame = inet_frame

    def _update_data_cap_bar_style(self, color: str) -> None:
        """Update data cap progress bar style with given color."""
        p = get_palette()
        self.data_cap_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {p.border};
                border-radius: 3px;
                background-color: {p.bg_tertiary};
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)

    def update_stats(self, stats: BandwidthStats) -> None:
        """Update all displays from BandwidthStats."""
        # Update max rate for scaling
        self._max_rate = max(
            stats.lan_rx_rate, stats.lan_tx_rate,
            stats.inet_rx_rate, stats.inet_tx_rate,
            self._max_rate * 0.99,  # Slow decay
            1024  # Minimum 1 KB/s scale
        )

        # Update bars
        self.lan_rx.update_speed(stats.lan_rx_rate, stats.lan_rx_total, self._max_rate)
        self.lan_tx.update_speed(stats.lan_tx_rate, stats.lan_tx_total, self._max_rate)
        self.inet_rx.update_speed(stats.inet_rx_rate, stats.inet_rx_total, self._max_rate)
        self.inet_tx.update_speed(stats.inet_tx_rate, stats.inet_tx_total, self._max_rate)

        # VPN section — show only when interfaces detected
        if stats.vpn_interfaces:
            self.vpn_frame.show()
            ifaces = ", ".join(stats.vpn_interfaces)
            self._vpn_label.setText(f"VPN ({ifaces})")
            self.vpn_rx.update_speed(stats.vpn_rx_rate, stats.vpn_rx_total, self._max_rate)
            self.vpn_tx.update_speed(stats.vpn_tx_rate, stats.vpn_tx_total, self._max_rate)
        else:
            self.vpn_frame.hide()

        # Update summary
        total_rx = stats.total_rx_rate
        total_tx = stats.total_tx_rate
        inet_rx_pct = stats.inet_rx_percent()
        inet_tx_pct = stats.inet_tx_percent()

        self.rx_summary.setText(
            f"RX: {format_rate(total_rx)} ({inet_rx_pct:.0f}% internet)"
        )
        self.tx_summary.setText(
            f"TX: {format_rate(total_tx)} ({inet_tx_pct:.0f}% internet)"
        )

    def update_data_cap(self, status: DataCapStatus) -> None:
        """Update data cap display with current status."""
        if not status.enabled:
            self.data_cap_frame.hide()
            return

        self.data_cap_frame.show()
        p = get_palette()

        # Update days remaining
        if status.days_remaining == 1:
            self.data_cap_days.setText("1 day remaining")
        else:
            self.data_cap_days.setText(f"{status.days_remaining} days remaining")

        # Update progress bar (0-1000 range)
        value = int(min(1000, status.percent_used * 10))
        self.data_cap_bar.setValue(value)

        # Determine color based on percent used
        if status.percent_used >= 90:
            color = get_color("error")
        elif status.percent_used >= 75:
            color = get_color("warning")
        elif status.percent_used >= 50:
            color = get_color("warning")
        else:
            color = get_color("success")

        self._update_data_cap_bar_style(color)

        # Update usage text
        self.data_cap_usage.setText(
            f"{status.used_gb:.1f} GB / {status.monthly_cap_gb:.0f} GB ({status.percent_used:.0f}%)"
        )

        # Update projected usage warning
        if status.will_exceed:
            self.data_cap_projected.setText(
                f"Projected: {status.projected_usage_gb:.1f} GB (will exceed!)"
            )
            self.data_cap_projected.setStyleSheet(f"color: {get_color('error')}; font-weight: bold;")
        elif status.projected_usage_gb > status.monthly_cap_gb * 0.9:
            self.data_cap_projected.setText(
                f"Projected: {status.projected_usage_gb:.1f} GB"
            )
            self.data_cap_projected.setStyleSheet(f"color: {get_color('warning')};")
        else:
            self.data_cap_projected.setText(
                f"Projected: {status.projected_usage_gb:.1f} GB"
            )
            self.data_cap_projected.setStyleSheet(f"color: {p.text_secondary};")

    def refresh_theme(self) -> None:
        """Refresh all colors for theme change."""
        p = get_palette()

        # Refresh speed bars
        self.lan_rx.refresh_theme()
        self.lan_tx.refresh_theme()
        self.inet_rx.refresh_theme()
        self.inet_tx.refresh_theme()

        # Refresh frames
        self._lan_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 6px;
            }}
        """)
        self._inet_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 6px;
            }}
        """)
        self.data_cap_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 6px;
            }}
        """)
        self.vpn_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 6px;
            }}
        """)
        self._vpn_label.setStyleSheet(f"color: {get_color('vpn')}; font-weight: bold;")
        self.vpn_rx.refresh_theme()
        self.vpn_tx.refresh_theme()

        # Refresh labels not updated elsewhere
        self.rx_summary.setStyleSheet(f"color: {p.text_primary};")
        self.tx_summary.setStyleSheet(f"color: {p.text_primary};")
        self.data_cap_label.setStyleSheet(f"color: {get_color('warning')}; font-weight: bold;")
        self.data_cap_days.setStyleSheet(f"color: {p.text_secondary};")
        self.data_cap_usage.setStyleSheet(f"color: {p.text_primary};")
        self._update_data_cap_bar_style(get_color("success"))
