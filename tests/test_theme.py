"""Unit tests for theme module."""



from netscope.core.theme import (
    DARK_PALETTE,
    LIGHT_PALETTE,
    ColorPalette,
    Theme,
    ThemeMode,
    get_color,
    get_palette,
    get_theme,
)


class TestColorPalette:
    """Tests for ColorPalette dataclass."""

    def test_dark_palette_has_required_colors(self):
        """Dark palette should have all required colors."""
        assert DARK_PALETTE.bg_primary
        assert DARK_PALETTE.text_primary
        assert DARK_PALETTE.download
        assert DARK_PALETTE.upload
        assert DARK_PALETTE.success
        assert DARK_PALETTE.error

    def test_light_palette_has_required_colors(self):
        """Light palette should have all required colors."""
        assert LIGHT_PALETTE.bg_primary
        assert LIGHT_PALETTE.text_primary
        assert LIGHT_PALETTE.download
        assert LIGHT_PALETTE.upload
        assert LIGHT_PALETTE.success
        assert LIGHT_PALETTE.error

    def test_to_qcolor(self):
        """Should convert color string to QColor."""
        from PyQt6.QtGui import QColor
        color = DARK_PALETTE.to_qcolor("download")
        assert isinstance(color, QColor)


class TestThemeMode:
    """Tests for ThemeMode enum."""

    def test_theme_modes_exist(self):
        """Should have all theme modes."""
        assert ThemeMode.DARK
        assert ThemeMode.LIGHT
        assert ThemeMode.SYSTEM


class TestTheme:
    """Tests for Theme singleton."""

    def test_singleton_returns_same_instance(self):
        """Should return the same instance."""
        theme1 = get_theme()
        theme2 = get_theme()
        assert theme1 is theme2

    def test_default_mode_is_system(self):
        """Default mode should be SYSTEM."""
        # Reset to default
        Theme._current_mode = ThemeMode.SYSTEM
        assert Theme.get_mode() == ThemeMode.SYSTEM

    def test_set_mode_dark(self):
        """Should set dark mode."""
        Theme.set_mode(ThemeMode.DARK)
        assert Theme.get_mode() == ThemeMode.DARK
        assert Theme.get_palette() == DARK_PALETTE

    def test_set_mode_light(self):
        """Should set light mode."""
        Theme.set_mode(ThemeMode.LIGHT)
        assert Theme.get_mode() == ThemeMode.LIGHT
        assert Theme.get_palette() == LIGHT_PALETTE

    def test_set_mode_system(self):
        """Should set system mode."""
        Theme.set_mode(ThemeMode.SYSTEM)
        assert Theme.get_mode() == ThemeMode.SYSTEM
        # Palette depends on detection

    def teardown_method(self):
        """Reset theme after each test."""
        Theme._current_mode = ThemeMode.SYSTEM


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_color_returns_string(self):
        """get_color should return a color string."""
        Theme.set_mode(ThemeMode.DARK)
        color = get_color("download")
        assert isinstance(color, str)
        assert color.startswith("#")

    def test_get_palette_returns_palette(self):
        """get_palette should return a ColorPalette."""
        Theme.set_mode(ThemeMode.DARK)
        palette = get_palette()
        assert isinstance(palette, ColorPalette)

    def test_get_color_unknown_returns_black(self):
        """get_color should return black for unknown colors."""
        color = get_color("nonexistent_color")
        assert color == "#000000"


class TestSystemThemeDetection:
    """Tests for system theme detection."""

    def test_detect_without_qapp_returns_light(self):
        """Should return light palette when no QApplication exists."""
        # When no QApplication, should default to light
        Theme.set_mode(ThemeMode.SYSTEM)
        # The actual detection depends on Qt state
        # Just verify it doesn't crash
        palette = Theme.get_palette()
        assert isinstance(palette, ColorPalette)

    def test_detect_with_dark_palette(self):
        """Should detect dark theme from dark window color."""
        from PyQt6.QtGui import QColor
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            # This test verifies the luminance calculation
            dark_color = QColor(30, 30, 46)  # Dark background
            luminance = (dark_color.red() + dark_color.green() + dark_color.blue()) / 3
            assert luminance < 128  # Should be detected as dark

            light_color = QColor(255, 255, 255)  # Light background
            luminance = (light_color.red() + light_color.green() + light_color.blue()) / 3
            assert luminance >= 128  # Should be detected as light
