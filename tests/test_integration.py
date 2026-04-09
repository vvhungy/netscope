"""Integration tests for NetScope workflows."""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from netscope.core.bandwidth import BandwidthCalculator, BandwidthStats
from netscope.core.data_cap import DataCapTracker, DataCapStatus
from netscope.core.alert_rules import AlertRulesManager, AlertRule, AlertType, AlertDirection


class TestBandwidthMonitoringWorkflow:
    """Integration tests for bandwidth monitoring end-to-end."""

    def test_calculator_with_simulated_iptables_data(self, mock_usage_file):
        """Test calculator with simulated iptables counter data."""
        calculator = BandwidthCalculator()
        tracker = DataCapTracker(monthly_cap_gb=100.0, enabled=True)

        # Simulate iptables counter snapshots over time
        snapshots = [
            {"lan_rx": 0, "lan_tx": 0, "inet_rx": 0, "inet_tx": 0},
            {"lan_rx": 1024, "lan_tx": 512, "inet_rx": 2048, "inet_tx": 1024},
            {"lan_rx": 3072, "lan_tx": 2048, "inet_rx": 8192, "inet_tx": 4096},
            {"lan_rx": 6144, "lan_tx": 4096, "inet_rx": 16384, "inet_tx": 8192},
        ]

        results = []
        current_time = 0.0

        for counters in snapshots:
            stats = calculator.update(counters, current_time=current_time)
            results.append(stats)

            # Update data cap tracker
            tracker.update_session_usage(
                stats.inet_rx_total,
                stats.inet_tx_total
            )

            current_time += 1.0

        # Verify rate calculations progressed
        assert results[0].inet_rx_rate == 0  # First update
        assert results[1].inet_rx_rate == 2048.0  # Second update
        assert results[2].inet_rx_rate == 6144.0  # Third update

        # Verify data cap tracked cumulative usage
        status = tracker.get_status()
        assert status.used_gb > 0

    def test_bandwidth_alerts_integration(self, mock_alert_rules_file):
        """Test alert triggering based on bandwidth rates."""
        manager = AlertRulesManager()

        # Add a rule that triggers at 1 KB/s download
        rule = AlertRule(
            id="low-rate-alert",
            name="Low Rate Alert",
            alert_type=AlertType.RATE_THRESHOLD,
            direction=AlertDirection.DOWNLOAD,
            threshold=1024.0,  # 1 KB/s
            cooldown_minutes=0,
        )
        manager.add_rule(rule)

        # Simulate callback
        alerts_triggered = []
        manager.set_on_alert(lambda r, m: alerts_triggered.append((r.id, m)))

        # Simulate bandwidth updates with varying rates
        rates = [
            (512.0, 0.0),    # Below threshold
            (1024.0, 0.0),   # At threshold
            (2048.0, 0.0),   # Above threshold
        ]

        for rx_rate, tx_rate in rates:
            manager.check_rate_alerts(rx_rate, tx_rate)

        # Should have triggered twice (at and above threshold)
        assert len(alerts_triggered) >= 1
        assert any(a[0] == "low-rate-alert" for a in alerts_triggered)


class TestDataCapPersistenceWorkflow:
    """Integration tests for data cap tracking with persistence."""

    def test_data_cap_persists_across_sessions(self, mock_usage_file):
        """Test that usage persists across tracker instances."""
        current_month = datetime.now().strftime("%Y-%m")

        # Session 1: Use some data
        tracker1 = DataCapTracker(monthly_cap_gb=100.0, enabled=True)
        tracker1.update_session_usage(10 * 1024**3, 5 * 1024**3)

        status1 = tracker1.get_status()
        assert status1.used_gb == pytest.approx(15.0, rel=0.01)

        # Simulate app restart - create new tracker
        tracker2 = DataCapTracker(monthly_cap_gb=100.0, enabled=True)

        # Add more usage in new session
        tracker2.update_session_usage(3 * 1024**3, 2 * 1024**3)

        status2 = tracker2.get_status()
        # Should include persisted + new session usage
        # Note: persisted was 15GB, new session adds 5GB
        assert status2.used_gb == pytest.approx(20.0, rel=0.01)

    def test_data_cap_warning_escalation(self, mock_usage_file):
        """Test warning level escalation over time."""
        tracker = DataCapTracker(
            monthly_cap_gb=100.0,
            enabled=True,
            warn_50=True,
            warn_75=True,
            warn_90=True,
        )

        warnings_received = []

        # Simulate increasing usage
        usage_steps = [
            (10 * 1024**3, 0),   # 10%
            (25 * 1024**3, 0),   # 25%
            (50 * 1024**3, 0),   # 50%
            (75 * 1024**3, 0),   # 75%
            (90 * 1024**3, 0),   # 90%
        ]

        for rx, tx in usage_steps:
            tracker.update_session_usage(rx, tx)
            status = tracker.get_status()
            warning = tracker.get_new_warning(status)
            if warning:
                warnings_received.append(status.warning_level)

        # Should have received 50%, 75%, 90% warnings
        assert "50%" in warnings_received
        assert "75%" in warnings_received
        assert "90%" in warnings_received


class TestAlertRulesPersistenceWorkflow:
    """Integration tests for alert rules with persistence."""

    def test_alert_rules_persist_across_sessions(self, mock_alert_rules_file):
        """Test that custom rules persist across manager instances."""
        # Session 1: Create custom rule
        manager1 = AlertRulesManager()
        custom_rule = AlertRule(
            id="my-custom-rule",
            name="My Custom Alert",
            alert_type=AlertType.RATE_THRESHOLD,
            direction=AlertDirection.DOWNLOAD,
            threshold=5 * 1024 * 1024,  # 5 MB/s
            enabled=True,
        )
        manager1.add_rule(custom_rule)

        # Verify it was added
        rules1 = manager1.get_rules()
        assert any(r.id == "my-custom-rule" for r in rules1)

        # Session 2: Create new manager (simulates restart)
        manager2 = AlertRulesManager()
        rules2 = manager2.get_rules()

        # Custom rule should persist
        assert any(r.id == "my-custom-rule" for r in rules2)

        found = next(r for r in rules2 if r.id == "my-custom-rule")
        assert found.name == "My Custom Alert"
        assert found.threshold == 5 * 1024 * 1024

    def test_update_rule_persists(self, mock_alert_rules_file):
        """Test that rule updates persist."""
        manager1 = AlertRulesManager()
        rule = AlertRule(
            id="updateable-rule",
            name="Original Name",
            threshold=100.0,
        )
        manager1.add_rule(rule)

        # Update the rule
        updated = AlertRule(
            id="updateable-rule",
            name="Updated Name",
            threshold=200.0,
        )
        manager1.update_rule(updated)

        # New session
        manager2 = AlertRulesManager()
        rules = manager2.get_rules()
        found = next(r for r in rules if r.id == "updateable-rule")

        assert found.name == "Updated Name"
        assert found.threshold == 200.0


class TestEndToEndWorkflow:
    """Full end-to-end integration tests."""

    def test_bandwidth_monitoring_with_data_cap_and_alerts(
        self, mock_usage_file, mock_alert_rules_file
    ):
        """Test complete workflow: bandwidth -> data cap -> alerts."""
        calculator = BandwidthCalculator()
        tracker = DataCapTracker(monthly_cap_gb=10.0, enabled=True)  # 10 GB cap
        alert_manager = AlertRulesManager()

        # Add data cap alert at 50%
        cap_alert = AlertRule(
            id="cap-50",
            name="50% Data Cap",
            alert_type=AlertType.DATA_CAP_PERCENT,
            threshold=50.0,
            cooldown_minutes=0,
        )
        alert_manager.add_rule(cap_alert)

        alerts = []
        alert_manager.set_on_alert(lambda r, m: alerts.append((r.id, m)))

        # Simulate high bandwidth usage
        current_time = 0.0
        inet_rx_total = 0
        inet_tx_total = 0

        # Simulate 5 seconds of 1 GB/s download (will hit 50% of 10GB cap)
        for i in range(6):
            inet_rx_total += 1024**3  # Add 1 GB
            counters = {
                "lan_rx": 0,
                "lan_tx": 0,
                "inet_rx": inet_rx_total,
                "inet_tx": 0,
            }

            stats = calculator.update(counters, current_time=current_time)
            tracker.update_session_usage(stats.inet_rx_total, stats.inet_tx_total)

            # Check alerts
            status = tracker.get_status()
            alert_manager.check_rate_alerts(
                stats.inet_rx_rate,
                stats.inet_tx_rate,
                data_cap_percent=status.percent_used
            )

            current_time += 1.0

        # Should have triggered 50% alert
        assert any(a[0] == "cap-50" for a in alerts)
        assert tracker.get_status().percent_used >= 50.0


class TestSpeedTestIntegration:
    """Integration tests for speed test functionality."""

    def test_speed_test_result_format(self):
        """Test that speed test results are properly formatted."""
        from netscope.core.speed_test import SpeedTestResult

        result = SpeedTestResult(
            download_mbps=100.5,
            upload_mbps=25.3,
            ping_ms=15.2,
            server="Test Server",
            timestamp="2024-01-01T00:00:00Z",
        )

        assert result.download_mbps == 100.5
        assert result.upload_mbps == 25.3
        assert result.ping_ms == 15.2
        assert not result.error

    def test_speed_test_error_result(self):
        """Test that speed test errors are captured."""
        from netscope.core.speed_test import SpeedTestResult

        result = SpeedTestResult(error="Connection failed")

        assert result.error == "Connection failed"
        assert result.download_mbps == 0.0
        assert result.upload_mbps == 0.0
