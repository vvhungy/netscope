# NetScope

[![CI](https://github.com/youruser/netscope/actions/workflows/ci.yml/badge.svg)](https://github.com/youruser/netscope/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/youruser/netscope/branch/main/graph/badge.svg)](https://codecov.io/gh/youruser/netscope)
[![PyPI version](https://img.shields.io/pypi/v/netscope)](https://pypi.org/project/netscope/)

A real-time Linux network bandwidth monitor with a PyQt6 GUI.

## Features

- **Per-process bandwidth** — live upload/download rates per process
- **Connection tracking** — TCP/UDP connections with remote service identification
- **Destinations panel** — remote hosts and countries (GeoIP)
- **Historical graphs** — bandwidth over time, stored in SQLite
- **Data cap tracking** — monthly cap with warnings and usage projection
- **Custom alert rules** — user-defined thresholds with desktop notifications
- **Traffic blocking** — right-click a process to block its network access via iptables
- **Speed test** — integrated network speed test
- **Dark / light / system theme** — follows your desktop or set manually
- **System tray** — live tray icon with bandwidth rates
- **CSV / JSON export** — export connection history or bandwidth logs

## Requirements

- Linux (uses iptables, `/proc`, `ss`)
- Python 3.11+
- PyQt6
- Root privileges (for iptables chain management)

## Installation

```bash
pip install netscope
```

Or from source:

```bash
git clone https://github.com/youruser/netscope.git
cd netscope
pip install .
```

## Usage

```bash
sudo netscope
```

NetScope requires root to manage iptables chains. If run without root, it will prompt for a sudo password.

## Development

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Type check
mypy netscope

# Tests
pytest
```

## License

GPL v3 — see [LICENSE](LICENSE).
