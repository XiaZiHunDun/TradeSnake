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


# =============================================================================
# Evaluator Tests
# =============================================================================


def test_evaluator_is_mature_with_valid_data():
    """6个月中5个月盈利，基准超额>0%，应判定为成熟"""
    from backend.maturity.evaluator import MaturityEvaluator
    from backend.maturity.metrics import MonthlyReturn

    evaluator = MaturityEvaluator()

    monthly_returns = [
        MonthlyReturn('2026-01', 10000, 10500, 5.0, True),
        MonthlyReturn('2026-02', 10500, 10800, 2.86, True),
        MonthlyReturn('2026-03', 10800, 10600, -1.85, False),
        MonthlyReturn('2026-04', 10600, 11200, 5.66, True),
        MonthlyReturn('2026-05', 11200, 11500, 2.68, True),
        MonthlyReturn('2026-06', 11500, 11800, 2.61, True),
    ]

    result = evaluator.evaluate(monthly_returns=monthly_returns, benchmark_excess=0.02, oos_is_ratio=0.85)
    assert result.is_mature == True
    assert result.profitable_months == 5


def test_evaluator_not_mature_insufficient_profitable_months():
    """6个月中只有4个月盈利，不满足>=5/6条件"""
    from backend.maturity.evaluator import MaturityEvaluator
    from backend.maturity.metrics import MonthlyReturn

    evaluator = MaturityEvaluator()

    monthly_returns = [
        MonthlyReturn('2026-01', 10000, 10500, 5.0, True),
        MonthlyReturn('2026-02', 10500, 10800, 2.86, True),
        MonthlyReturn('2026-03', 10800, 10600, -1.85, False),
        MonthlyReturn('2026-04', 10600, 10800, 1.89, True),
        MonthlyReturn('2026-05', 10800, 10600, -1.85, False),
        MonthlyReturn('2026-06', 10600, 10800, 1.89, True),
    ]

    result = evaluator.evaluate(monthly_returns=monthly_returns, benchmark_excess=0.02, oos_is_ratio=0.85)
    assert result.is_mature == False
    assert result.reason == 'profitable_months_insufficient'


def test_evaluator_not_mature_low_benchmark_excess():
    """基准超额为负，不满足>0条件"""
    from backend.maturity.evaluator import MaturityEvaluator
    from backend.maturity.metrics import MonthlyReturn

    evaluator = MaturityEvaluator()

    monthly_returns = [
        MonthlyReturn('2026-01', 10000, 10500, 5.0, True),
        MonthlyReturn('2026-02', 10500, 10800, 2.86, True),
        MonthlyReturn('2026-03', 10800, 10600, -1.85, False),
        MonthlyReturn('2026-04', 10600, 11200, 5.66, True),
        MonthlyReturn('2026-05', 11200, 11500, 2.68, True),
        MonthlyReturn('2026-06', 11500, 11800, 2.61, True),
    ]

    result = evaluator.evaluate(monthly_returns=monthly_returns, benchmark_excess=-0.01, oos_is_ratio=0.85)
    assert result.is_mature == False
    assert result.reason == 'benchmark_excess_insufficient'


def test_evaluator_not_mature_low_oos_is_ratio():
    """OOS/IS比率0.7 < 0.8，不满足过拟合检验"""
    from backend.maturity.evaluator import MaturityEvaluator
    from backend.maturity.metrics import MonthlyReturn

    evaluator = MaturityEvaluator()

    monthly_returns = [
        MonthlyReturn('2026-01', 10000, 10500, 5.0, True),
        MonthlyReturn('2026-02', 10500, 10800, 2.86, True),
        MonthlyReturn('2026-03', 10800, 10600, -1.85, False),
        MonthlyReturn('2026-04', 10600, 11200, 5.66, True),
        MonthlyReturn('2026-05', 11200, 11500, 2.68, True),
        MonthlyReturn('2026-06', 11500, 11800, 2.61, True),
    ]

    result = evaluator.evaluate(monthly_returns=monthly_returns, benchmark_excess=0.02, oos_is_ratio=0.7)
    assert result.is_mature == False
    assert result.reason == 'oos_is_ratio_insufficient'


# =============================================================================
# Daily Signal Tests
# =============================================================================


def test_daily_signal_strong_buy_mature():
    """毕业后：Kelly 10%, 低风险, 预测向上 -> 强烈买入"""
    from backend.maturity.daily_signal import DailySignalGenerator

    generator = DailySignalGenerator()

    signal = generator.generate(
        kelly_position=10.0,
        risk_level='acceptable',
        predicted_gain_5d=8.0,
        up_probability_5d=0.65,
        is_mature=True
    )
    assert signal.level == 'strong_buy'
    assert signal.emoji == '🟢'


def test_daily_signal_empty_before_maturity():
    """毕业前：Kelly 10% 但未达强烈买入 -> 空仓（禁止操作）"""
    from backend.maturity.daily_signal import DailySignalGenerator

    generator = DailySignalGenerator()

    signal = generator.generate(
        kelly_position=10.0,
        risk_level='acceptable',
        predicted_gain_5d=3.0,  # < 5%
        up_probability_5d=0.55,  # < 0.6
        is_mature=False
    )
    assert signal.level == 'empty'
    assert signal.emoji == '🔴'


def test_daily_signal_watch_after_maturity():
    """毕业后：Kelly 5%, 中风险, 预测中性 -> 观望"""
    from backend.maturity.daily_signal import DailySignalGenerator

    generator = DailySignalGenerator()

    signal = generator.generate(
        kelly_position=5.0,
        risk_level='warning',
        predicted_gain_5d=3.0,
        up_probability_5d=0.55,
        is_mature=True
    )
    assert signal.level == 'watch'
    assert signal.emoji == '🟡'


def test_daily_signal_empty_high_risk():
    """高风险无论是否毕业都空仓"""
    from backend.maturity.daily_signal import DailySignalGenerator

    generator = DailySignalGenerator()

    signal = generator.generate(
        kelly_position=10.0,
        risk_level='high',
        predicted_gain_5d=8.0,
        up_probability_5d=0.65,
        is_mature=True
    )
    assert signal.level == 'empty'
    assert signal.emoji == '🔴'