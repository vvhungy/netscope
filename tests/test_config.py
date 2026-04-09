"""Unit tests for configuration module."""

import json

from netscope.config import DEFAULT_CONFIG, load_config, save_config


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_default_when_no_file(self, mock_config_path):
        """Should return default config when file doesn't exist."""
        config = load_config()
        assert config == DEFAULT_CONFIG

    def test_load_existing_config(self, mock_config_path, sample_config):
        """Should load and return existing config."""
        mock_config_path.write_text(json.dumps(sample_config))
        config = load_config()

        assert config["interface"] == "eth0"
        assert config["data_cap_gb"] == 50.0

    def test_merge_with_defaults(self, mock_config_path):
        """Should merge with defaults for missing keys."""
        partial_config = {"interface": "wlan0"}
        mock_config_path.write_text(json.dumps(partial_config))
        config = load_config()

        assert config["interface"] == "wlan0"
        assert config["update_interval"] == DEFAULT_CONFIG["update_interval"]
        assert config["data_cap_enabled"] == DEFAULT_CONFIG["data_cap_enabled"]

    def test_handle_invalid_json(self, mock_config_path):
        """Should return default config on invalid JSON."""
        mock_config_path.write_text("not valid json")
        config = load_config()
        assert config == DEFAULT_CONFIG


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_creates_directory(self, mock_config_path):
        """Should create config directory if it doesn't exist."""
        mock_config_path.parent.mkdir(parents=True, exist_ok=True)
        # Remove the directory to test creation
        import shutil
        shutil.rmtree(mock_config_path.parent)

        save_config({"test": "value"})
        assert mock_config_path.parent.exists()

    def test_save_writes_json(self, mock_config_path):
        """Should write valid JSON to config file."""
        config = {"interface": "eth0", "update_interval": 2.0}
        save_config(config)

        saved = json.loads(mock_config_path.read_text())
        assert saved["interface"] == "eth0"
        assert saved["update_interval"] == 2.0

    def test_save_overwrites_existing(self, mock_config_path):
        """Should overwrite existing config file."""
        mock_config_path.write_text(json.dumps({"old": "data"}))

        new_config = {"new": "config"}
        save_config(new_config)

        saved = json.loads(mock_config_path.read_text())
        assert "old" not in saved
        assert saved["new"] == "config"
