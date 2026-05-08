"""策略成熟度评估模块"""
from .metrics import MonthlyReturn, MaturityMetrics, calculate_monthly_returns, calculate_benchmark_excess, is_maturity_qualified

# TODO: 等 evaluator.py 和 daily_signal.py 创建后添加
# from .evaluator import MaturityEvaluator, MaturityResult
# from .daily_signal import DailySignalGenerator, DailySignal, SignalLevel

__all__ = [
    'MonthlyReturn',
    'MaturityMetrics',
    'calculate_monthly_returns',
    'calculate_benchmark_excess',
    'is_maturity_qualified',
]