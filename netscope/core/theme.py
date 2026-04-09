"""Theme and color management for NetScope.

Provides a centralized color palette with support for:
- Dark theme
- Light theme
- System theme detection (via Qt)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication


class ThemeMode(Enum):
    """Theme mode selection."""
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


@dataclass
class ColorPalette:
    """Color palette for a theme."""
    # Background colors
    bg_primary: str       # Main background
    bg_secondary: str     # Card/panel background
    bg_tertiary: str      # Input/hover background

    # Text colors
    text_primary: str     # Main text
    text_secondary: str   # Muted text
    text_disabled: str    # Disabled state

    # Accent colors
    accent_primary: str   # Primary accent (buttons, highlights)
    accent_secondary: str # Secondary accent

    # Status colors
    success: str          # Success/positive (download)
    warning: str          # Warning
    error: str            # Error/negative
    info: str             # Info/neutral

    # Traffic colors
    download: str         # Download traffic
    upload: str           # Upload traffic
    lan: str              # LAN traffic
    internet: str         # Internet traffic

    # UI colors
    border: str           # Borders
    separator: str        # Separators
    highlight: str        # Selection highlight

    # Graph colors
    graph_bg: str         # Graph canvas background (high contrast vs bg_primary)
    graph_border: str     # Graph grid lines (visible against graph_bg)

    def to_qcolor(self, color_name: str) -> QColor:
        """Convert a color name to QColor."""
        color_str = getattr(self, color_name, "#000000")
        return QColor(color_str)


# Dark theme palette
DARK_PALETTE = ColorPalette(
    # Background
    bg_primary="#1a1a2e",
    bg_secondary="#16213e",
    bg_tertiary="#0f3460",

    # Text
    text_primary="#e4e4e7",
    text_secondary="#a1a1aa",
    text_disabled="#52525b",

    # Accent
    accent_primary="#6366f1",
    accent_secondary="#818cf8",

    # Status
    success="#22c55e",
    warning="#f59e0b",
    error="#ef4444",
    info="#3b82f6",

    # Traffic
    download="#4ade80",   # Green
    upload="#f97316",     # Orange
    lan="#06b6d4",        # Cyan
    internet="#8b5cf6",   # Purple

    # UI
    border="#27272a",
    separator="#3f3f46",
    highlight="#6366f1",

    # Graph
    graph_bg="#0d1117",
    graph_border="#3d3d50",
)

# Light theme palette
LIGHT_PALETTE = ColorPalette(
    # Background
    bg_primary="#ffffff",
    bg_secondary="#f4f4f5",
    bg_tertiary="#e4e4e7",

    # Text
    text_primary="#18181b",
    text_secondary="#52525b",
    text_disabled="#a1a1aa",

    # Accent
    accent_primary="#6366f1",
    accent_secondary="#4f46e5",

    # Status
    success="#16a34a",
    warning="#d97706",
    error="#dc2626",
    info="#2563eb",

    # Traffic
    download="#16a34a",   # Green
    upload="#ea580c",     # Orange
    lan="#0891b2",        # Cyan
    internet="#7c3aed",   # Purple

    # UI
    border="#d4d4d8",
    separator="#a1a1aa",
    highlight="#6366f1",

    # Graph
    graph_bg="#e8e8ec",
    graph_border="#a0a0b0",
)


class Theme:
    """Theme manager for NetScope."""

    _instance: Optional["Theme"] = None
    _current_mode: ThemeMode = ThemeMode.SYSTEM
    _current_palette: ColorPalette = DARK_PALETTE

    def __new__(cls) -> "Theme":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_mode(cls) -> ThemeMode:
        """Get current theme mode."""
        return cls._current_mode

    @classmethod
    def set_mode(cls, mode: ThemeMode) -> None:
        """Set theme mode and push palette to QApplication."""
        cls._current_mode = mode
        cls._update_palette()
        cls.apply_to_qapp()

    @classmethod
    def _update_palette(cls) -> None:
        """Update palette based on mode."""
        if cls._current_mode == ThemeMode.DARK:
            cls._current_palette = DARK_PALETTE
        elif cls._current_mode == ThemeMode.LIGHT:
            cls._current_palette = LIGHT_PALETTE
        else:
            # System: detect from Qt
            cls._current_palette = cls._detect_system_theme()

    @classmethod
    def _detect_system_theme(cls) -> ColorPalette:
        """Detect system theme preference.

        Checks in order:
        1. GNOME gsettings color-scheme — freedesktop standard, correct on GNOME/Wayland/X11
        2. GTK theme name fallback for older GNOME without color-scheme key
        3. KDE Plasma look-and-feel package name
        4. GTK_THEME environment variable
        5. Qt styleHints().colorScheme() — fallback for non-Linux or other DEs
        """
        import subprocess, os

        # When running under sudo, gsettings queries root's dconf database
        # (which has no GNOME settings).  We need to query as the real user.
        sudo_user = os.environ.get("SUDO_USER")
        sudo_uid = os.environ.get("SUDO_UID")

        def _gsettings(key: str) -> str:
            """Run gsettings, querying the real user when running under sudo."""
            cmd = ["gsettings", "get", "org.gnome.desktop.interface", key]
            # Under sudo, root's gsettings returns 'default' (no real preference).
            # Query the original user directly via sudo -u / runuser.
            if sudo_user:
                env = os.environ.copy()
                if sudo_uid:
                    env.setdefault(
                        "DBUS_SESSION_BUS_ADDRESS",
                        f"unix:path=/run/user/{sudo_uid}/bus",
                    )
                # Try runuser first (doesn't need password), then sudo -u
                for run_cmd in [
                    ["runuser", "-u", sudo_user, "--"] + cmd,
                    ["sudo", "-u", sudo_user, "--preserve-env=DBUS_SESSION_BUS_ADDRESS"] + cmd,
                ]:
                    try:
                        result = subprocess.run(
                            run_cmd, capture_output=True, text=True, timeout=2, env=env,
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            return result.stdout.strip().strip("'").lower()
                    except Exception:
                        continue
                return ""
            # Not under sudo — query directly
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().strip("'").lower()
            return ""

        # Method 1: GNOME color-scheme key (GNOME 42+, most reliable on Linux)
        try:
            scheme = _gsettings("color-scheme")
            if "dark" in scheme:
                return DARK_PALETTE
            if "light" in scheme or scheme == "default":
                return LIGHT_PALETTE
        except Exception:
            pass

        # Method 2: GTK theme name (older GNOME / Ubuntu)
        try:
            gtk_theme = _gsettings("gtk-theme")
            if "dark" in gtk_theme:
                return DARK_PALETTE
        except Exception:
            pass

        # Method 3: KDE Plasma look-and-feel
        try:
            result = subprocess.run(
                ["kreadconfig5", "--file", "kdeglobals", "--group", "KDE",
                 "--key", "LookAndFeelPackage"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and "dark" in result.stdout.lower():
                return DARK_PALETTE
        except Exception:
            pass

        # Method 4: GTK_THEME environment variable
        gtk_theme_env = os.environ.get("GTK_THEME", "").lower()
        if "dark" in gtk_theme_env:
            return DARK_PALETTE
        if gtk_theme_env:
            return LIGHT_PALETTE

        # Method 5: Qt styleHints — useful on macOS/Windows or non-GNOME/KDE DEs
        try:
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QGuiApplication
            app = QGuiApplication.instance()
            if isinstance(app, QGuiApplication):
                hints = app.styleHints()
                if hints is not None:
                    qt_scheme = hints.colorScheme()
                    if qt_scheme == Qt.ColorScheme.Dark:
                        return DARK_PALETTE
                    if qt_scheme == Qt.ColorScheme.Light:
                        return LIGHT_PALETTE
        except Exception:
            pass

        # Default to light
        return LIGHT_PALETTE

    @classmethod
    def apply_to_qapp(cls) -> None:
        """Push the current palette into QApplication so native widgets
        (scrollbars, menus, QTableWidget, QProgressBar, etc.) also respond
        to theme changes.
        """
        try:
            from PyQt6.QtGui import QPalette, QColor as _QColor
            from PyQt6.QtWidgets import QApplication as _QApp
            app = _QApp.instance()
            if not isinstance(app, _QApp):
                return

            p = cls.get_palette()
            pal = QPalette()

            def c(name: str) -> _QColor:
                return _QColor(getattr(p, name))

            # Window / panel backgrounds
            pal.setColor(QPalette.ColorRole.Window,         c("bg_primary"))
            pal.setColor(QPalette.ColorRole.Base,           c("bg_secondary"))
            pal.setColor(QPalette.ColorRole.AlternateBase,  c("bg_tertiary"))
            pal.setColor(QPalette.ColorRole.Button,         c("bg_secondary"))
            pal.setColor(QPalette.ColorRole.ToolTipBase,    c("bg_tertiary"))

            # Text
            pal.setColor(QPalette.ColorRole.WindowText,     c("text_primary"))
            pal.setColor(QPalette.ColorRole.Text,           c("text_primary"))
            pal.setColor(QPalette.ColorRole.ButtonText,     c("text_primary"))
            pal.setColor(QPalette.ColorRole.BrightText,     c("text_primary"))
            pal.setColor(QPalette.ColorRole.ToolTipText,    c("text_primary"))
            pal.setColor(QPalette.ColorRole.PlaceholderText, c("text_disabled"))

            # Accent / selection
            pal.setColor(QPalette.ColorRole.Highlight,      c("highlight"))
            pal.setColor(QPalette.ColorRole.HighlightedText, _QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.Link,           c("accent_primary"))

            # Borders / decorations
            pal.setColor(QPalette.ColorRole.Mid,            c("separator"))
            pal.setColor(QPalette.ColorRole.Dark,           c("border"))
            pal.setColor(QPalette.ColorRole.Shadow,         c("border"))
            pal.setColor(QPalette.ColorRole.Midlight,       c("bg_tertiary"))
            pal.setColor(QPalette.ColorRole.Light,          c("bg_tertiary"))

            app.setPalette(pal)
        except Exception:
            pass

    @classmethod
    def get_palette(cls) -> ColorPalette:
        """Get current color palette."""
        if cls._current_mode == ThemeMode.SYSTEM:
            cls._update_palette()
        return cls._current_palette

    @classmethod
    def is_dark(cls) -> bool:
        """Check if current theme is dark."""
        return cls.get_palette() == DARK_PALETTE

    @classmethod
    def color(cls, name: str) -> str:
        """Get a color by name from current palette."""
        return getattr(cls.get_palette(), name, "#000000")

    @classmethod
    def qcolor(cls, name: str) -> QColor:
        """Get a QColor by name from current palette."""
        return cls.get_palette().to_qcolor(name)


def get_theme() -> Theme:
    """Get the theme singleton."""
    return Theme()


def get_color(name: str) -> str:
    """Convenience function to get a color string."""
    return Theme.color(name)


def get_qcolor(name: str) -> QColor:
    """Convenience function to get a QColor."""
    return Theme.qcolor(name)


def get_palette() -> ColorPalette:
    """Convenience function to get current color palette."""
    return Theme.get_palette()


# Style helper functions
def panel_style() -> str:
    """Get standard panel style."""
    p = Theme.get_palette()
    return f"""
        QGroupBox {{
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 8px;
            color: {p.text_primary};
            font-weight: bold;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: {p.text_secondary};
        }}
    """


def table_style() -> str:
    """Get standard table style."""
    p = Theme.get_palette()
    return f"""
        QTableWidget {{
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            gridline-color: {p.border};
            color: {p.text_primary};
        }}
        QTableWidget::item {{
            padding: 4px;
        }}
        QTableWidget::item:selected {{
            background-color: {p.highlight};
        }}
        QHeaderView::section {{
            background-color: {p.bg_tertiary};
            color: {p.text_secondary};
            padding: 4px;
            border: none;
            border-bottom: 1px solid {p.border};
            font-weight: bold;
        }}
    """


def button_style() -> str:
    """Get standard button style."""
    p = Theme.get_palette()
    return f"""
        QPushButton {{
            background-color: {p.accent_primary};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {p.accent_secondary};
        }}
        QPushButton:disabled {{
            background-color: {p.bg_tertiary};
            color: {p.text_disabled};
        }}
    """
