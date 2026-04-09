"""Remote destinations summary panel."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PyQt6.QtCore import Qt

from ..core.geoip import GeoIPLookup, get_geoip, country_flag
from ..core.theme import get_color, get_palette, panel_style


class DestinationsPanel(QWidget):
    """Panel showing summary of remote services with country flags."""

    def __init__(self):
        super().__init__()
        self._geoip: GeoIPLookup | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        p = get_palette()

        # Title
        self.title = QLabel("Remote Destinations")
        self.title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        layout.addWidget(self.title)

        # Services container
        self.services_frame = QFrame()
        self.services_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 4px;
            }}
        """)
        self.services_layout = QVBoxLayout(self.services_frame)
        self.services_layout.setSpacing(2)
        self.services_layout.setContentsMargins(8, 4, 8, 4)

        layout.addWidget(self.services_frame)

        # Placeholder
        self.placeholder = QLabel("No internet connections")
        self.placeholder.setStyleSheet(f"color: {p.text_secondary};")
        layout.addWidget(self.placeholder)

    def update_data(self, service_ips: dict[str, list[str]]) -> None:
        """Update with new service data.

        Args:
            service_ips: Dict mapping service name -> list of IPs
        """
        p = get_palette()

        # Clear existing widgets
        while self.services_layout.count():
            item = self.services_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        if not service_ips:
            self.placeholder.show()
            self.services_frame.hide()
            return

        self.placeholder.hide()
        self.services_frame.show()

        # Count total connections (approximate)
        total_services = len(service_ips)
        self.title.setText(f"Remote Destinations ({total_services} services)")

        # Sort by service name, with (other) last
        sorted_services = sorted(
            service_ips.items(),
            key=lambda kv: (kv[0] == "(other)", kv[0])
        )

        for service, ips in sorted_services:
            # Get country flag from first IP
            flag = ""
            if ips:
                country_code, _ = self._lookup_country(ips[0])
                if country_code:
                    flag = country_flag(country_code)

            # Create row widget
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            # Service name with flag
            service_label = QLabel(f"{flag} {service}")
            service_label.setStyleSheet(f"font-family: monospace; color: {p.text_primary};")
            row_layout.addWidget(service_label)

            row_layout.addStretch()

            # IPs with count
            ips_text = f"({len(ips)} IPs)"
            ips_label = QLabel(ips_text)
            ips_label.setStyleSheet(f"font-family: monospace; color: {p.text_secondary};")
            row_layout.addWidget(ips_label)

            self.services_layout.addWidget(row)

    def _lookup_country(self, ip: str) -> tuple[str | None, str | None]:
        """Lookup country for an IP address.

        Args:
            ip: IP address string

        Returns:
            Tuple of (country_code, country_name) or (None, None)
        """
        if self._geoip is None:
            self._geoip = get_geoip()

        try:
            return self._geoip.lookup_country(ip)
        except Exception:
            return None, None

    def refresh_theme(self) -> None:
        """Refresh colors for theme change."""
        p = get_palette()
        self.title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {p.text_primary};")
        self.services_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 4px;
            }}
        """)
        self.placeholder.setStyleSheet(f"color: {p.text_secondary};")
