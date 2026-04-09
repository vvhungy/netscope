"""Application entry point."""

import os
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from .config import load_config
from .widgets.tray_icon import TrayIcon
from .windows import MainWindow

# Try to load app icon from resources
try:
    from .resources import get_app_icon
    _HAS_RESOURCE_ICONS = True
except ImportError:
    _HAS_RESOURCE_ICONS = False


def check_dependencies() -> bool:
    """Check that required system tools are available."""
    # Check for ip command
    if not os.path.exists("/usr/bin/ip") and not os.path.exists("/sbin/ip"):
        QMessageBox.critical(
            None,
            "Missing Dependency",
            "The 'ip' command is required but not found.\n"
            "Please install iproute2 package."
        )
        return False

    # Check for iptables
    if not os.path.exists("/usr/bin/iptables") and not os.path.exists("/sbin/iptables"):
        QMessageBox.critical(
            None,
            "Missing Dependency",
            "iptables is required but not found.\n"
            "Please install iptables package."
        )
        return False

    return True


def main() -> int:
    """Main entry point."""
    # Check for sudo early
    if os.geteuid() != 0:
        print("[warning] Not running as root - sudo password will be required for iptables.")
        print("          Some process names may show as 'unknown'.")

    # Create application
    app = QApplication(sys.argv)
    from . import __version__
    app.setApplicationName("NetScope")
    app.setApplicationVersion(__version__)

    # Use Fusion style for consistent cross-platform appearance
    app.setStyle("Fusion")

    # Load config and initialize theme BEFORE creating widgets.
    # apply_to_qapp (called inside set_mode) pushes our palette into
    # QApplication AFTER Fusion is set, so Fusion renders with our colors.
    config = load_config()
    theme_name = config.get("theme", "system")
    from .core.theme import Theme, ThemeMode
    mode_map = {
        "dark": ThemeMode.DARK,
        "light": ThemeMode.LIGHT,
        "system": ThemeMode.SYSTEM,
    }
    Theme.set_mode(mode_map.get(theme_name, ThemeMode.SYSTEM))

    # Check dependencies
    if not check_dependencies():
        return 1

    # Create main window (after theme is initialized)
    window = MainWindow()

    # Set window icon
    if _HAS_RESOURCE_ICONS:
        window.setWindowIcon(get_app_icon())

    # Create and show system tray icon
    tray_icon = TrayIcon(window)
    window.tray_icon = tray_icon

    # Connect tray icon signals
    tray_icon.show_settings_requested.connect(window._on_settings_requested)

    tray_icon.show()

    config = load_config()
    if not config.get("start_minimized", False):
        window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
