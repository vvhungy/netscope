"""Unit tests for bandwidth calculation module."""



from netscope.core.bandwidth import BandwidthCalculator, BandwidthStats


class TestBandwidthStats:
    """Tests for BandwidthStats dataclass."""

    def test_default_values(self):
        """Should have all zero defaults."""
        stats = BandwidthStats()
        assert stats.lan_rx_rate == 0.0
        assert stats.lan_tx_rate == 0.0
        assert stats.inet_rx_rate == 0.0
        assert stats.inet_tx_rate == 0.0
        assert stats.lan_rx_total == 0
        assert stats.lan_tx_total == 0
        assert stats.inet_rx_total == 0
        assert stats.inet_tx_total == 0

    def test_total_rx_rate(self):
        """Should sum LAN and internet RX rates."""
        stats = BandwidthStats(lan_rx_rate=100.0, inet_rx_rate=50.0)
        assert stats.total_rx_rate == 150.0

    def test_total_tx_rate(self):
        """Should sum LAN and internet TX rates."""
        stats = BandwidthStats(lan_tx_rate=200.0, inet_tx_rate=75.0)
        assert stats.total_tx_rate == 275.0

    def test_total_rx(self):
        """Should sum all RX totals."""
        stats = BandwidthStats(lan_rx_total=1000, inet_rx_total=500)
        assert stats.total_rx == 1500

    def test_total_tx(self):
        """Should sum all TX totals."""
        stats = BandwidthStats(lan_tx_total=800, inet_tx_total=200)
        assert stats.total_tx == 1000

    def test_inet_rx_percent(self):
        """Should calculate internet RX percentage."""
        stats = BandwidthStats(lan_rx_rate=100.0, inet_rx_rate=100.0)
        assert stats.inet_rx_percent() == 50.0

    def test_inet_rx_percent_zero_total(self):
        """Should return 0 when total is zero."""
        stats = BandwidthStats()
        assert stats.inet_rx_percent() == 0.0

    def test_inet_tx_percent(self):
        """Should calculate internet TX percentage."""
        stats = BandwidthStats(lan_tx_rate=25.0, inet_tx_rate=75.0)
        assert stats.inet_tx_percent() == 75.0


class TestBandwidthCalculator:
    """Tests for BandwidthCalculator class."""

    def test_first_update_returns_zeros(self):
        """First update should return zero rates."""
        calc = BandwidthCalculator()
        counters = {"lan_rx": 1000, "lan_tx": 500, "inet_rx": 2000, "inet_tx": 1000}

        stats = calc.update(counters, current_time=0.0)

        assert stats.lan_rx_rate == 0.0
        assert stats.lan_tx_rate == 0.0
        assert stats.inet_rx_rate == 0.0
        assert stats.inet_tx_rate == 0.0

    def test_calculate_rate_from_delta(self):
        """Should calculate rate from counter delta."""
        calc = BandwidthCalculator()

        # First update
        counters1 = {"lan_rx": 0, "lan_tx": 0, "inet_rx": 0, "inet_tx": 0}
        calc.update(counters1, current_time=0.0)

        # Second update - 1000 bytes in 1 second = 1000 B/s
        counters2 = {"lan_rx": 1000, "lan_tx": 500, "inet_rx": 2000, "inet_tx": 1000}
        stats = calc.update(counters2, current_time=1.0)

        assert stats.lan_rx_rate == 1000.0
        assert stats.lan_tx_rate == 500.0
        assert stats.inet_rx_rate == 2000.0
        assert stats.inet_tx_rate == 1000.0

    def test_accumulate_totals(self):
        """Should accumulate totals across updates."""
        calc = BandwidthCalculator()

        calc.update({"lan_rx": 0, "lan_tx": 0, "inet_rx": 0, "inet_tx": 0}, current_time=0.0)
        calc.update({"lan_rx": 1000, "lan_tx": 500, "inet_rx": 2000, "inet_tx": 1000}, current_time=1.0)
        stats = calc.update({"lan_rx": 2500, "lan_tx": 1200, "inet_rx": 5000, "inet_tx": 2500}, current_time=2.0)

        # Totals should be accumulated
        assert stats.lan_rx_total == 2500
        assert stats.lan_tx_total == 1200
        assert stats.inet_rx_total == 5000
        assert stats.inet_tx_total == 2500

    def test_handle_counter_reset(self):
        """Should handle counter reset (negative delta)."""
        calc = BandwidthCalculator()

        # First update
        calc.update({"lan_rx": 0, "lan_tx": 0, "inet_rx": 0, "inet_tx": 0}, current_time=0.0)

        # Second update
        calc.update({"lan_rx": 10000, "lan_tx": 5000, "inet_rx": 20000, "inet_tx": 10000}, current_time=1.0)

        # Counter reset - should treat as 0 delta
        stats = calc.update({"lan_rx": 100, "lan_tx": 50, "inet_rx": 200, "inet_tx": 100}, current_time=2.0)

        # Rates should be 0 for reset counters
        assert stats.lan_rx_rate == 0.0
        assert stats.lan_tx_rate == 0.0

    def test_reset_clears_state(self):
        """Reset should clear all tracking state."""
        calc = BandwidthCalculator()

        calc.update({"lan_rx": 0, "lan_tx": 0, "inet_rx": 0, "inet_tx": 0}, current_time=0.0)
        calc.update({"lan_rx": 1000, "lan_tx": 500, "inet_rx": 2000, "inet_tx": 1000}, current_time=1.0)

        calc.reset()

        # After reset, should behave like first update
        stats = calc.update({"lan_rx": 5000, "lan_tx": 2000, "inet_rx": 10000, "inet_tx": 5000}, current_time=2.0)
        assert stats.lan_rx_rate == 0.0
        assert stats.lan_rx_total == 0

    def test_use_current_time_if_not_provided(self):
        """Should use time.monotonic() if current_time not provided."""
        calc = BandwidthCalculator()

        calc.update({"lan_rx": 0, "lan_tx": 0, "inet_rx": 0, "inet_tx": 0})
        # Should not raise
        calc.update({"lan_rx": 1000, "lan_tx": 500, "inet_rx": 2000, "inet_tx": 1000})

    def test_partial_counters(self):
        """Should handle missing counter keys gracefully."""
        calc = BandwidthCalculator()

        calc.update({"lan_rx": 0, "lan_tx": 0, "inet_rx": 0, "inet_tx": 0}, current_time=0.0)

        # Missing inet_tx
        stats = calc.update({"lan_rx": 1000, "lan_tx": 500, "inet_rx": 2000}, current_time=1.0)

        # Should still calculate rates for present keys
        assert stats.lan_rx_rate == 1000.0
        assert stats.inet_tx_rate == 0.0
