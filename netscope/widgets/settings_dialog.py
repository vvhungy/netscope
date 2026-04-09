"""Settings dialog for NetScope configuration."""

import uuid
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QPushButton, QComboBox, QGroupBox, QFormLayout, QDialogButtonBox,
    QMessageBox, QFrame, QListWidget, QListWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..config import load_config, save_config, DEFAULT_CONFIG, CONFIG_FILE
from ..core.alert_rules import (
    AlertRulesManager, AlertRule, AlertType, AlertDirection,
    get_alert_manager
)


class AlertRuleEditor(QWidget):
    """Widget for editing a single alert rule."""

    def __init__(self, rule: AlertRule | None = None):
        super().__init__()
        self._rule = rule
        self._setup_ui()
        if rule:
            self._load_rule(rule)

    def _setup_ui(self) -> None:
        layout = QFormLayout(self)

        # Rule name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g., High Download Alert")
        layout.addRow("Name:", self._name_edit)

        # Enabled
        self._enabled_check = QCheckBox("Enabled")
        layout.addRow("", self._enabled_check)

        # Alert type
        self._type_combo = QComboBox()
        self._type_combo.addItem("Rate Threshold", AlertType.RATE_THRESHOLD.value)
        self._type_combo.addItem("Volume in Period", AlertType.VOLUME_THRESHOLD.value)
        self._type_combo.addItem("Data Cap Percentage", AlertType.DATA_CAP_PERCENT.value)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addRow("Alert Type:", self._type_combo)

        # Direction
        self._direction_combo = QComboBox()
        self._direction_combo.addItem("Download", AlertDirection.DOWNLOAD.value)
        self._direction_combo.addItem("Upload", AlertDirection.UPLOAD.value)
        self._direction_combo.addItem("Both", AlertDirection.BOTH.value)
        layout.addRow("Direction:", self._direction_combo)

        # Threshold
        self._threshold_layout = QHBoxLayout()
        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setRange(0.0, 1000000000.0)
        self._threshold_spin.setDecimals(2)
        self._threshold_spin.setValue(100.0)
        self._threshold_layout.addWidget(self._threshold_spin)

        self._threshold_unit = QComboBox()
        self._threshold_unit.addItems(["B/s", "KB/s", "MB/s", "GB/s", "B", "KB", "MB", "GB", "%"])
        self._threshold_unit.setCurrentIndex(2)  # Default to MB/s
        self._threshold_layout.addWidget(self._threshold_unit)
        self._threshold_layout.addStretch()

        layout.addRow("Threshold:", self._threshold_layout)

        # Period (for volume alerts)
        self._period_spin = QSpinBox()
        self._period_spin.setRange(1, 1440)
        self._period_spin.setValue(60)
        self._period_spin.setSuffix(" minutes")
        layout.addRow("Period:", self._period_spin)

        # Cooldown
        self._cooldown_spin = QSpinBox()
        self._cooldown_spin.setRange(1, 1440)
        self._cooldown_spin.setValue(30)
        self._cooldown_spin.setSuffix(" minutes")
        layout.addRow("Cooldown:", self._cooldown_spin)

        # Notification options
        self._notify_desktop_check = QCheckBox("Desktop notification")
        self._notify_desktop_check.setChecked(True)
        layout.addRow("Notify:", self._notify_desktop_check)

        # Initial state
        self._on_type_changed(0)

    def _on_type_changed(self, index: int) -> None:
        """Update UI based on alert type."""
        alert_type = AlertType(self._type_combo.currentData())
        is_rate = alert_type == AlertType.RATE_THRESHOLD
        is_volume = alert_type == AlertType.VOLUME_THRESHOLD
        is_percent = alert_type == AlertType.DATA_CAP_PERCENT

        # Update unit options
        self._threshold_unit.clear()
        if is_rate:
            self._threshold_unit.addItems(["B/s", "KB/s", "MB/s", "GB/s"])
            self._threshold_unit.setCurrentIndex(2)
        elif is_volume:
            self._threshold_unit.addItems(["B", "KB", "MB", "GB"])
            self._threshold_unit.setCurrentIndex(2)
        else:
            self._threshold_unit.addItems(["%"])
            self._threshold_spin.setRange(0.0, 100.0)
            self._threshold_spin.setValue(80.0)

        # Show/hide period
        self._period_spin.setEnabled(is_volume)

        # Show/hide direction (not applicable for data cap percent)
        self._direction_combo.setEnabled(not is_percent)

    def _load_rule(self, rule: AlertRule) -> None:
        """Load rule values into editor."""
        self._rule = rule
        self._name_edit.setText(rule.name)
        self._enabled_check.setChecked(rule.enabled)

        # Set type
        type_index = self._type_combo.findData(rule.alert_type.value)
        if type_index >= 0:
            self._type_combo.setCurrentIndex(type_index)

        # Set direction
        dir_index = self._direction_combo.findData(rule.direction.value)
        if dir_index >= 0:
            self._direction_combo.setCurrentIndex(dir_index)

        # Set threshold
        self._period_spin.setValue(rule.period_minutes)
        self._cooldown_spin.setValue(rule.cooldown_minutes)
        self._notify_desktop_check.setChecked(rule.notify_desktop)

        # Convert threshold to appropriate unit
        self._set_threshold_value(rule.threshold, rule.alert_type)

    def _set_threshold_value(self, value: float, alert_type: AlertType) -> None:
        """Set threshold value with appropriate unit conversion."""
        if alert_type == AlertType.RATE_THRESHOLD:
            # Find best unit for rate
            if value >= 1024 ** 3:
                self._threshold_spin.setValue(value / (1024 ** 3))
                self._threshold_unit.setCurrentIndex(3)  # GB/s
            elif value >= 1024 ** 2:
                self._threshold_spin.setValue(value / (1024 ** 2))
                self._threshold_unit.setCurrentIndex(2)  # MB/s
            elif value >= 1024:
                self._threshold_spin.setValue(value / 1024)
                self._threshold_unit.setCurrentIndex(1)  # KB/s
            else:
                self._threshold_spin.setValue(value)
                self._threshold_unit.setCurrentIndex(0)  # B/s
        elif alert_type == AlertType.VOLUME_THRESHOLD:
            # Find best unit for volume
            if value >= 1024 ** 3:
                self._threshold_spin.setValue(value / (1024 ** 3))
                self._threshold_unit.setCurrentIndex(3)  # GB
            elif value >= 1024 ** 2:
                self._threshold_spin.setValue(value / (1024 ** 2))
                self._threshold_unit.setCurrentIndex(2)  # MB
            elif value >= 1024:
                self._threshold_spin.setValue(value / 1024)
                self._threshold_unit.setCurrentIndex(1)  # KB
            else:
                self._threshold_spin.setValue(value)
                self._threshold_unit.setCurrentIndex(0)  # B
        else:
            # Percentage
            self._threshold_spin.setValue(value)

    def get_rule(self) -> AlertRule:
        """Get the edited rule."""
        # Calculate threshold in base units
        threshold = self._threshold_spin.value()
        unit = self._threshold_unit.currentText()
        alert_type = AlertType(self._type_combo.currentData())

        if alert_type == AlertType.RATE_THRESHOLD:
            if unit == "KB/s":
                threshold *= 1024
            elif unit == "MB/s":
                threshold *= 1024 ** 2
            elif unit == "GB/s":
                threshold *= 1024 ** 3
        elif alert_type == AlertType.VOLUME_THRESHOLD:
            if unit == "KB":
                threshold *= 1024
            elif unit == "MB":
                threshold *= 1024 ** 2
            elif unit == "GB":
                threshold *= 1024 ** 3

        if self._rule:
            rule = self._rule
        else:
            rule = AlertRule(id=str(uuid.uuid4())[:8], name="")

        rule.name = self._name_edit.text().strip() or "Unnamed Rule"
        rule.enabled = self._enabled_check.isChecked()
        rule.alert_type = alert_type
        rule.direction = AlertDirection(self._direction_combo.currentData())
        rule.threshold = threshold
        rule.period_minutes = self._period_spin.value()
        rule.cooldown_minutes = self._cooldown_spin.value()
        rule.notify_desktop = self._notify_desktop_check.isChecked()

        return rule


class SettingsDialog(QDialog):
    """Configuration dialog for NetScope settings."""

    # Signal emitted when settings are saved
    settings_saved = pyqtSignal(dict)
    alerts_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NetScope Settings")
        self.setMinimumSize(500, 450)
        self.setModal(True)

        # Load current config
        self._config = load_config()

        # Alert manager
        self._alert_manager = get_alert_manager()

        # Build UI
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Create tabs
        self._tabs.addTab(self._create_general_tab(), "General")
        self._tabs.addTab(self._create_data_cap_tab(), "Data Cap")
        self._tabs.addTab(self._create_alerts_tab(), "Alert Rules")
        self._tabs.addTab(self._create_display_tab(), "Display")

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self._on_ok)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)

        layout.addWidget(button_box)

        # Config file path label
        path_label = QLabel(f"<small>Config file: {CONFIG_FILE}</small>")
        path_label.setStyleSheet("color: gray;")
        layout.addWidget(path_label)

    def _create_general_tab(self) -> QWidget:
        """Create the General settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Network settings group
        network_group = QGroupBox("Network Settings")
        network_layout = QFormLayout(network_group)

        # Interface selection
        self._interface_combo = QComboBox()
        self._interface_combo.setEditable(True)
        self._interface_combo.addItem("auto (auto-detect)")
        self._interface_combo.setCurrentText("auto")
        network_layout.addRow("Network Interface:", self._interface_combo)

        # LAN subnet
        self._lan_subnet_edit = QLineEdit()
        self._lan_subnet_edit.setPlaceholderText("e.g., 192.168.0.0/20")
        network_layout.addRow("LAN Subnet:", self._lan_subnet_edit)

        layout.addWidget(network_group)

        # Update intervals group
        interval_group = QGroupBox("Update Intervals")
        interval_layout = QFormLayout(interval_group)

        # Bandwidth update interval
        self._bandwidth_interval_spin = QDoubleSpinBox()
        self._bandwidth_interval_spin.setRange(0.5, 10.0)
        self._bandwidth_interval_spin.setSingleStep(0.5)
        self._bandwidth_interval_spin.setSuffix(" seconds")
        interval_layout.addRow("Bandwidth Update:", self._bandwidth_interval_spin)

        # Connection update interval
        self._connection_interval_spin = QDoubleSpinBox()
        self._connection_interval_spin.setRange(0.5, 30.0)
        self._connection_interval_spin.setSingleStep(0.5)
        self._connection_interval_spin.setSuffix(" seconds")
        interval_layout.addRow("Connection Scan:", self._connection_interval_spin)

        layout.addWidget(interval_group)

        layout.addStretch()
        return widget

    def _create_data_cap_tab(self) -> QWidget:
        """Create the Data Cap settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Enable checkbox
        self._data_cap_enabled_check = QCheckBox("Enable Data Cap Tracking")
        self._data_cap_enabled_check.toggled.connect(self._on_data_cap_toggled)
        layout.addWidget(self._data_cap_enabled_check)

        # Data cap settings group
        self._data_cap_group = QGroupBox("Data Cap Settings")
        data_cap_layout = QFormLayout(self._data_cap_group)

        # Data cap threshold
        self._data_cap_spin = QDoubleSpinBox()
        self._data_cap_spin.setRange(1.0, 10000.0)
        self._data_cap_spin.setSuffix(" GB")
        self._data_cap_spin.setDecimals(1)
        data_cap_layout.addRow("Monthly Data Cap:", self._data_cap_spin)

        layout.addWidget(self._data_cap_group)

        # Warning thresholds group
        warning_group = QGroupBox("Warning Thresholds")
        warning_layout = QVBoxLayout(warning_group)

        self._warn_50_check = QCheckBox("Warn at 50% usage")
        self._warn_75_check = QCheckBox("Warn at 75% usage")
        self._warn_90_check = QCheckBox("Warn at 90% usage")

        warning_layout.addWidget(self._warn_50_check)
        warning_layout.addWidget(self._warn_75_check)
        warning_layout.addWidget(self._warn_90_check)

        layout.addWidget(warning_group)

        # Info label
        info_label = QLabel(
            "<small>Data cap is tracked from boot time. "
            "Reset monthly by clearing iptables counters.</small>"
        )
        info_label.setStyleSheet("color: gray;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()
        return widget

    def _create_alerts_tab(self) -> QWidget:
        """Create the Alert Rules settings tab."""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Left side: rule list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Alert Rules:"))

        self._rules_list = QListWidget()
        self._rules_list.currentRowChanged.connect(self._on_rule_selected)
        left_layout.addWidget(self._rules_list)

        # Buttons
        btn_layout = QHBoxLayout()
        self._add_rule_btn = QPushButton("Add")
        self._add_rule_btn.clicked.connect(self._on_add_rule)
        btn_layout.addWidget(self._add_rule_btn)

        self._remove_rule_btn = QPushButton("Remove")
        self._remove_rule_btn.clicked.connect(self._on_remove_rule)
        btn_layout.addWidget(self._remove_rule_btn)

        left_layout.addLayout(btn_layout)

        layout.addWidget(left_panel, 1)

        # Right side: rule editor
        self._rule_editor = AlertRuleEditor()
        layout.addWidget(self._rule_editor, 2)

        # Load rules
        self._load_rules()

        return widget

    def _create_display_tab(self) -> QWidget:
        """Create the Display settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Window settings group
        window_group = QGroupBox("Window Settings")
        window_layout = QVBoxLayout(window_group)

        self._start_minimized_check = QCheckBox("Start minimized to system tray")
        window_layout.addWidget(self._start_minimized_check)

        layout.addWidget(window_group)

        # Traffic display group
        traffic_group = QGroupBox("Traffic Display")
        traffic_layout = QVBoxLayout(traffic_group)

        self._show_lan_check = QCheckBox("Show LAN traffic separately")
        traffic_layout.addWidget(self._show_lan_check)

        layout.addWidget(traffic_group)

        # Info about changes
        info_label = QLabel(
            "<small>Some changes may require restarting the application to take effect.</small>"
        )
        info_label.setStyleSheet("color: gray;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()
        return widget

    def _load_rules(self) -> None:
        """Load alert rules into list."""
        self._rules_list.clear()
        for rule in self._alert_manager.get_rules():
            item = QListWidgetItem(f"{'✓' if rule.enabled else '○'} {rule.name}")
            item.setData(Qt.ItemDataRole.UserRole, rule.id)
            self._rules_list.addItem(item)

        if self._rules_list.count() > 0:
            self._rules_list.setCurrentRow(0)

    def _on_rule_selected(self, row: int) -> None:
        """Handle rule selection."""
        if row < 0:
            return

        item = self._rules_list.item(row)
        rule_id = item.data(Qt.ItemDataRole.UserRole)

        for rule in self._alert_manager.get_rules():
            if rule.id == rule_id:
                self._rule_editor._load_rule(rule)
                break

    def _on_add_rule(self) -> None:
        """Add a new alert rule."""
        rule = AlertRule(
            id=str(uuid.uuid4())[:8],
            name="New Alert Rule",
            enabled=False,
        )
        self._alert_manager.add_rule(rule)
        self._load_rules()

        # Select the new rule
        self._rules_list.setCurrentRow(self._rules_list.count() - 1)

    def _on_remove_rule(self) -> None:
        """Remove the selected alert rule."""
        row = self._rules_list.currentRow()
        if row < 0:
            return

        item = self._rules_list.item(row)
        rule_id = item.data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this alert rule?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._alert_manager.remove_rule(rule_id)
            self._load_rules()

    def _load_settings(self) -> None:
        """Load settings from config into UI."""
        # General tab
        interface = self._config.get("interface", "auto")
        if interface == "auto":
            self._interface_combo.setCurrentIndex(0)
        else:
            self._interface_combo.setCurrentText(interface)

        self._lan_subnet_edit.setText(self._config.get("lan_subnet", "192.168.0.0/20"))
        self._bandwidth_interval_spin.setValue(self._config.get("update_interval", 1.0))
        self._connection_interval_spin.setValue(self._config.get("connection_interval", 2.0))

        # Data cap tab
        self._data_cap_enabled_check.setChecked(self._config.get("data_cap_enabled", False))
        self._data_cap_spin.setValue(self._config.get("data_cap_gb", 100.0))
        self._warn_50_check.setChecked(self._config.get("data_cap_warn_50", True))
        self._warn_75_check.setChecked(self._config.get("data_cap_warn_75", True))
        self._warn_90_check.setChecked(self._config.get("data_cap_warn_90", True))

        self._on_data_cap_toggled(self._data_cap_enabled_check.isChecked())

        # Display tab
        self._start_minimized_check.setChecked(self._config.get("start_minimized", False))
        self._show_lan_check.setChecked(self._config.get("show_lan_traffic", True))

    def _save_settings(self) -> dict:
        """Save UI settings to config."""
        # Get interface value
        interface = self._interface_combo.currentText()
        if interface.startswith("auto"):
            interface = "auto"

        # Build config
        self._config["interface"] = interface
        self._config["lan_subnet"] = self._lan_subnet_edit.text().strip()
        self._config["update_interval"] = self._bandwidth_interval_spin.value()
        self._config["connection_interval"] = self._connection_interval_spin.value()

        self._config["data_cap_enabled"] = self._data_cap_enabled_check.isChecked()
        self._config["data_cap_gb"] = self._data_cap_spin.value()
        self._config["data_cap_warn_50"] = self._warn_50_check.isChecked()
        self._config["data_cap_warn_75"] = self._warn_75_check.isChecked()
        self._config["data_cap_warn_90"] = self._warn_90_check.isChecked()

        self._config["start_minimized"] = self._start_minimized_check.isChecked()
        self._config["show_lan_traffic"] = self._show_lan_check.isChecked()

        # Save alert rule if one is selected
        if self._rules_list.currentRow() >= 0:
            item = self._rules_list.item(self._rules_list.currentRow())
            rule_id = item.data(Qt.ItemDataRole.UserRole)
            edited_rule = self._rule_editor.get_rule()
            edited_rule.id = rule_id
            self._alert_manager.update_rule(edited_rule)
            self.alerts_changed.emit()

        # Save to file
        save_config(self._config)

        return self._config  # type: ignore[no-any-return]

    def _on_data_cap_toggled(self, enabled: bool) -> None:
        """Enable/disable data cap controls."""
        self._data_cap_group.setEnabled(enabled)

    def _on_ok(self) -> None:
        """Handle OK button - save and close."""
        config = self._save_settings()
        self.settings_saved.emit(config)
        self.accept()

    def _on_apply(self) -> None:
        """Handle Apply button - save without closing."""
        config = self._save_settings()
        self.settings_saved.emit(config)
        self._load_rules()  # Refresh rule list
