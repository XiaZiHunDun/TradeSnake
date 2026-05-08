"""策略毕业标准评估器"""
from typing import List, Dict, Optional
from dataclasses import dataclass

from .metrics import MonthlyReturn

@dataclass
class MaturityResult:
    """毕业评估结果"""
    is_mature: bool
    profitable_months: int
    total_months: int
    benchmark_excess: float
    oos_is_ratio: float
    reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'is_mature': self.is_mature,
            'profitable_months': self.profitable_months,
            'total_months': self.total_months,
            'benchmark_excess': round(self.benchmark_excess, 4),
            'oos_is_ratio': round(self.oos_is_ratio, 3),
            'reason': self.reason
        }


class MaturityEvaluator:
    """策略成熟度评估器

    毕业条件（需同时满足）：
    1. 滚动6个月 >=5个月盈利（每月 >0.5%）
    2. 相对基准（沪深300）超额 > 0%
    3. OOS/IS Sharpe > 0.8（防止过拟合）
    """

    MIN_PROFITABLE_MONTHS = 5
    MIN_MONTHS = 6
    MIN_BENCHMARK_EXCESS = 0.0
    MIN_OOS_IS_RATIO = 0.8

    def evaluate(
        self,
        monthly_returns: List[MonthlyReturn],
        benchmark_excess: float,
        oos_is_ratio: float
    ) -> MaturityResult:
        """评估策略是否达到毕业标准"""
        profitable_months = sum(1 for m in monthly_returns if m.profitable)
        total_months = len(monthly_returns)

        # 条件1：盈利月份数
        if profitable_months < self.MIN_PROFITABLE_MONTHS:
            return MaturityResult(
                is_mature=False,
                profitable_months=profitable_months,
                total_months=total_months,
                benchmark_excess=benchmark_excess,
                oos_is_ratio=oos_is_ratio,
                reason='profitable_months_insufficient'
            )

        # 条件2：基准超额
        if benchmark_excess <= self.MIN_BENCHMARK_EXCESS:
            return MaturityResult(
                is_mature=False,
                profitable_months=profitable_months,
                total_months=total_months,
                benchmark_excess=benchmark_excess,
                oos_is_ratio=oos_is_ratio,
                reason='benchmark_excess_insufficient'
            )

        # 条件3：OOS/IS 比率
        if oos_is_ratio < self.MIN_OOS_IS_RATIO:
            return MaturityResult(
                is_mature=False,
                profitable_months=profitable_months,
                total_months=total_months,
                benchmark_excess=benchmark_excess,
                oos_is_ratio=oos_is_ratio,
                reason='oos_is_ratio_insufficient'
            )

        return MaturityResult(
            is_mature=True,
            profitable_months=profitable_months,
            total_months=total_months,
            benchmark_excess=benchmark_excess,
            oos_is_ratio=oos_is_ratio,
            reason=None
        )