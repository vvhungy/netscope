"""Utility functions for NetScope."""



def format_bytes(b: float) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def format_rate(bps: float) -> str:
    """Format bytes/sec as human-readable rate string."""
    return format_bytes(bps) + "/s"


