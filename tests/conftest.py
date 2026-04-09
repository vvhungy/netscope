"""Pytest configuration and fixtures."""


import pytest


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication instance for widget tests."""
    import os
    import sys
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory."""
    config_dir = tmp_path / ".config" / "netscope"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def temp_config_file(temp_config_dir):
    """Create a temporary config file."""
    return temp_config_dir / "config.json"


@pytest.fixture
def mock_config_path(temp_config_file, monkeypatch):
    """Mock the CONFIG_FILE path for tests."""
    from netscope import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_FILE", temp_config_file)
    monkeypatch.setattr(config_module, "CONFIG_DIR", temp_config_file.parent)
    yield temp_config_file


@pytest.fixture
def sample_config():
    """Sample configuration data."""
    return {
        "interface": "eth0",
        "lan_subnet": "192.168.1.0/24",
        "update_interval": 2.0,
        "connection_interval": 5.0,
        "start_minimized": True,
        "show_lan_traffic": True,
        "data_cap_enabled": True,
        "data_cap_gb": 50.0,
    }


@pytest.fixture
def mock_usage_file(tmp_path, monkeypatch):
    """Mock the USAGE_FILE path for DataCapTracker tests."""
    usage_file = tmp_path / ".config" / "netscope" / "usage.json"
    usage_file.parent.mkdir(parents=True, exist_ok=True)

    from netscope.core import data_cap
    monkeypatch.setattr(data_cap.DataCapTracker, "USAGE_FILE", usage_file)
    yield usage_file


@pytest.fixture
def mock_alert_rules_file(tmp_path, monkeypatch):
    """Mock the CONFIG_FILE path for AlertRulesManager tests."""
    rules_file = tmp_path / ".config" / "netscope" / "alert_rules.json"
    rules_file.parent.mkdir(parents=True, exist_ok=True)

    from netscope.core import alert_rules
    monkeypatch.setattr(alert_rules.AlertRulesManager, "CONFIG_FILE", rules_file)
    yield rules_file
