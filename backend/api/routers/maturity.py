"""策略成熟度相关 API"""
from fastapi import APIRouter, Depends
from typing import List, Optional
from pydantic import BaseModel

from backend.maturity.evaluator import MaturityEvaluator, MaturityResult
from backend.maturity.daily_signal import DailySignalGenerator
from backend.maturity.metrics import MonthlyReturn

router = APIRouter(prefix='/api/maturity', tags=['maturity'])


class MonthlyReturnResponse(BaseModel):
    month: str
    start_value: float
    end_value: float
    return_pct: float
    profitable: bool


class MaturityStatusResponse(BaseModel):
    is_mature: bool
    profitable_months: int
    total_months: int
    benchmark_excess: float
    oos_is_ratio: float
    reason: Optional[str]
    monthly_returns: List[MonthlyReturnResponse]


class DailySignalResponse(BaseModel):
    level: str
    emoji: str
    kelly_position: float
    risk_level: str
    predicted_gain_5d: float
    up_probability_5d: float
    is_mature: bool
    reason: str


@router.get('/status', response_model=MaturityStatusResponse)
def get_maturity_status():
    """获取策略毕业状态"""
    evaluator = MaturityEvaluator()

    # 模拟数据
    monthly_returns = [
        MonthlyReturn('2026-01', 10000, 10500, 5.0, True),
        MonthlyReturn('2026-02', 10500, 10800, 2.86, True),
        MonthlyReturn('2026-03', 10800, 10600, -1.85, False),
        MonthlyReturn('2026-04', 10600, 11200, 5.66, True),
        MonthlyReturn('2026-05', 11200, 11500, 2.68, True),
        MonthlyReturn('2026-06', 11500, 11800, 2.61, True),
    ]

    result = evaluator.evaluate(
        monthly_returns=monthly_returns,
        benchmark_excess=0.02,
        oos_is_ratio=0.85
    )

    return MaturityStatusResponse(
        is_mature=result.is_mature,
        profitable_months=result.profitable_months,
        total_months=result.total_months,
        benchmark_excess=result.benchmark_excess,
        oos_is_ratio=result.oos_is_ratio,
        reason=result.reason,
        monthly_returns=[
            MonthlyReturnResponse(
                month=m.month,
                start_value=m.start_value,
                end_value=m.end_value,
                return_pct=m.return_pct,
                profitable=m.profitable
            ) for m in monthly_returns
        ]
    )


@router.get('/daily_signal', response_model=DailySignalResponse)
def get_daily_signal():
    """获取每日交易信号"""
    generator = DailySignalGenerator()

    # 模拟数据
    signal = generator.generate(
        kelly_position=10.0,
        risk_level='acceptable',
        predicted_gain_5d=8.0,
        up_probability_5d=0.65,
        is_mature=True
    )

    return DailySignalResponse(**signal.to_dict())


@router.get('/history', response_model=List[MonthlyReturnResponse])
def get_monthly_history():
    """获取历史月度表现"""
    return [
        MonthlyReturnResponse(month='2026-01', start_value=10000, end_value=10500, return_pct=5.0, profitable=True),
        MonthlyReturnResponse(month='2026-02', start_value=10500, end_value=10800, return_pct=2.86, profitable=True),
    ]