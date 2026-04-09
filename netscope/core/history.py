"""Historical data storage using SQLite."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
from collections import defaultdict

# Database location
DATA_DIR = Path.home() / ".local" / "share" / "netscope"
DB_PATH = DATA_DIR / "history.db"


@dataclass
class BandwidthSample:
    """A single bandwidth sample."""
    timestamp: datetime
    lan_rx: int
    lan_tx: int
    inet_rx: int
    inet_tx: int


@dataclass
class HourlyStats:
    """Aggregated hourly statistics."""
    hour: datetime
    lan_rx_total: int
    lan_tx_total: int
    inet_rx_total: int
    inet_tx_total: int
    connection_count: int


@dataclass
class DailyTotal:
    """Aggregated daily totals."""
    date: date
    lan_rx_total: int
    lan_tx_total: int
    inet_rx_total: int
    inet_tx_total: int
    peak_rx_rate: int
    peak_tx_rate: int


class HistoryManager:
    """Manages historical bandwidth data storage."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript("""
            -- Bandwidth samples (keep 7 days of raw data)
            CREATE TABLE IF NOT EXISTS bandwidth_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                lan_rx INTEGER NOT NULL DEFAULT 0,
                lan_tx INTEGER NOT NULL DEFAULT 0,
                inet_rx INTEGER NOT NULL DEFAULT 0,
                inet_tx INTEGER NOT NULL DEFAULT 0
            );

            -- Hourly aggregates (keep 90 days)
            CREATE TABLE IF NOT EXISTS hourly_stats (
                hour DATETIME PRIMARY KEY,
                lan_rx_total INTEGER NOT NULL DEFAULT 0,
                lan_tx_total INTEGER NOT NULL DEFAULT 0,
                inet_rx_total INTEGER NOT NULL DEFAULT 0,
                inet_tx_total INTEGER NOT NULL DEFAULT 0,
                connection_count INTEGER NOT NULL DEFAULT 0
            );

            -- Daily totals (keep forever)
            CREATE TABLE IF NOT EXISTS daily_totals (
                date DATE PRIMARY KEY,
                lan_rx_total INTEGER NOT NULL DEFAULT 0,
                lan_tx_total INTEGER NOT NULL DEFAULT 0,
                inet_rx_total INTEGER NOT NULL DEFAULT 0,
                inet_tx_total INTEGER NOT NULL DEFAULT 0,
                peak_rx_rate INTEGER NOT NULL DEFAULT 0,
                peak_tx_rate INTEGER NOT NULL DEFAULT 0
            );

            -- Index for quick sample queries
            CREATE INDEX IF NOT EXISTS idx_samples_timestamp
            ON bandwidth_samples(timestamp);

            -- Index for hourly queries
            CREATE INDEX IF NOT EXISTS idx_hourly_stats_hour
            ON hourly_stats(hour);
        """)
        conn.commit()

    def add_sample(self, lan_rx: int, lan_tx: int, inet_rx: int, inet_tx: int) -> None:
        """Add a bandwidth sample to the database."""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO bandwidth_samples (lan_rx, lan_tx, inet_rx, inet_tx)
            VALUES (?, ?, ?, ?)
        """, (lan_rx, lan_tx, inet_rx, inet_tx))
        conn.commit()

    def get_recent_samples(self, hours: int = 1) -> list[BandwidthSample]:
        """Get recent bandwidth samples."""
        conn = self._get_conn()
        cutoff = datetime.now() - timedelta(hours=hours)

        rows = conn.execute("""
            SELECT timestamp, lan_rx, lan_tx, inet_rx, inet_tx
            FROM bandwidth_samples
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (cutoff.isoformat(),)).fetchall()

        return [
            BandwidthSample(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                lan_rx=row["lan_rx"],
                lan_tx=row["lan_tx"],
                inet_rx=row["inet_rx"],
                inet_tx=row["inet_tx"]
            )
            for row in rows
        ]

    def get_hourly_stats(self, days: int = 7) -> list[HourlyStats]:
        """Get hourly statistics for the past N days."""
        conn = self._get_conn()
        cutoff = datetime.now() - timedelta(days=days)

        rows = conn.execute("""
            SELECT hour, lan_rx_total, lan_tx_total, inet_rx_total, inet_tx_total, connection_count
            FROM hourly_stats
            WHERE hour >= ?
            ORDER BY hour ASC
        """, (cutoff.isoformat(),)).fetchall()

        return [
            HourlyStats(
                hour=datetime.fromisoformat(row["hour"]),
                lan_rx_total=row["lan_rx_total"],
                lan_tx_total=row["lan_tx_total"],
                inet_rx_total=row["inet_rx_total"],
                inet_tx_total=row["inet_tx_total"],
                connection_count=row["connection_count"]
            )
            for row in rows
        ]

    def get_daily_totals(self, days: int = 30) -> list[DailyTotal]:
        """Get daily totals for the past N days."""
        conn = self._get_conn()
        cutoff = date.today() - timedelta(days=days)

        rows = conn.execute("""
            SELECT date, lan_rx_total, lan_tx_total, inet_rx_total, inet_tx_total,
                   peak_rx_rate, peak_tx_rate
            FROM daily_totals
            WHERE date >= ?
            ORDER BY date ASC
        """, (cutoff.isoformat(),)).fetchall()

        return [
            DailyTotal(
                date=date.fromisoformat(row["date"]),
                lan_rx_total=row["lan_rx_total"],
                lan_tx_total=row["lan_tx_total"],
                inet_rx_total=row["inet_rx_total"],
                inet_tx_total=row["inet_tx_total"],
                peak_rx_rate=row["peak_rx_rate"],
                peak_tx_rate=row["peak_tx_rate"]
            )
            for row in rows
        ]

    def aggregate_hourly(self) -> None:
        """Aggregate samples into hourly stats. Call every hour."""
        conn = self._get_conn()

        # Get the last hour that was aggregated
        last_hour = conn.execute(
            "SELECT MAX(hour) FROM hourly_stats"
        ).fetchone()[0]

        if last_hour:
            start_hour = datetime.fromisoformat(last_hour) + timedelta(hours=1)
        else:
            # Start from the earliest sample
            earliest = conn.execute(
                "SELECT MIN(timestamp) FROM bandwidth_samples"
            ).fetchone()[0]
            if not earliest:
                return
            start_hour = datetime.fromisoformat(earliest).replace(
                minute=0, second=0, microsecond=0
            )

        now = datetime.now()
        current_hour = start_hour

        while current_hour < now:
            next_hour = current_hour + timedelta(hours=1)

            # Aggregate samples for this hour
            row = conn.execute("""
                SELECT
                    COALESCE(SUM(lan_rx), 0) as lan_rx,
                    COALESCE(SUM(lan_tx), 0) as lan_tx,
                    COALESCE(SUM(inet_rx), 0) as inet_rx,
                    COALESCE(SUM(inet_tx), 0) as inet_tx,
                    COUNT(*) as sample_count
                FROM bandwidth_samples
                WHERE timestamp >= ? AND timestamp < ?
            """, (current_hour.isoformat(), next_hour.isoformat())).fetchone()

            if row and row["sample_count"] > 0:
                conn.execute("""
                    INSERT OR REPLACE INTO hourly_stats
                    (hour, lan_rx_total, lan_tx_total, inet_rx_total, inet_tx_total, connection_count)
                    VALUES (?, ?, ?, ?, ?, 0)
                """, (
                    current_hour.isoformat(),
                    row["lan_rx"], row["lan_tx"],
                    row["inet_rx"], row["inet_tx"]
                ))

            current_hour = next_hour

        conn.commit()

    def aggregate_daily(self) -> None:
        """Aggregate hourly stats into daily totals. Call at midnight."""
        conn = self._get_conn()

        yesterday = date.today() - timedelta(days=1)

        # Check if already aggregated
        existing = conn.execute(
            "SELECT 1 FROM daily_totals WHERE date = ?",
            (yesterday.isoformat(),)
        ).fetchone()

        if existing:
            return

        # Get hourly stats for yesterday
        day_start = datetime.combine(yesterday, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        row = conn.execute("""
            SELECT
                COALESCE(SUM(lan_rx_total), 0) as lan_rx,
                COALESCE(SUM(lan_tx_total), 0) as lan_tx,
                COALESCE(SUM(inet_rx_total), 0) as inet_rx,
                COALESCE(SUM(inet_tx_total), 0) as inet_tx,
                MAX(
                    COALESCE((lan_rx_total + inet_rx_total), 0)
                ) as peak_rx,
                MAX(
                    COALESCE((lan_tx_total + inet_tx_total), 0)
                ) as peak_tx
            FROM hourly_stats
            WHERE hour >= ? AND hour < ?
        """, (day_start.isoformat(), day_end.isoformat())).fetchone()

        if row:
            conn.execute("""
                INSERT OR REPLACE INTO daily_totals
                (date, lan_rx_total, lan_tx_total, inet_rx_total, inet_tx_total,
                 peak_rx_rate, peak_tx_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                yesterday.isoformat(),
                row["lan_rx"], row["lan_tx"],
                row["inet_rx"], row["inet_tx"],
                row["peak_rx"], row["peak_tx"]
            ))
            conn.commit()

    def cleanup_old_data(self) -> None:
        """Remove old data beyond retention period."""
        conn = self._get_conn()

        # Delete old samples (keep 7 days)
        sample_cutoff = datetime.now() - timedelta(days=7)
        conn.execute(
            "DELETE FROM bandwidth_samples WHERE timestamp < ?",
            (sample_cutoff.isoformat(),)
        )

        # Delete old hourly stats (keep 90 days)
        hourly_cutoff = datetime.now() - timedelta(days=90)
        conn.execute(
            "DELETE FROM hourly_stats WHERE hour < ?",
            (hourly_cutoff.isoformat(),)
        )

        conn.commit()

    def get_total_usage(self, days: int = 30) -> tuple[int, int, int, int]:
        """Get total usage for the past N days."""
        conn = self._get_conn()
        cutoff = date.today() - timedelta(days=days)

        row = conn.execute("""
            SELECT
                COALESCE(SUM(lan_rx_total), 0) as lan_rx,
                COALESCE(SUM(lan_tx_total), 0) as lan_tx,
                COALESCE(SUM(inet_rx_total), 0) as inet_rx,
                COALESCE(SUM(inet_tx_total), 0) as inet_tx
            FROM daily_totals
            WHERE date >= ?
        """, (cutoff.isoformat(),)).fetchone()

        return (
            row["lan_rx"], row["lan_tx"],
            row["inet_rx"], row["inet_tx"]
        )

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
