"""Export utilities for bandwidth and connection data."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .history import HistoryManager, BandwidthSample, HourlyStats, DailyTotal
from .connections import Connection, ListeningPort


def export_bandwidth_csv(samples: list[BandwidthSample], filepath: Path) -> None:
    """Export bandwidth samples to CSV."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'lan_rx', 'lan_tx', 'inet_rx', 'inet_tx'])
        for s in samples:
            writer.writerow([
                s.timestamp.isoformat(),
                s.lan_rx,
                s.lan_tx,
                s.inet_rx,
                s.inet_tx
            ])


def export_bandwidth_json(samples: list[BandwidthSample], filepath: Path) -> None:
    """Export bandwidth samples to JSON."""
    data = [
        {
            'timestamp': s.timestamp.isoformat(),
            'lan_rx': s.lan_rx,
            'lan_tx': s.lan_tx,
            'inet_rx': s.inet_rx,
            'inet_tx': s.inet_tx
        }
        for s in samples
    ]
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def export_hourly_stats_csv(stats: list[HourlyStats], filepath: Path) -> None:
    """Export hourly statistics to CSV."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['hour', 'lan_rx_total', 'lan_tx_total', 'inet_rx_total', 'inet_tx_total', 'sample_count'])
        for s in stats:
            writer.writerow([
                s.hour.isoformat(),
                s.lan_rx_total,
                s.lan_tx_total,
                s.inet_rx_total,
                s.inet_tx_total,
                s.connection_count
            ])


def export_hourly_stats_json(stats: list[HourlyStats], filepath: Path) -> None:
    """Export hourly statistics to JSON."""
    data = [
        {
            'hour': s.hour.isoformat(),
            'lan_rx_total': s.lan_rx_total,
            'lan_tx_total': s.lan_tx_total,
            'inet_rx_total': s.inet_rx_total,
            'inet_tx_total': s.inet_tx_total,
            'connection_count': s.connection_count
        }
        for s in stats
    ]
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def export_daily_totals_csv(totals: list[DailyTotal], filepath: Path) -> None:
    """Export daily totals to CSV."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'lan_rx_total', 'lan_tx_total', 'inet_rx_total', 'inet_tx_total'])
        for t in totals:
            writer.writerow([
                t.date.isoformat(),
                t.lan_rx_total,
                t.lan_tx_total,
                t.inet_rx_total,
                t.inet_tx_total
            ])


def export_daily_totals_json(totals: list[DailyTotal], filepath: Path) -> None:
    """Export daily totals to JSON."""
    data = [
        {
            'date': t.date.isoformat(),
            'lan_rx_total': t.lan_rx_total,
            'lan_tx_total': t.lan_tx_total,
            'inet_rx_total': t.inet_rx_total,
            'inet_tx_total': t.inet_tx_total
        }
        for t in totals
    ]
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def export_connections_csv(connections: list[Connection], filepath: Path) -> None:
    """Export connections to CSV."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'protocol', 'local_addr', 'local_port',
            'remote_addr', 'remote_port', 'state',
            'pid', 'process_name', 'service'
        ])
        for c in connections:
            writer.writerow([
                c.protocol,
                c.local_port,
                c.remote_ip,
                c.remote_port,
                c.is_ipv6,
                c.is_private,
                c.pid or '',
                c.process_name or '',
                c.service or ''
            ])


def export_connections_json(connections: list[Connection], filepath: Path) -> None:
    """Export connections to JSON."""
    data = [
        {
            'protocol': c.protocol,
            'local_port': c.local_port,
            'remote_ip': c.remote_ip,
            'remote_port': c.remote_port,
            'is_ipv6': c.is_ipv6,
            'is_private': c.is_private,
            'pid': c.pid,
            'process_name': c.process_name,
            'service': c.service
        }
        for c in connections
    ]
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def export_listening_ports_csv(ports: list[ListeningPort], filepath: Path) -> None:
    """Export listening ports to CSV."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['protocol', 'address', 'port', 'pid', 'process_name'])
        for p in ports:
            writer.writerow([
                p.protocol,
                p.address,
                p.port,
                p.pid or '',
                p.process_name or ''
            ])


def export_listening_ports_json(ports: list[ListeningPort], filepath: Path) -> None:
    """Export listening ports to JSON."""
    data = [
        {
            'protocol': p.protocol,
            'address': p.address,
            'port': p.port,
            'pid': p.pid,
            'process_name': p.process_name
        }
        for p in ports
    ]
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def generate_export_filename(prefix: str, format: str) -> str:
    """Generate a timestamped filename for export."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ext = 'csv' if format == 'csv' else 'json'
    return f"{prefix}_{timestamp}.{ext}"
