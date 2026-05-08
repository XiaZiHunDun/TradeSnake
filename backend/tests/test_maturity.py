import pytest
from backend.maturity.metrics import calculate_monthly_returns, calculate_benchmark_excess

class MockPortfolio:
    def __init__(self, monthly_values):
        self.monthly_values = monthly_values  # [(date, value), ...]

def test_calculate_monthly_returns_single_profitable_month():
    """月初10000，月末10500，收益5% > 0.5%阈值，应该算盈利"""
    portfolio = MockPortfolio([
        ('2026-01-01', 10000),
        ('2026-01-31', 10500),
    ])
    result = calculate_monthly_returns(portfolio)
    assert len(result) == 1
    assert result[0].profitable == True
    assert result[0].return_pct == 5.0

def test_calculate_monthly_returns_loss_month():
    """月初10000，月末9900，收益-1%，不应算盈利（低于0.5%盈利门槛）"""
    portfolio = MockPortfolio([
        ('2026-01-01', 10000),
        ('2026-01-31', 9900),
    ])
    result = calculate_monthly_returns(portfolio)
    assert result[0].profitable == False

def test_calculate_benchmark_excess_positive():
    """策略收益5%，基准3%，超额2% > 0"""
    excess = calculate_benchmark_excess(
        strategy_return=0.05,
        benchmark_return=0.03
    )
    assert excess == pytest.approx(0.02)