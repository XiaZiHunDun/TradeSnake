"""Tests for metrics enhanced features (trimmed profit/loss ratio)"""

import pytest
from backend.backtester.metrics import Metrics, Trade


class TestTrimExtremes:
    """Test _trim_extremes method"""

    def test_trim_extremes_normal(self):
        """Trim 5% from both ends of normal distribution"""
        values = list(range(1, 101))  # 1 to 100
        trimmed = Metrics._trim_extremes(values, 0.05)
        # 5% of 100 = 5 items removed from each end
        assert len(trimmed) == 90
        assert trimmed[0] == 6
        assert trimmed[-1] == 95

    def test_trim_extremes_small_list(self):
        """Small lists should be returned unchanged"""
        values = [1, 2, 3]
        trimmed = Metrics._trim_extremes(values, 0.05)
        assert trimmed == values

    def test_trim_extremes_empty(self):
        """Empty list returns empty"""
        trimmed = Metrics._trim_extremes([], 0.05)
        assert trimmed == []


class TestTrimmedProfitLossRatio:
    """Test calculate_trimmed_profit_loss_ratio"""

    def test_basic_calculation(self):
        """Basic trimmed profit/loss ratio"""
        trades = [
            Trade('2024-01-01', '2024-01-02', '000001', '股票A', 'buy', 10.0, 100, 1000, profit=100),
            Trade('2024-01-01', '2024-01-02', '000002', '股票B', 'buy', 10.0, 100, 1000, profit=200),
            Trade('2024-01-01', '2024-01-02', '000003', '股票C', 'buy', 10.0, 100, 1000, profit=-50),
            Trade('2024-01-01', '2024-01-02', '000004', '股票D', 'buy', 10.0, 100, 1000, profit=-100),
        ]
        ratio = Metrics.calculate_trimmed_profit_loss_ratio(trades)
        # (100 + 200) / 2 = 150 avg profit, (50 + 100) / 2 = 75 avg loss → 2.0
        assert ratio == 2.0

    def test_with_extreme_values(self):
        """Extreme values should be trimmed"""
        trades = [
            Trade('2024-01-01', '2024-01-02', '000001', '股票A', 'buy', 10.0, 100, 1000, profit=100),
            Trade('2024-01-01', '2024-01-02', '000002', '股票B', 'buy', 10.0, 100, 1000, profit=200),
            Trade('2024-01-01', '2024-01-02', '000003', '股票C', 'buy', 10.0, 100, 1000, profit=10000),  # extreme
            Trade('2024-01-01', '2024-01-02', '000004', '股票D', 'buy', 10.0, 100, 1000, profit=-50),
            Trade('2024-01-01', '2024-01-02', '000005', '股票E', 'buy', 10.0, 100, 1000, profit=-100),
            Trade('2024-01-01', '2024-01-02', '000006', '股票F', 'buy', 10.0, 100, 1000, profit=-5000),  # extreme
        ]
        ratio = Metrics.calculate_trimmed_profit_loss_ratio(trades, trim_pct=0.05)
        # With 6 trades, 5% of 3 profits = 0.15 → max(1, 0) = 1 trimmed from each end
        # After trimming: profits = [100, 200], losses = [50, 100]
        # ratio should be 2.0 (not affected by extremes since we only trim 1 from each)
        assert ratio == 2.0

    def test_no_trades(self):
        """No trades returns 0"""
        ratio = Metrics.calculate_trimmed_profit_loss_ratio([])
        assert ratio == 0.0

    def test_no_profits(self):
        """No profits returns 0"""
        trades = [
            Trade('2024-01-01', '2024-01-02', '000001', '股票A', 'buy', 10.0, 100, 1000, profit=-100),
            Trade('2024-01-01', '2024-01-02', '000002', '股票B', 'buy', 10.0, 100, 1000, profit=-200),
        ]
        ratio = Metrics.calculate_trimmed_profit_loss_ratio(trades)
        assert ratio == 0.0

    def test_no_losses(self):
        """No losses returns 0"""
        trades = [
            Trade('2024-01-01', '2024-01-02', '000001', '股票A', 'buy', 10.0, 100, 1000, profit=100),
            Trade('2024-01-01', '2024-01-02', '000002', '股票B', 'buy', 10.0, 100, 1000, profit=200),
        ]
        ratio = Metrics.calculate_trimmed_profit_loss_ratio(trades)
        assert ratio == 0.0

    def test_trim_pct_respected(self):
        """Different trim_pct values produce valid results"""
        profits = [100, 200, 300, 400, 500, 600, 700, 800, 900, 10000]
        losses = [50, 60, 70, 80, 90, 100, 110, 120, 130, 5000]

        trades = []
        for i, (p, l) in enumerate(zip(profits, losses)):
            trades.append(Trade('2024-01-01', '2024-01-02', f'00000{i}', f'股票{i}', 'buy', 10.0, 100, 1000, profit=p if i < 5 else -l))

        # Both should return valid ratios
        ratio_5pct = Metrics.calculate_trimmed_profit_loss_ratio(trades, trim_pct=0.05)
        ratio_20pct = Metrics.calculate_trimmed_profit_loss_ratio(trades, trim_pct=0.20)
        assert ratio_5pct > 0
        assert ratio_20pct > 0
        # The actual values depend on distribution; just verify both work


class TestCalculateMetricsWithTrimmed:
    """Test that calculate_metrics includes trimmed_profit_loss_ratio"""

    def test_calculate_metrics_includes_trimmed(self):
        """calculate_metrics should include trimmed_profit_loss_ratio in result"""
        equity_curve = {f'2024-01-{i:02d}': 10000 + i * 10 for i in range(1, 31)}
        trades = [
            Trade('2024-01-01', '2024-01-02', '000001', '股票A', 'buy', 10.0, 100, 1000, profit=150),
            Trade('2024-01-01', '2024-01-02', '000002', '股票B', 'buy', 10.0, 100, 1000, profit=150),
            Trade('2024-01-01', '2024-01-02', '000003', '股票C', 'buy', 10.0, 100, 1000, profit=-50),
        ]
        result = Metrics.calculate_metrics(equity_curve, trades=trades)
        assert 'trimmed_profit_loss_ratio' in result
        # avg_profit = (150+150)/2 = 150, avg_loss = 50 → ratio = 3.0
        assert result['trimmed_profit_loss_ratio'] == 3.0
