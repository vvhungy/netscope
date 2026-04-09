"""Unit tests for alert rules module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from netscope.core.alert_rules import (
    AlertRule, AlertRulesManager, AlertType, AlertDirection,
    get_alert_manager
)


class TestAlertRule:
    """Tests for AlertRule dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        rule = AlertRule(id="test", name="Test Rule")
        assert rule.enabled
        assert rule.alert_type == AlertType.RATE_THRESHOLD
        assert rule.direction == AlertDirection.BOTH
        assert rule.threshold == 0.0

    def test_to_dict(self):
        """Should serialize to dictionary."""
        rule = AlertRule(
            id="test-id",
            name="High Download",
            alert_type=AlertType.RATE_THRESHOLD,
            direction=AlertDirection.DOWNLOAD,
            threshold=50 * 1024 * 1024,
        )
        data = rule.to_dict()

        assert data["id"] == "test-id"
        assert data["name"] == "High Download"
        assert data["alert_type"] == "rate"
        assert data["direction"] == "download"
        assert data["threshold"] == 50 * 1024 * 1024

    def test_from_dict(self):
        """Should deserialize from dictionary."""
        data = {
            "id": "test-id",
            "name": "High Upload",
            "enabled": False,
            "alert_type": "rate",
            "direction": "upload",
            "threshold": 20 * 1024 * 1024,
            "period_minutes": 30,
            "cooldown_minutes": 15,
        }
        rule = AlertRule.from_dict(data)

        assert rule.id == "test-id"
        assert rule.name == "High Upload"
        assert not rule.enabled
        assert rule.alert_type == AlertType.RATE_THRESHOLD
        assert rule.direction == AlertDirection.UPLOAD
        assert rule.threshold == 20 * 1024 * 1024

    def test_roundtrip_serialization(self):
        """Should survive to_dict/from_dict roundtrip."""
        original = AlertRule(
            id="test",
            name="Test",
            enabled=False,
            alert_type=AlertType.VOLUME_THRESHOLD,
            direction=AlertDirection.BOTH,
            threshold=500 * 1024 * 1024,
            period_minutes=60,
            cooldown_minutes=10,
        )
        data = original.to_dict()
        restored = AlertRule.from_dict(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.enabled == original.enabled
        assert restored.alert_type == original.alert_type
        assert restored.direction == original.direction
        assert restored.threshold == original.threshold


class TestAlertRulesManager:
    """Tests for AlertRulesManager class."""

    def test_load_default_rules(self, mock_alert_rules_file):
        """Should create default rules if no file exists."""
        manager = AlertRulesManager()
        rules = manager.get_rules()

        assert len(rules) > 0
        assert any(r.id == "high-download-rate" for r in rules)
        assert any(r.id == "high-upload-rate" for r in rules)

    def test_add_rule(self, mock_alert_rules_file):
        """Should add a new rule."""
        manager = AlertRulesManager()
        initial_count = len(manager.get_rules())

        rule = AlertRule(id="custom", name="Custom Rule")
        manager.add_rule(rule)

        assert len(manager.get_rules()) == initial_count + 1

    def test_update_rule(self, mock_alert_rules_file):
        """Should update existing rule."""
        manager = AlertRulesManager()
        rule = AlertRule(id="test", name="Original", threshold=100.0)
        manager.add_rule(rule)

        # Update
        updated = AlertRule(id="test", name="Updated", threshold=200.0)
        manager.update_rule(updated)

        rules = manager.get_rules()
        found = next(r for r in rules if r.id == "test")
        assert found.name == "Updated"
        assert found.threshold == 200.0

    def test_remove_rule(self, mock_alert_rules_file):
        """Should remove a rule."""
        manager = AlertRulesManager()
        rule = AlertRule(id="to-remove", name="Remove Me")
        manager.add_rule(rule)

        manager.remove_rule("to-remove")

        rules = manager.get_rules()
        assert not any(r.id == "to-remove" for r in rules)

    def test_check_rate_alerts_disabled_rule(self, mock_alert_rules_file):
        """Should not trigger disabled rules."""
        manager = AlertRulesManager()
        rule = AlertRule(
            id="test",
            name="Test",
            enabled=False,
            alert_type=AlertType.RATE_THRESHOLD,
            threshold=100.0,
        )
        manager.add_rule(rule)

        triggered = manager.check_rate_alerts(200.0, 0.0)
        assert not any(t[0].id == "test" for t in triggered)

    def test_check_rate_alerts_download(self, mock_alert_rules_file):
        """Should trigger download rate alerts."""
        manager = AlertRulesManager()
        rule = AlertRule(
            id="dl-test",
            name="Download Test",
            alert_type=AlertType.RATE_THRESHOLD,
            direction=AlertDirection.DOWNLOAD,
            threshold=50.0,  # 50 bytes/sec
            cooldown_minutes=0,  # No cooldown for test
        )
        manager.add_rule(rule)

        triggered = manager.check_rate_alerts(100.0, 0.0)

        assert any(t[0].id == "dl-test" for t in triggered)

    def test_check_rate_alerts_upload(self, mock_alert_rules_file):
        """Should trigger upload rate alerts."""
        manager = AlertRulesManager()
        rule = AlertRule(
            id="ul-test",
            name="Upload Test",
            alert_type=AlertType.RATE_THRESHOLD,
            direction=AlertDirection.UPLOAD,
            threshold=30.0,
            cooldown_minutes=0,
        )
        manager.add_rule(rule)

        triggered = manager.check_rate_alerts(0.0, 60.0)

        assert any(t[0].id == "ul-test" for t in triggered)

    def test_check_rate_alerts_both(self, mock_alert_rules_file):
        """Should trigger alerts for combined rate."""
        manager = AlertRulesManager()
        rule = AlertRule(
            id="both-test",
            name="Both Test",
            alert_type=AlertType.RATE_THRESHOLD,
            direction=AlertDirection.BOTH,
            threshold=100.0,
            cooldown_minutes=0,
        )
        manager.add_rule(rule)

        # 60 + 50 = 110 > 100
        triggered = manager.check_rate_alerts(60.0, 50.0)

        assert any(t[0].id == "both-test" for t in triggered)

    def test_check_rate_alerts_cooldown(self, mock_alert_rules_file):
        """Should respect cooldown period."""
        manager = AlertRulesManager()
        rule = AlertRule(
            id="cooldown-test",
            name="Cooldown Test",
            alert_type=AlertType.RATE_THRESHOLD,
            threshold=50.0,
            cooldown_minutes=30,
        )
        manager.add_rule(rule)

        # First trigger
        triggered1 = manager.check_rate_alerts(100.0, 0.0)
        assert any(t[0].id == "cooldown-test" for t in triggered1)

        # Immediate second check - should not trigger due to cooldown
        triggered2 = manager.check_rate_alerts(100.0, 0.0)
        assert not any(t[0].id == "cooldown-test" for t in triggered2)

    def test_check_data_cap_alert(self, mock_alert_rules_file):
        """Should trigger data cap percentage alerts."""
        manager = AlertRulesManager()
        rule = AlertRule(
            id="cap-test",
            name="Cap Test",
            alert_type=AlertType.DATA_CAP_PERCENT,
            threshold=80.0,
            cooldown_minutes=0,
        )
        manager.add_rule(rule)

        triggered = manager.check_rate_alerts(0.0, 0.0, data_cap_percent=85.0)

        assert any(t[0].id == "cap-test" for t in triggered)

    def test_on_alert_callback(self, mock_alert_rules_file):
        """Should call registered callback on alert."""
        manager = AlertRulesManager()

        callback_calls = []
        manager.set_on_alert(lambda rule, msg: callback_calls.append((rule, msg)))

        rule = AlertRule(
            id="callback-test",
            name="Callback Test",
            alert_type=AlertType.RATE_THRESHOLD,
            threshold=10.0,
            cooldown_minutes=0,
        )
        manager.add_rule(rule)

        manager.check_rate_alerts(50.0, 0.0)

        assert len(callback_calls) == 1
        assert callback_calls[0][0].id == "callback-test"


class TestAlertManagerSingleton:
    """Tests for global alert manager singleton."""

    def test_get_alert_manager_returns_same_instance(self):
        """Should return the same instance."""
        # Reset singleton
        import netscope.core.alert_rules as ar
        ar._alert_manager = None

        manager1 = get_alert_manager()
        manager2 = get_alert_manager()

        assert manager1 is manager2
