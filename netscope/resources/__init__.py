"""Resource loading utilities."""

from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap

# Resource directory
RESOURCES_DIR = Path(__file__).parent
ICONS_DIR = RESOURCES_DIR / "icons"


def get_icon_path(name: str) -> Path:
    """Get path to an icon file."""
    return ICONS_DIR / name


def load_icon(name: str) -> QIcon:
    """Load an SVG icon from resources."""
    path = get_icon_path(name)
    if path.exists():
        return QIcon(str(path))
    return QIcon()


def load_pixmap(name: str, size: QSize | None = None) -> QPixmap:
    """Load an SVG as a pixmap with optional size."""
    path = get_icon_path(name)
    if not path.exists():
        return QPixmap()

    if size:
        return QPixmap(str(path)).scaled(
            size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    return QPixmap(str(path))


def get_app_icon() -> QIcon:
    """Get the main application icon."""
    return load_icon("app-icon.svg")


def get_tray_icon() -> QIcon:
    """Get the system tray icon."""
    return load_icon("tray-icon.svg")
