"""Tests for HistoryManager — write and read bandwidth samples."""

from pathlib import Path

from netscope.core.history import HistoryManager


def _make_manager(tmp_path: Path) -> HistoryManager:
    db = tmp_path / "test_history.db"
    return HistoryManager(db_path=db)


def test_add_and_read_samples(tmp_path: Path) -> None:
    """Write three samples, read them back — row count and values match."""
    mgr = _make_manager(tmp_path)

    mgr.add_sample(lan_rx=100, lan_tx=200, inet_rx=300, inet_tx=400)
    mgr.add_sample(lan_rx=150, lan_tx=250, inet_rx=350, inet_tx=450)
    mgr.add_sample(lan_rx=200, lan_tx=300, inet_rx=400, inet_tx=500)

    samples = mgr.get_recent_samples(hours=1)
    assert len(samples) == 3

    assert samples[0].lan_rx == 100
    assert samples[0].inet_tx == 400
    assert samples[2].lan_rx == 200
    assert samples[2].inet_tx == 500

    mgr.close()


def test_get_recent_samples_respects_time_window(tmp_path: Path) -> None:
    """Samples older than the requested window are excluded."""
    mgr = _make_manager(tmp_path)
    conn = mgr._get_conn()

    # Insert a sample 2 hours ago using SQLite's own clock (UTC-consistent)
    conn.execute(
        "INSERT INTO bandwidth_samples (timestamp, lan_rx, lan_tx, inet_rx, inet_tx) "
        "VALUES (datetime('now', '-2 hours'), 10, 20, 30, 40)"
    )
    conn.commit()

    # Insert a recent sample
    mgr.add_sample(lan_rx=50, lan_tx=60, inet_rx=70, inet_tx=80)

    # 1-hour window should only see the recent sample
    samples_1h = mgr.get_recent_samples(hours=1)
    assert len(samples_1h) == 1
    assert samples_1h[0].lan_rx == 50

    # 3-hour window should see both
    samples_3h = mgr.get_recent_samples(hours=3)
    assert len(samples_3h) == 2

    mgr.close()


def test_schema_created_on_init(tmp_path: Path) -> None:
    """Database file and tables are created on construction."""
    db = tmp_path / "fresh.db"
    mgr = HistoryManager(db_path=db)

    assert db.exists()

    conn = mgr._get_conn()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {r["name"] for r in tables}
    assert "bandwidth_samples" in table_names
    assert "hourly_stats" in table_names
    assert "daily_totals" in table_names

    mgr.close()


def test_close_disconnects(tmp_path: Path) -> None:
    """close() releases the connection; subsequent operations create a new one."""
    mgr = _make_manager(tmp_path)
    mgr.add_sample(lan_rx=1, lan_tx=2, inet_rx=3, inet_tx=4)
    mgr.close()

    assert mgr._conn is None

    # Re-opening should work
    mgr.add_sample(lan_rx=5, lan_tx=6, inet_rx=7, inet_tx=8)
    samples = mgr.get_recent_samples(hours=1)
    assert len(samples) == 2
    mgr.close()


def test_empty_db_returns_no_samples(tmp_path: Path) -> None:
    """Reading from a fresh DB returns an empty list, not an error."""
    mgr = _make_manager(tmp_path)
    assert mgr.get_recent_samples(hours=24) == []
    assert mgr.get_hourly_stats(days=7) == []
    assert mgr.get_daily_totals(days=30) == []
    mgr.close()
