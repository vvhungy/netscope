"""Tests for theme switching — verifies all widgets refresh correctly across modes."""

import pytest

from netscope.core.theme import DARK_PALETTE, LIGHT_PALETTE, Theme, ThemeMode


class TestNewPaletteTokens:
    """Verify the graph_bg and graph_border tokens are present in both palettes."""

    def test_dark_palette_has_graph_bg(self):
        assert DARK_PALETTE.graph_bg
        assert DARK_PALETTE.graph_bg.startswith("#")

    def test_dark_palette_has_graph_border(self):
        assert DARK_PALETTE.graph_border
        assert DARK_PALETTE.graph_border.startswith("#")

    def test_light_palette_has_graph_bg(self):
        assert LIGHT_PALETTE.graph_bg
        assert LIGHT_PALETTE.graph_bg.startswith("#")

    def test_light_palette_has_graph_border(self):
        assert LIGHT_PALETTE.graph_border
        assert LIGHT_PALETTE.graph_border.startswith("#")

    def test_dark_graph_bg_distinct_from_bg_primary(self):
        """Graph background must be visually distinct from widget background."""
        assert DARK_PALETTE.graph_bg != DARK_PALETTE.bg_primary
        assert DARK_PALETTE.graph_bg != DARK_PALETTE.bg_secondary

    def test_light_graph_bg_distinct_from_bg_primary(self):
        assert LIGHT_PALETTE.graph_bg != LIGHT_PALETTE.bg_primary
        assert LIGHT_PALETTE.graph_bg != LIGHT_PALETTE.bg_secondary


class TestWidgetThemeSwitch:
    """Verify all widgets with refresh_theme() update without errors on mode change."""

    @pytest.fixture(autouse=True)
    def reset_theme(self):
        yield
        Theme.set_mode(ThemeMode.SYSTEM)

    def _make_widgets(self):
        from netscope.widgets.bandwidth_graph import BandwidthGraph
        from netscope.widgets.bandwidth_panel import BandwidthPanel
        from netscope.widgets.destinations_panel import DestinationsPanel
        from netscope.widgets.historical_graph import HistoricalGraph
        from netscope.widgets.process_bandwidth_table import ProcessBandwidthTable
        from netscope.widgets.process_table import ProcessTable

        return [
            BandwidthPanel(),
            BandwidthGraph(),
            HistoricalGraph(),
            ProcessTable(),
            DestinationsPanel(),
            ProcessBandwidthTable(),
        ]

    def test_dark_to_light(self, qapp):
        """All widgets must refresh without error when switching dark → light."""
        Theme.set_mode(ThemeMode.DARK)
        widgets = self._make_widgets()
        Theme.set_mode(ThemeMode.LIGHT)
        for w in widgets:
            w.refresh_theme()  # Must not raise

    def test_light_to_dark(self, qapp):
        """All widgets must refresh without error when switching light → dark."""
        Theme.set_mode(ThemeMode.LIGHT)
        widgets = self._make_widgets()
        Theme.set_mode(ThemeMode.DARK)
        for w in widgets:
            w.refresh_theme()

    def test_cycle_all_modes(self, qapp):
        """Cycling through all three modes must not raise on any widget."""
        widgets = self._make_widgets()
        for mode in (ThemeMode.DARK, ThemeMode.LIGHT, ThemeMode.SYSTEM, ThemeMode.DARK):
            Theme.set_mode(mode)
            for w in widgets:
                w.refresh_theme()

    def test_bandwidth_graph_paint_after_theme_switch(self, qapp):
        """BandwidthGraph paintEvent must not raise after theme switch."""
        from PyQt6.QtGui import QPainter, QPixmap

        from netscope.widgets.bandwidth_graph import BandwidthGraph

        graph = BandwidthGraph()
        graph.resize(400, 200)

        for mode in (ThemeMode.DARK, ThemeMode.LIGHT):
            Theme.set_mode(mode)
            graph.refresh_theme()
            # Render to offscreen pixmap — verifies paintEvent runs cleanly
            pixmap = QPixmap(graph.size())
            painter = QPainter(pixmap)
            graph.render(painter)
            painter.end()

    def test_historical_graph_paint_after_theme_switch(self, qapp):
        """HistoricalGraph paintEvent must not raise after theme switch."""
        from PyQt6.QtGui import QPainter, QPixmap

        from netscope.widgets.historical_graph import HistoricalGraph

        graph = HistoricalGraph()
        graph.resize(600, 250)

        for mode in (ThemeMode.DARK, ThemeMode.LIGHT):
            Theme.set_mode(mode)
            graph.refresh_theme()
            pixmap = QPixmap(graph.size())
            painter = QPainter(pixmap)
            graph.render(painter)
            painter.end()
