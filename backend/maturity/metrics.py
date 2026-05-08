"""策略成熟度指标计算"""
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MonthlyReturn:
    month: str  # 'YYYY-MM'
    start_value: float
    end_value: float
    return_pct: float
    profitable: bool  # > 0.5% threshold

    def to_dict(self) -> Dict:
        return {
            'month': self.month,
            'start_value': self.start_value,
            'end_value': self.end_value,
            'return_pct': self.return_pct,
            'profitable': self.profitable,
        }

@dataclass
class MaturityMetrics:
    monthly_returns: List[MonthlyReturn]
    profitable_months: int  # ≥5/6 for graduation
    total_months: int
    benchmark_excess: float  # > 0 for graduation
    is_qualified: bool  # overall qualification

def calculate_monthly_returns(portfolio) -> List[MonthlyReturn]:
    """计算月度收益率"""
    if not portfolio.monthly_values:
        return []

    result = []
    values = portfolio.monthly_values

    from collections import defaultdict
    by_month = defaultdict(list)
    for date_str, value in values:
        month = date_str[:7]  # 'YYYY-MM'
        by_month[month].append((date_str, value))

    for month in sorted(by_month.keys()):
        month_values = sorted(by_month[month])
        start_value = month_values[0][1]
        end_value = month_values[-1][1]
        return_pct = (end_value - start_value) / start_value * 100 if start_value > 0 else 0

        result.append(MonthlyReturn(
            month=month,
            start_value=start_value,
            end_value=end_value,
            return_pct=return_pct,
            profitable=return_pct > 0.5
        ))

    return result

def calculate_benchmark_excess(strategy_return: float, benchmark_return: float) -> float:
    """计算相对基准的超额收益"""
    return strategy_return - benchmark_return

def is_maturity_qualified(metrics: MaturityMetrics) -> bool:
    """判断是否达到毕业标准"""
    if metrics.total_months < 6:
        return False
    profitable_condition = metrics.profitable_months >= 5
    excess_condition = metrics.benchmark_excess > 0
    return profitable_condition and excess_condition