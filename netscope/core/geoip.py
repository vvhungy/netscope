"""GeoIP country lookup for IP addresses."""

import socket
import struct
from pathlib import Path

# Try to import geoip2 for MaxMind database support
try:
    import geoip2.database
    import geoip2.errors
    HAS_GEOIP2 = True
except ImportError:
    HAS_GEOIP2 = False

# Country code to emoji flag conversion
def country_flag(code: str) -> str:
    """Convert country code to emoji flag (e.g., 'US' -> '🇺🇸')."""
    if not code or len(code) != 2:
        return ""
    # Convert country code to regional indicator symbols
    # A = 🇦 (U+1F1E6), B = 🇧 (U+1F1E7), etc.
    base = 0x1F1E6 - ord('A')
    return chr(ord(code[0]) + base) + chr(ord(code[1]) + base)

# Embedded fallback database for common IP ranges
# Maps IP prefixes to (country_code, country_name)
_EMBEDDED_GEOIP = {
    # Google
    "142.250.": ("US", "United States"),
    "142.251.": ("US", "United States"),
    "64.233.": ("US", "United States"),
    "66.102.": ("US", "United States"),
    "66.249.": ("US", "United States"),
    "72.14.": ("US", "United States"),
    "74.125.": ("US", "United States"),
    "108.177.": ("US", "United States"),
    "209.85.": ("US", "United States"),
    "216.58.": ("US", "United States"),
    "216.239.": ("US", "United States"),

    # Google Cloud
    "35.190.": ("US", "United States"),
    "35.191.": ("US", "United States"),
    "34.64.": ("US", "United States"),
    "34.65.": ("US", "United States"),
    "34.66.": ("US", "United States"),
    "34.67.": ("US", "United States"),

    # Cloudflare
    "104.16.": ("US", "United States"),
    "104.17.": ("US", "United States"),
    "104.18.": ("US", "United States"),
    "104.19.": ("US", "United States"),
    "104.20.": ("US", "United States"),
    "104.21.": ("US", "United States"),
    "104.22.": ("US", "United States"),
    "104.23.": ("US", "United States"),
    "104.24.": ("US", "United States"),
    "104.25.": ("US", "United States"),
    "104.26.": ("US", "United States"),
    "104.27.": ("US", "United States"),
    "172.64.": ("US", "United States"),
    "172.65.": ("US", "United States"),
    "172.66.": ("US", "United States"),
    "172.67.": ("US", "United States"),
    "172.68.": ("US", "United States"),
    "172.69.": ("US", "United States"),
    "172.70.": ("US", "United States"),
    "172.71.": ("US", "United States"),
    "162.158.": ("US", "United States"),
    "162.159.": ("US", "United States"),
    "162.160.": ("US", "United States"),
    "1.1.": ("US", "United States"),
    "1.0.": ("US", "United States"),

    # GitHub
    "140.82.": ("US", "United States"),
    "192.30.": ("US", "United States"),
    "185.199.": ("US", "United States"),

    # AWS
    "52.0.": ("US", "United States"),
    "52.1.": ("US", "United States"),
    "52.2.": ("US", "United States"),
    "52.3.": ("US", "United States"),
    "52.4.": ("US", "United States"),
    "52.5.": ("US", "United States"),
    "52.6.": ("US", "United States"),
    "52.7.": ("US", "United States"),
    "52.8.": ("US", "United States"),
    "52.9.": ("US", "United States"),
    "52.10.": ("US", "United States"),
    "52.11.": ("US", "United States"),
    "52.12.": ("US", "United States"),
    "52.13.": ("US", "United States"),
    "52.14.": ("US", "United States"),
    "52.15.": ("US", "United States"),
    "54.0.": ("US", "United States"),
    "54.1.": ("US", "United States"),
    "54.2.": ("US", "United States"),
    "54.3.": ("US", "United States"),
    "13.0.": ("US", "United States"),
    "13.1.": ("US", "United States"),
    "13.2.": ("US", "United States"),
    "13.3.": ("US", "United States"),
    "13.4.": ("US", "United States"),
    "3.0.": ("US", "United States"),
    "3.1.": ("US", "United States"),
    "3.2.": ("US", "United States"),
    "3.3.": ("US", "United States"),
    "18.0.": ("US", "United States"),
    "18.1.": ("US", "United States"),
    "18.2.": ("US", "United States"),
    "18.3.": ("US", "United States"),

    # Azure
    "40.64.": ("US", "United States"),
    "40.65.": ("US", "United States"),
    "40.66.": ("US", "United States"),
    "40.67.": ("US", "United States"),
    "40.68.": ("US", "United States"),
    "20.0.": ("US", "United States"),
    "20.1.": ("US", "United States"),
    "20.2.": ("US", "United States"),
    "51.0.": ("US", "United States"),
    "51.1.": ("US", "United States"),
    "51.2.": ("US", "United States"),
    "65.52.": ("US", "United States"),

    # Apple
    "17.0.": ("US", "United States"),
    "17.1.": ("US", "United States"),
    "17.2.": ("US", "United States"),
    "17.3.": ("US", "United States"),
    "17.4.": ("US", "United States"),
    "17.5.": ("US", "United States"),
    "17.6.": ("US", "United States"),
    "17.7.": ("US", "United States"),
    "17.8.": ("US", "United States"),
    "17.9.": ("US", "United States"),
    "17.10.": ("US", "United States"),
    "17.11.": ("US", "United States"),
    "17.12.": ("US", "United States"),
    "17.13.": ("US", "United States"),
    "17.14.": ("US", "United States"),
    "17.15.": ("US", "United States"),
    "17.16.": ("US", "United States"),
    "17.17.": ("US", "United States"),
    "17.18.": ("US", "United States"),
    "17.19.": ("US", "United States"),
    "17.20.": ("US", "United States"),
    "17.21.": ("US", "United States"),
    "17.22.": ("US", "United States"),
    "17.23.": ("US", "United States"),
    "17.24.": ("US", "United States"),
    "17.25.": ("US", "United States"),
    "17.30.": ("US", "United States"),
    "17.31.": ("US", "United States"),
    "17.32.": ("US", "United States"),
    "17.33.": ("US", "United States"),
    "17.34.": ("US", "United States"),
    "17.35.": ("US", "United States"),
    "17.36.": ("US", "United States"),
    "17.37.": ("US", "United States"),
    "17.38.": ("US", "United States"),
    "17.39.": ("US", "United States"),
    "17.40.": ("US", "United States"),
    "17.41.": ("US", "United States"),
    "17.42.": ("US", "United States"),
    "17.43.": ("US", "United States"),
    "17.44.": ("US", "United States"),
    "17.45.": ("US", "United States"),
    "17.46.": ("US", "United States"),
    "17.47.": ("US", "United States"),
    "17.48.": ("US", "United States"),
    "17.49.": ("US", "United States"),
    "17.50.": ("US", "United States"),
    "17.51.": ("US", "United States"),
    "17.52.": ("US", "United States"),
    "17.53.": ("US", "United States"),
    "17.54.": ("US", "United States"),
    "17.55.": ("US", "United States"),
    "17.56.": ("US", "United States"),
    "17.57.": ("US", "United States"),
    "17.58.": ("US", "United States"),
    "17.59.": ("US", "United States"),
    "17.60.": ("US", "United States"),
    "17.61.": ("US", "United States"),
    "17.62.": ("US", "United States"),
    "17.63.": ("US", "United States"),
    "17.64.": ("US", "United States"),
    "17.65.": ("US", "United States"),
    "17.66.": ("US", "United States"),
    "17.67.": ("US", "United States"),
    "17.68.": ("US", "United States"),
    "17.69.": ("US", "United States"),
    "17.70.": ("US", "United States"),
    "17.71.": ("US", "United States"),
    "17.72.": ("US", "United States"),
    "17.73.": ("US", "United States"),
    "17.74.": ("US", "United States"),
    "17.75.": ("US", "United States"),
    "17.76.": ("US", "United States"),
    "17.77.": ("US", "United States"),
    "17.78.": ("US", "United States"),
    "17.79.": ("US", "United States"),
    "17.80.": ("US", "United States"),
    "17.81.": ("US", "United States"),
    "17.82.": ("US", "United States"),
    "17.83.": ("US", "United States"),
    "17.84.": ("US", "United States"),
    "17.85.": ("US", "United States"),
    "17.86.": ("US", "United States"),
    "17.87.": ("US", "United States"),
    "17.88.": ("US", "United States"),
    "17.89.": ("US", "United States"),
    "17.90.": ("US", "United States"),
    "17.91.": ("US", "United States"),
    "17.92.": ("US", "United States"),
    "17.93.": ("US", "United States"),
    "17.94.": ("US", "United States"),
    "17.95.": ("US", "United States"),
    "17.96.": ("US", "United States"),
    "17.97.": ("US", "United States"),
    "17.98.": ("US", "United States"),
    "17.99.": ("US", "United States"),
    "17.100.": ("US", "United States"),
    "17.101.": ("US", "United States"),
    "17.102.": ("US", "United States"),
    "17.103.": ("US", "United States"),
    "17.104.": ("US", "United States"),
    "17.105.": ("US", "United States"),
    "17.106.": ("US", "United States"),
    "17.107.": ("US", "United States"),
    "17.108.": ("US", "United States"),
    "17.109.": ("US", "United States"),
    "17.110.": ("US", "United States"),
    "17.111.": ("US", "United States"),
    "17.112.": ("US", "United States"),
    "17.113.": ("US", "United States"),
    "17.114.": ("US", "United States"),
    "17.115.": ("US", "United States"),
    "17.116.": ("US", "United States"),
    "17.117.": ("US", "United States"),
    "17.118.": ("US", "United States"),
    "17.119.": ("US", "United States"),
    "17.120.": ("US", "United States"),
    "17.121.": ("US", "United States"),
    "17.122.": ("US", "United States"),
    "17.123.": ("US", "United States"),
    "17.124.": ("US", "United States"),
    "17.125.": ("US", "United States"),
    "17.126.": ("US", "United States"),
    "17.127.": ("US", "United States"),
    "17.128.": ("US", "United States"),
    "17.129.": ("US", "United States"),
    "17.130.": ("US", "United States"),
    "17.131.": ("US", "United States"),
    "17.132.": ("US", "United States"),
    "17.133.": ("US", "United States"),
    "17.134.": ("US", "United States"),
    "17.135.": ("US", "United States"),
    "17.136.": ("US", "United States"),
    "17.137.": ("US", "United States"),
    "17.138.": ("US", "United States"),
    "17.139.": ("US", "United States"),
    "17.140.": ("US", "United States"),
    "17.141.": ("US", "United States"),
    "17.142.": ("US", "United States"),
    "17.143.": ("US", "United States"),
    "17.144.": ("US", "United States"),
    "17.145.": ("US", "United States"),
    "17.146.": ("US", "United States"),
    "17.147.": ("US", "United States"),
    "17.148.": ("US", "United States"),
    "17.149.": ("US", "United States"),
    "17.150.": ("US", "United States"),
    "17.151.": ("US", "United States"),
    "17.152.": ("US", "United States"),
    "17.153.": ("US", "United States"),
    "17.154.": ("US", "United States"),
    "17.155.": ("US", "United States"),
    "17.156.": ("US", "United States"),
    "17.157.": ("US", "United States"),
    "17.158.": ("US", "United States"),
    "17.159.": ("US", "United States"),
    "17.160.": ("US", "United States"),
    "17.161.": ("US", "United States"),
    "17.162.": ("US", "United States"),
    "17.163.": ("US", "United States"),
    "17.164.": ("US", "United States"),
    "17.165.": ("US", "United States"),
    "17.166.": ("US", "United States"),
    "17.167.": ("US", "United States"),
    "17.168.": ("US", "United States"),
    "17.169.": ("US", "United States"),
    "17.170.": ("US", "United States"),
    "17.171.": ("US", "United States"),
    "17.172.": ("US", "United States"),
    "17.173.": ("US", "United States"),
    "17.174.": ("US", "United States"),
    "17.175.": ("US", "United States"),
    "17.176.": ("US", "United States"),
    "17.177.": ("US", "United States"),
    "17.178.": ("US", "United States"),
    "17.179.": ("US", "United States"),
    "17.180.": ("US", "United States"),
    "17.181.": ("US", "United States"),
    "17.182.": ("US", "United States"),
    "17.183.": ("US", "United States"),
    "17.184.": ("US", "United States"),
    "17.185.": ("US", "United States"),
    "17.186.": ("US", "United States"),
    "17.187.": ("US", "United States"),
    "17.188.": ("US", "United States"),
    "17.189.": ("US", "United States"),
    "17.190.": ("US", "United States"),
    "17.191.": ("US", "United States"),

    # Telegram
    "149.154.": ("AE", "United Arab Emirates"),
    "91.108.": ("GB", "United Kingdom"),
    "91.105.": ("GB", "United Kingdom"),

    # Meta/Facebook
    "157.240.": ("US", "United States"),
    "31.13.": ("US", "United States"),
    "66.220.": ("US", "United States"),

    # Dropbox
    "162.125.": ("US", "United States"),

    # Fastly
    "151.101.": ("US", "United States"),
    "199.232.": ("US", "United States"),

    # Akamai
    "23.0.": ("US", "United States"),
    "23.1.": ("US", "United States"),
    "23.2.": ("US", "United States"),
    "23.3.": ("US", "United States"),
    "23.4.": ("US", "United States"),
    "23.5.": ("US", "United States"),
    "23.6.": ("US", "United States"),
    "23.7.": ("US", "United States"),
    "23.8.": ("US", "United States"),
    "23.9.": ("US", "United States"),
    "23.10.": ("US", "United States"),
    "23.11.": ("US", "United States"),
    "23.12.": ("US", "United States"),
    "23.13.": ("US", "United States"),
    "23.14.": ("US", "United States"),
    "23.15.": ("US", "United States"),
    "23.16.": ("US", "United States"),
    "23.17.": ("US", "United States"),
    "23.18.": ("US", "United States"),
    "23.19.": ("US", "United States"),
    "23.20.": ("US", "United States"),
    "23.21.": ("US", "United States"),
    "23.22.": ("US", "United States"),
    "23.23.": ("US", "United States"),
    "23.24.": ("US", "United States"),
    "23.25.": ("US", "United States"),
    "23.26.": ("US", "United States"),
    "23.27.": ("US", "United States"),
    "23.28.": ("US", "United States"),
    "23.29.": ("US", "United States"),
    "23.30.": ("US", "United States"),
    "23.31.": ("US", "United States"),
    "23.32.": ("US", "United States"),
    "23.33.": ("US", "United States"),
    "23.34.": ("US", "United States"),
    "23.35.": ("US", "United States"),
    "23.36.": ("US", "United States"),
    "23.37.": ("US", "United States"),
    "23.38.": ("US", "United States"),
    "23.39.": ("US", "United States"),
    "23.40.": ("US", "United States"),
    "23.41.": ("US", "United States"),
    "23.42.": ("US", "United States"),
    "23.43.": ("US", "United States"),
    "23.44.": ("US", "United States"),
    "23.45.": ("US", "United States"),
    "23.46.": ("US", "United States"),
    "23.47.": ("US", "United States"),
    "23.48.": ("US", "United States"),
    "23.49.": ("US", "United States"),
    "23.50.": ("US", "United States"),
    "23.51.": ("US", "United States"),
    "23.52.": ("US", "United States"),
    "23.53.": ("US", "United States"),
    "23.54.": ("US", "United States"),
    "23.55.": ("US", "United States"),
    "23.56.": ("US", "United States"),
    "23.57.": ("US", "United States"),
    "23.58.": ("US", "United States"),
    "23.59.": ("US", "United States"),
    "23.60.": ("US", "United States"),
    "23.61.": ("US", "United States"),
    "23.62.": ("US", "United States"),
    "23.63.": ("US", "United States"),
    "23.64.": ("US", "United States"),
    "23.65.": ("US", "United States"),
    "23.66.": ("US", "United States"),
    "23.67.": ("US", "United States"),
    "23.68.": ("US", "United States"),
    "23.69.": ("US", "United States"),
    "23.70.": ("US", "United States"),
    "23.71.": ("US", "United States"),
    "23.72.": ("US", "United States"),
    "23.73.": ("US", "United States"),
    "23.74.": ("US", "United States"),
    "23.75.": ("US", "United States"),
    "23.76.": ("US", "United States"),
    "23.77.": ("US", "United States"),
    "23.78.": ("US", "United States"),
    "23.79.": ("US", "United States"),
    "23.80.": ("US", "United States"),
    "23.81.": ("US", "United States"),
    "23.82.": ("US", "United States"),
    "23.83.": ("US", "United States"),
    "23.84.": ("US", "United States"),
    "23.85.": ("US", "United States"),
    "23.86.": ("US", "United States"),
    "23.87.": ("US", "United States"),
    "23.88.": ("US", "United States"),
    "23.89.": ("US", "United States"),
    "23.90.": ("US", "United States"),
    "23.91.": ("US", "United States"),
    "23.92.": ("US", "United States"),
    "23.93.": ("US", "United States"),
    "23.94.": ("US", "United States"),
    "23.95.": ("US", "United States"),
    "23.96.": ("US", "United States"),
    "23.97.": ("US", "United States"),
    "23.98.": ("US", "United States"),
    "23.99.": ("US", "United States"),
    "95.100.": ("US", "United States"),

    # Microsoft
    "13.107.": ("US", "United States"),
    "40.126.": ("US", "United States"),
    "52.96.": ("US", "United States"),

    # Netflix
    "23.246.": ("US", "United States"),
    "37.77.": ("US", "United States"),
    "45.57.": ("US", "United States"),

    # Spotify
    "35.186.": ("SE", "Sweden"),
    "104.199.": ("SE", "Sweden"),

    # Discord
    "188.114.": ("US", "United States"),

    # Slack
    "54.191.": ("US", "United States"),
    "34.211.": ("US", "United States"),
    "52.72.": ("US", "United States"),
}


class GeoIPLookup:
    """GeoIP lookup with MaxMind database support and embedded fallback."""

    def __init__(self):
        self._reader = None
        self._db_paths = [
            Path("/usr/share/GeoIP/GeoLite2-Country.mmdb"),
            Path("/var/lib/GeoIP/GeoLite2-Country.mmdb"),
            Path.home() / ".local/share/GeoIP/GeoLite2-Country.mmdb",
            Path.home() / ".config/netscope/GeoLite2-Country.mmdb",
        ]

        if HAS_GEOIP2:
            for path in self._db_paths:
                if path.exists():
                    try:
                        self._reader = geoip2.database.Reader(str(path))
                        break
                    except Exception:
                        pass

    def lookup_country(self, ip: str) -> tuple[str | None, str | None]:
        """
        Look up country for an IP address.

        Returns:
            (country_code, country_name) or (None, None) if unknown
        """
        # Skip private IPs
        if self._is_private(ip):
            return None, None

        # Try MaxMind database first
        if self._reader:
            try:
                result = self._reader.country(ip)
                return result.country.iso_code, result.country.name
            except Exception:
                pass

        # Fall back to embedded database
        for prefix, (code, name) in _EMBEDDED_GEOIP.items():
            if ip.startswith(prefix):
                return code, name

        return None, None

    def _is_private(self, ip: str) -> bool:
        """Check if IP is private/local."""
        try:
            n = struct.unpack("!I", socket.inet_aton(ip))[0]
            private_masks = [
                (0x0A000000, 0xFF000000),   # 10.0.0.0/8
                (0xAC100000, 0xFFF00000),   # 172.16.0.0/12
                (0xC0A80000, 0xFFFF0000),   # 192.168.0.0/16
                (0x7F000000, 0xFF000000),   # 127.0.0.0/8
            ]
            return any((n & mask) == (base & mask) for base, mask in private_masks)
        except OSError:
            # IPv6
            return ip.startswith("fe80") or ip == "::1"

    def close(self):
        """Close the database reader."""
        if self._reader:
            self._reader.close()
            self._reader = None


# Global instance
_geoip_lookup: GeoIPLookup | None = None


def get_geoip() -> GeoIPLookup:
    """Get the global GeoIP lookup instance."""
    global _geoip_lookup
    if _geoip_lookup is None:
        _geoip_lookup = GeoIPLookup()
    return _geoip_lookup


def lookup_country(ip: str) -> tuple[str | None, str | None]:
    """Convenience function to look up country for an IP."""
    return get_geoip().lookup_country(ip)
