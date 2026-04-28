"""Application configuration and constants."""

import json
from pathlib import Path

# Default configuration
DEFAULT_CONFIG = {
    "interface": "auto",          # auto-detect primary interface
    "lan_subnet": "192.168.0.0/20",
    "update_interval": 1.0,       # seconds between bandwidth samples
    "connection_interval": 2.0,   # seconds between connection scans
    "start_minimized": False,
    "show_lan_traffic": True,
    # Data cap settings
    "data_cap_enabled": False,
    "data_cap_gb": 100.0,         # 100 GB default
    "data_cap_warn_50": True,
    "data_cap_warn_75": True,
    "data_cap_warn_90": True,
    "data_cap_reset_day": 1,       # day of month (1–31) when cap resets
}

# IPTables chain name
IPTABLES_CHAIN = "NETSCOPE"

# Rule tags for counter identification
RULE_TAGS = {
    "lan_rx": "netscope-lan-rx",
    "lan_tx": "netscope-lan-tx",
    "inet_rx": "netscope-inet-rx",
    "inet_tx": "netscope-inet-tx",
}

# Config file location
CONFIG_DIR = Path.home() / ".config" / "netscope"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    """Load configuration from file, creating default if missing."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
                # Merge with defaults for any missing keys
                return {**DEFAULT_CONFIG, **cfg}
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
