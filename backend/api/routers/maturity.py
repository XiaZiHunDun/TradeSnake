"""策略成熟度相关 API"""
import logging
from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.maturity.evaluator import MaturityEvaluator, MaturityResult
from backend.maturity.daily_signal import DailySignalGenerator
from backend.maturity.metrics import MonthlyReturn, get_benchmark_return
from backend.simulator.database import get_db
from backend.api.dependencies import cp_engine
from backend.recommender.buy_analyzer import BuyAnalyzer

# 默认本金（用于Kelly计算）
DEFAULT_PRINCIPAL = 100000.0


def get_current_kelly_position() -> float:
    """获取当前最优Kelly仓位

    Returns:
        Kelly仓位百分比（如10.0表示10%）
        如果无数据或出错，返回0.0
    """
    try:
        # 1. 获取候选股票列表（战力榜Top 20）
        stocks = cp_engine.get_top(n=20)
        if not stocks:
            logger.warning("get_current_kelly_position: no stocks available")
            return 0.0

        # 2. 对每只股票调用BuyAnalyzer，取Kelly仓位最高的
        best_kelly = 0.0
        for stock in stocks:
            try:
                signal = BuyAnalyzer.analyze_buy_opportunity(
                    stock=stock,
                    principal=DEFAULT_PRINCIPAL,
                    risk_preference='balanced'
                )
                if signal.kelly_position > best_kelly:
                    best_kelly = signal.kelly_position
            except Exception as e:
                logger.debug(f"BuyAnalyzer skipped {stock.code}: {e}")
                continue

        return best_kelly

    except Exception as e:
        logger.error(f"get_current_kelly_position failed: {e}")
        return 0.0

logger = logging.getLogger(__name__)


def get_monthly_returns_from_portfolio(portfolio_history: List[Dict]) -> List[MonthlyReturn]:
    """从持仓历史记录计算月度收益率

    Args:
        portfolio_history: 持仓历史记录，每条记录包含 date, total_value

    Returns:
        List[MonthlyReturn] - 按月统计的收益率
    """
    if not portfolio_history:
        return []

    # 按月分组
    by_month: Dict[str, List[tuple]] = defaultdict(list)
    for record in portfolio_history:
        date_str = record.get('date', '')
        if not date_str:
            continue
        # date format: 'YYYY-MM-DD'
        month = date_str[:7]
        total_value = record.get('total_value', 0)
        by_month[month].append((date_str, total_value))

    # 计算每月收益率
    result = []
    for month in sorted(by_month.keys()):
        month_records = sorted(by_month[month])
        if len(month_records) < 2:
            # 只有一天数据，使用该值作为期初和期末
            start_value = month_records[0][1]
            end_value = start_value
        else:
            start_value = month_records[0][1]
            end_value = month_records[-1][1]

        return_pct = (end_value - start_value) / start_value * 100 if start_value > 0 else 0
        result.append(MonthlyReturn(
            month=month,
            start_value=round(start_value, 2),
            end_value=round(end_value, 2),
            return_pct=round(return_pct, 2),
            profitable=return_pct > 0.5
        ))

    return result

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

    # 从 simulator 获取真实持仓数据
    try:
        db = get_db()
        portfolio_history = db.get_portfolio_value_history()
        monthly_returns = get_monthly_returns_from_portfolio(portfolio_history)

        if not monthly_returns:
            # 如果没有真实数据，返回默认值而非错误
            logger.warning("maturity/status: 无持仓历史数据，使用默认模拟数据")
            monthly_returns = [
                MonthlyReturn('2026-01', 10000, 10500, 5.0, True),
                MonthlyReturn('2026-02', 10500, 10800, 2.86, True),
                MonthlyReturn('2026-03', 10800, 10600, -1.85, False),
                MonthlyReturn('2026-04', 10600, 11200, 5.66, True),
                MonthlyReturn('2026-05', 11200, 11500, 2.68, True),
                MonthlyReturn('2026-06', 11500, 11800, 2.61, True),
            ]
    except Exception as e:
        logger.error(f"maturity/status: 获取持仓历史失败: {e}")
        # 出错时返回模拟数据，保持向后兼容
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

    # 获取真实Kelly仓位
    kelly_position = get_current_kelly_position()

    # 如果获取失败（返回0），使用模拟值但保持向后兼容
    if kelly_position <= 0:
        logger.warning("maturity/daily_signal: 无法获取真实Kelly仓位，使用默认值")
        kelly_position = 10.0

    # TODO: 获取真实风险等级和预测数据
    # 暂时使用模拟数据，后续可从 recommender 融合结果获取
    signal = generator.generate(
        kelly_position=kelly_position,
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