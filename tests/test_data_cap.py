"""Unit tests for data cap tracking module."""

import pytest
import json
from datetime import datetime
from unittest.mock import patch

from netscope.core.data_cap import DataCapTracker, DataCapStatus


class TestDataCapStatus:
    """Tests for DataCapStatus dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        status = DataCapStatus(
            enabled=True,
            monthly_cap_gb=100.0,
            used_gb=0.0,
            remaining_gb=100.0,
            percent_used=0.0,
            days_remaining=30,
            projected_usage_gb=0.0,
            will_exceed=False,
            warning_level="none",
        )
        assert status.enabled
        assert status.percent_used == 0.0
        assert status.warning_level == "none"


class TestDataCapTracker:
    """Tests for DataCapTracker class."""

    def test_initial_state(self, mock_usage_file):
        """Should initialize with correct defaults."""
        tracker = DataCapTracker(monthly_cap_gb=50.0)
        assert tracker.monthly_cap_gb == 50.0
        assert not tracker.enabled
        assert tracker.warn_50
        assert tracker.warn_75
        assert tracker.warn_90

    def test_disabled_tracker_returns_empty_status(self, mock_usage_file):
        """Disabled tracker should return empty status."""
        tracker = DataCapTracker(enabled=False)
        status = tracker.get_status()

        assert not status.enabled
        assert status.used_gb == 0.0
        assert status.remaining_gb == tracker.monthly_cap_gb

    def test_update_session_usage(self, mock_usage_file):
        """Should track session usage."""
        tracker = DataCapTracker(enabled=True)
        tracker.update_session_usage(1024**3, 512 * 1024**2)  # 1GB RX, 512MB TX

        status = tracker.get_status()
        assert status.used_gb > 0

    def test_percent_calculation(self, mock_usage_file):
        """Should calculate percent used correctly."""
        tracker = DataCapTracker(monthly_cap_gb=100.0, enabled=True)
        # Use 50GB out of 100GB
        tracker.update_session_usage(50 * 1024**3, 0)

        status = tracker.get_status()
        assert status.percent_used == pytest.approx(50.0, rel=0.01)

    def test_remaining_calculation(self, mock_usage_file):
        """Should calculate remaining correctly."""
        tracker = DataCapTracker(monthly_cap_gb=100.0, enabled=True)
        tracker.update_session_usage(30 * 1024**3, 20 * 1024**3)  # 50GB total

        status = tracker.get_status()
        assert status.remaining_gb == pytest.approx(50.0, rel=0.01)

    def test_warning_level_50(self, mock_usage_file):
        """Should trigger 50% warning."""
        tracker = DataCapTracker(monthly_cap_gb=100.0, enabled=True, warn_50=True)
        tracker.update_session_usage(50 * 1024**3, 0)

        status = tracker.get_status()
        assert status.warning_level == "50%"

    def test_warning_level_75(self, mock_usage_file):
        """Should trigger 75% warning."""
        tracker = DataCapTracker(monthly_cap_gb=100.0, enabled=True, warn_75=True)
        tracker.update_session_usage(75 * 1024**3, 0)

        status = tracker.get_status()
        assert status.warning_level == "75%"

    def test_warning_level_90(self, mock_usage_file):
        """Should trigger 90% warning."""
        tracker = DataCapTracker(monthly_cap_gb=100.0, enabled=True, warn_90=True)
        tracker.update_session_usage(90 * 1024**3, 0)

        status = tracker.get_status()
        assert status.warning_level == "90%"

    def test_warning_level_100(self, mock_usage_file):
        """Should trigger 100% warning when exceeded."""
        tracker = DataCapTracker(monthly_cap_gb=100.0, enabled=True)
        tracker.update_session_usage(100 * 1024**3, 0)

        status = tracker.get_status()
        assert status.warning_level == "100%"

    def test_warning_disabled(self, mock_usage_file):
        """Should not warn when warnings disabled."""
        tracker = DataCapTracker(
            monthly_cap_gb=100.0, enabled=True,
            warn_50=False, warn_75=False, warn_90=False
        )
        tracker.update_session_usage(80 * 1024**3, 0)

        status = tracker.get_status()
        assert status.warning_level == "none"

    def test_set_cap(self, mock_usage_file):
        """Should update cap value."""
        tracker = DataCapTracker()
        tracker.set_cap(200.0)
        assert tracker.monthly_cap_gb == 200.0

    def test_set_cap_negative(self, mock_usage_file):
        """Should not allow negative cap."""
        tracker = DataCapTracker()
        tracker.set_cap(-50.0)
        assert tracker.monthly_cap_gb == 0.0

    def test_set_enabled(self, mock_usage_file):
        """Should toggle enabled state."""
        tracker = DataCapTracker(enabled=False)
        tracker.set_enabled(True)
        assert tracker.enabled

    def test_set_warnings(self, mock_usage_file):
        """Should update warning thresholds."""
        tracker = DataCapTracker()
        tracker.set_warnings(False, True, False)
        assert not tracker.warn_50
        assert tracker.warn_75
        assert not tracker.warn_90

    def test_reset_month(self, mock_usage_file):
        """Should reset usage to zero."""
        tracker = DataCapTracker(enabled=True)
        tracker.update_session_usage(50 * 1024**3, 0)
        tracker.reset_month()

        status = tracker.get_status()
        assert status.used_gb == 0.0

    def test_persist_usage(self, mock_usage_file):
        """Should persist usage to file."""
        tracker = DataCapTracker(monthly_cap_gb=100.0, enabled=True)
        tracker.update_session_usage(10 * 1024**3, 5 * 1024**3)

        # Check file was written
        assert mock_usage_file.exists()
        data = json.loads(mock_usage_file.read_text())
        assert "month" in data
        assert data["total_rx"] == 10 * 1024**3
        assert data["total_tx"] == 5 * 1024**3

    def test_load_persisted_usage(self, mock_usage_file):
        """Should load persisted usage on init."""
        current_month = datetime.now().strftime("%Y-%m")

        # Write existing data
        mock_usage_file.write_text(json.dumps({
            "month": current_month,
            "total_rx": 20 * 1024**3,
            "total_tx": 10 * 1024**3,
        }))

        tracker = DataCapTracker(enabled=True)
        # Add session usage
        tracker.update_session_usage(5 * 1024**3, 2 * 1024**3)

        status = tracker.get_status()
        # Should include both persisted and session
        assert status.used_gb == pytest.approx(37.0, rel=0.01)  # 30 + 7 GB

    def test_new_month_resets_usage(self, mock_usage_file):
        """Should reset when month changes."""
        # Write data for previous month
        mock_usage_file.write_text(json.dumps({
            "month": "2000-01",  # Old month
            "total_rx": 50 * 1024**3,
            "total_tx": 50 * 1024**3,
        }))

        tracker = DataCapTracker(enabled=True)
        tracker.update_session_usage(1 * 1024**3, 1 * 1024**3)

        status = tracker.get_status()
        # Should only count current session
        assert status.used_gb == pytest.approx(2.0, rel=0.01)

    def test_get_new_warning(self, mock_usage_file):
        """Should detect new warning level."""
        tracker = DataCapTracker(monthly_cap_gb=100.0, enabled=True)
        tracker.update_session_usage(0, 0)

        # Update to 50%
        tracker.update_session_usage(50 * 1024**3, 0)
        status = tracker.get_status()
        warning = tracker.get_new_warning(status)

        assert warning is not None
        assert "50%" in warning

    def test_no_repeat_warning(self, mock_usage_file):
        """Should not repeat same warning level."""
        tracker = DataCapTracker(monthly_cap_gb=100.0, enabled=True)

        # First warning at 50%
        tracker.update_session_usage(50 * 1024**3, 0)
        status1 = tracker.get_status()
        warning1 = tracker.get_new_warning(status1)
        assert warning1 is not None

        # Update to 55% - same warning level
        tracker.update_session_usage(55 * 1024**3, 0)
        status2 = tracker.get_status()
        warning2 = tracker.get_new_warning(status2)
        assert warning2 is None  # No new warning

        # Update to 75% - new warning level
        tracker.update_session_usage(75 * 1024**3, 0)
        status3 = tracker.get_status()
        warning3 = tracker.get_new_warning(status3)
        assert warning3 is not None
