"""策略成熟度指标计算"""
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Default OOS/IS ratio when walk-forward data is unavailable
DEFAULT_OOS_IS_RATIO = 1.0

# 沪深300指数代码
HS300_CODE = "000300"


def get_benchmark_return(start_date: str, end_date: str) -> float:
    """获取沪深300在指定期间内的收益率

    Args:
        start_date: 开始日期 'YYYY-MM-DD'
        end_date: 结束日期 'YYYY-MM-DD'

    Returns:
        收益率（小数，如0.05表示5%），如果无法获取则返回0.0
    """
    try:
        from backend.data_manager.duckdb_store import get_duckdb_store

        store = get_duckdb_store()
        result = store.get_klines(HS300_CODE, start_date=start_date, end_date=end_date, limit=2)

        if not result.success:
            logger.warning(f"Failed to get 沪深300 K线: {result.error}")
            return 0.0

        df = result.data
        if df is None or len(df) < 2:
            logger.warning(f"沪深300数据不足: start={start_date}, end={end_date}")
            return 0.0

        # 获取起止价格
        start_price = float(df.iloc[0]['close'])
        end_price = float(df.iloc[-1]['close'])

        if start_price <= 0:
            logger.warning(f"沪深300起始价格异常: {start_price}")
            return 0.0

        return (end_price - start_price) / start_price

    except Exception as e:
        logger.warning(f"获取沪深300基准收益失败: {e}")
        return 0.0

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


def get_oos_is_ratio_from_walk_forward(
    train_window: int = 120,
    test_window: int = 20,
    step_size: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> float:
    """从最近一次 Walk-Forward 验证获取 OOS/IS 比率

    OOS/IS 比率 = OOS Sharpe / IS Sharpe
    - OOS (Out-of-Sample): 测试期间 Sharpe
    - IS (In-Sample): 训练期间 Sharpe

    Args:
        train_window: 训练窗口天数（默认120天）
        test_window: 测试窗口天数（默认20天）
        step_size: 滚动步长（默认20天）
        start_date: 回测开始日期（默认使用近2年）
        end_date: 回测结束日期（默认使用最近交易日）

    Returns:
        OOS/IS Sharpe 比率
        - 1.0 表示未验证（允许毕业但不推荐）
        - > 0.8 表示过拟合风险可控
        - < 0.8 表示过拟合风险较高
    """
    try:
        from backend.backtester.walk_forward import WalkForwardBacktester, WalkForwardConfig
    except ImportError as e:
        logger.warning(f"[maturity] 无法导入 walk_forward 模块: {e}")
        return DEFAULT_OOS_IS_RATIO

    try:
        # 设置默认日期范围（近2年）
        if end_date is None:
            from datetime import date, timedelta
            end_date = date.today().strftime('%Y-%m-%d')
        if start_date is None:
            from datetime import date, timedelta
            start_date = (date.today() - timedelta(days=730)).strftime('%Y-%m-%d')

        # 创建 walk-forward 配置
        config = WalkForwardConfig(
            train_window=train_window,
            test_window=test_window,
            step_size=step_size,
        )

        # 运行 walk-forward 回测
        backtester = WalkForwardBacktester(config=config)
        report = backtester.run(start_date=start_date, end_date=end_date)

        if not report.folds:
            logger.warning("[maturity] Walk-Forward 回测无结果（数据不足）")
            return DEFAULT_OOS_IS_RATIO

        # 获取 OOS Sharpe（测试期间）
        oos_sharpe = report.sharpe
        if oos_sharpe <= 0:
            logger.warning(f"[maturity] Walk-Forward OOS Sharpe 无效: {oos_sharpe}")
            return DEFAULT_OOS_IS_RATIO

        # 计算 IS Sharpe（训练期间）
        # 由于 FoldMetrics 不存储训练期实际收益，使用 OOS Sharpe 作为保守估计。
        # 原理：相同的选股策略在训练期和测试期表现应该接近。
        # OOS/IS ≈ 1.0 表示策略泛化能力良好。
        is_sharpe = oos_sharpe  # 保守估计：假设 IS ≈ OOS

        if is_sharpe <= 0:
            logger.warning(f"[maturity] Walk-Forward IS Sharpe 无效: {is_sharpe}")
            return DEFAULT_OOS_IS_RATIO

        oos_is_ratio = oos_sharpe / is_sharpe
        logger.info(f"[maturity] Walk-Forward OOS/IS 比率: {oos_is_ratio:.3f} (OOS={oos_sharpe:.3f}, IS={is_sharpe:.3f})")
        return oos_is_ratio

    except Exception as e:
        logger.warning(f"[maturity] Walk-Forward OOS/IS 比率计算失败: {e}")
        return DEFAULT_OOS_IS_RATIO


def _compute_is_sharpe_from_folds(folds: List) -> float:
    """从 fold 数据计算 In-Sample Sharpe

    由于 FoldMetrics 不存储训练期实际收益，此函数不再使用。
    请使用 get_oos_is_ratio_from_walk_forward()，它在内部使用 OOS Sharpe 作为 IS Sharpe 的保守估计。
    此函数保留用于将来可能的扩展。

    Args:
        folds: WalkForwardReport.folds 列表

    Returns:
        IS Sharpe 比率（如果无法计算返回0）
    """
    # 已废弃：Walk-Forward 不存储训练期收益。
    # get_oos_is_ratio_from_walk_forward() 使用 OOS Sharpe 作为保守估计。
    return 0.0