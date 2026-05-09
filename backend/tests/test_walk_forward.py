"""Walk-forward 回测验证体系测试"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from backend.backtester.walk_forward import (
    WalkForwardBacktester, WalkForwardConfig, WalkForwardReport, FoldMetrics,
)
from backend.backtester.benchmark import BenchmarkProvider
from backend.backtester.metrics import Metrics


class TestWalkForwardConfig:
    def test_defaults(self):
        c = WalkForwardConfig()
        assert c.train_window == 120
        assert c.test_window == 20
        assert c.top_n == 6
        assert c.stop_loss == -0.07

    def test_custom(self):
        c = WalkForwardConfig(train_window=60, test_window=10, top_n=10)
        assert c.train_window == 60
        assert c.top_n == 10


class TestWindowGeneration:
    def test_basic(self):
        bt = WalkForwardBacktester(WalkForwardConfig(train_window=5, test_window=2, step_size=2))
        dates = [f"2026-01-{d:02d}" for d in range(1, 21)]
        windows = bt._generate_windows(dates)
        assert len(windows) >= 1
        for train, test in windows:
            assert len(train) == 5
            assert len(test) == 2

    def test_no_overlap(self):
        bt = WalkForwardBacktester(WalkForwardConfig(train_window=5, test_window=3, step_size=3))
        dates = list(range(20))
        dates_str = [f"2026-01-{d+1:02d}" for d in dates]
        windows = bt._generate_windows(dates_str)
        for train, test in windows:
            assert train[-1] < test[0]

    def test_empty(self):
        bt = WalkForwardBacktester(WalkForwardConfig(train_window=120, test_window=20))
        assert bt._generate_windows([]) == []

    def test_insufficient(self):
        bt = WalkForwardBacktester(WalkForwardConfig(train_window=120, test_window=20))
        dates = [f"2026-01-{d:02d}" for d in range(1, 20)]
        assert bt._generate_windows(dates) == []


class TestMaxDrawdown:
    def test_no_drawdown(self):
        cum = np.array([1.0, 1.1, 1.2, 1.3])
        dd = WalkForwardBacktester._max_drawdown(cum)
        assert dd == 0.0

    def test_full_drawdown(self):
        cum = np.array([1.0, 0.8, 0.5, 0.7])
        dd = WalkForwardBacktester._max_drawdown(cum)
        assert abs(dd - 0.5) < 0.01

    def test_empty(self):
        assert WalkForwardBacktester._max_drawdown(np.array([])) == 0.0


class TestFoldSharpe:
    def test_positive_returns(self):
        rets = [0.01] * 20
        sharpe = WalkForwardBacktester._fold_sharpe(rets)
        assert sharpe > 0

    def test_negative_returns(self):
        rets = [-0.01] * 20
        sharpe = WalkForwardBacktester._fold_sharpe(rets)
        assert sharpe < 0

    def test_single_return(self):
        assert WalkForwardBacktester._fold_sharpe([0.01]) == 0.0


class TestReportSummary:
    def test_summary_string(self):
        report = WalkForwardReport(config=WalkForwardConfig())
        report.total_return = 15.5
        report.annual_return = 12.3
        report.sharpe = 1.2
        s = report.summary()
        assert "15.50%" in s
        assert "12.30%" in s
        assert "1.20" in s


class TestMetricsConsistency:
    """Sharpe 计算一致性测试"""

    def test_sharpe_uses_risk_free_rate(self):
        sharpe = Metrics._calculate_sharpe(25.0, 15.0)
        expected = (25.0 - 3.0) / 15.0
        assert abs(sharpe - expected) < 0.001

    def test_sharpe_zero_volatility(self):
        assert Metrics._calculate_sharpe(10.0, 0.0) == 0

    def test_max_drawdown(self):
        values = [100, 110, 105, 95, 100, 120]
        dd = Metrics._calculate_max_drawdown(values)
        expected = (110 - 95) / 110 * 100
        assert abs(dd - expected) < 0.1


class TestBenchmarkProvider:
    def test_unknown_benchmark(self):
        with patch.object(BenchmarkProvider, '__init__', lambda self: None):
            bp = BenchmarkProvider()
            bp.duckdb = MagicMock()
            result = bp.get_benchmark_returns("nonexistent", "2025-01-01", "2025-12-31")
            assert result == {}
