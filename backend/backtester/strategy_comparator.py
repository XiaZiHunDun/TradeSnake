"""
策略对比器 v1.0 - 阶段1"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .strategies import (
    Strategy, TopNStrategy, ValueStrategy, GrowthStrategy, MomentumStrategy,
    LowVolatilityStrategy, HighDividendStrategy, ValueGrowthBalancedStrategy
)
from .full_backtest import FullBacktestEngine, BacktestStats


@dataclass
class BacktestConfig:
    """回测配置"""
    top_n: int = 6                    # 持仓数量
    stop_loss: float = -0.07         # 止损 -7%（v21标准）
    max_holding_days: int = 5         # 最大持仓天数
    initial_capital: float = 1000000  # 初始资金 100万
    market_filter: float = -2.0      # 大盘过滤阈值（关闭）
    min_avg_volume: float = 50000000  # 日均成交额门槛 5000万


@dataclass
class StrategyComparisonResult:
    """策略对比结果

    Note: quarterly_returns is populated for future use (quarterly analysis).
    """
    strategy_name: str
    annual_return: float
    max_drawdown: float
    excess_return: float
    information_ratio: float
    sharpe_ratio: float
    calmar_ratio: float
    win_rate: float
    profit_loss_ratio: float
    total_trades: int
    quarterly_returns: List[Dict] = field(default_factory=list)  # Future: quarterly performance analysis


class StrategyComparator:
    """策略对比器 v1.0"""

    # 策略类名到引擎策略名的显式映射
    STRATEGY_NAME_MAP = {
        'TopNStrategy': 'top',
        'MultiFactorStrategy': 'multifactor',
        'MomentumStrategy': 'momentum',
        'GrowthStrategy': 'growth',
        'LowVolatilityStrategy': 'lowvolatility',
        'HighDividendStrategy': 'highdividend',
        'ValueGrowthBalanced': 'valuegrowthbalanced',
    }

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.engine = FullBacktestEngine()

        # 初始化策略列表
        self.strategies: Dict[str, Strategy] = {
            'TopNStrategy': TopNStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
            'MultiFactorStrategy': self._create_multifactor_strategy(),
            'MomentumStrategy': MomentumStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
            'GrowthStrategy': GrowthStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
            'LowVolatilityStrategy': LowVolatilityStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
            'HighDividendStrategy': HighDividendStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
            'ValueGrowthBalanced': ValueGrowthBalancedStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
        }

    def _create_multifactor_strategy(self) -> Strategy:
        """创建多因子策略"""
        from .strategies import MultiFactorStrategy
        return MultiFactorStrategy(
            n=self.config.top_n,
            max_days=self.config.max_holding_days,
            weights={'growth': 0.50, 'value': 0.00, 'momentum': 0.28, 'quality': 0.05}  # v21 WEIGHTS
        )

    def compare_strategies(
        self,
        start_date: str,
        end_date: str,
        strategy_names: Optional[List[str]] = None
    ) -> Dict[str, StrategyComparisonResult]:
        """对比策略表现

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            strategy_names: 要对比的策略名称列表，None 表示全部

        Returns:
            {strategy_name: result} 策略对比结果
        """
        results = {}

        # 获取基准（沪深300买入持有）
        benchmark_result = self._run_benchmark(start_date, end_date)

        # 对比各策略
        for name, strategy in self.strategies.items():
            if strategy_names and name not in strategy_names:
                continue

            print(f"  Running {name}...")

            # 使用显式映射获取引擎策略名
            engine_strategy_name = self.STRATEGY_NAME_MAP.get(name, name.lower())

            # 使用 engine.run 进行回测，带错误处理
            try:
                stats = self.engine.run(
                    start_date=start_date,
                    end_date=end_date,
                    strategy_name=engine_strategy_name,
                    top_n=self.config.top_n,
                    initial_capital=self.config.initial_capital,
                    stop_loss_pct=self.config.stop_loss,
                    max_holding_days=self.config.max_holding_days,
                    market_filter_pct=self.config.market_filter
                )
            except Exception as e:
                print(f"  WARNING: {name} failed: {e}")
                continue

            # 转换为对比结果格式
            result = self._convert_to_comparison_result(name, stats, benchmark_result)
            results[name] = result

        return results

    def _run_benchmark(self, start_date: str, end_date: str) -> BacktestStats:
        """运行基准策略（沪深300买入持有）"""
        # 简化：使用 TopNStrategy(n=300) 作为等权选股域基准
        return self.engine.run(
            start_date=start_date,
            end_date=end_date,
            strategy_name='top',
            top_n=300,  # 沪深300成分股数量
            initial_capital=self.config.initial_capital,
            stop_loss_pct=-0.30,  # 基准不止损
            max_holding_days=999,  # 长期持有
            market_filter_pct=-100  # 关闭大盘过滤
        )

    def _convert_to_comparison_result(
        self,
        strategy_name: str,
        stats: BacktestStats,
        benchmark: BacktestStats
    ) -> StrategyComparisonResult:
        """将 BacktestStats 转换为 StrategyComparisonResult"""
        # 计算超额收益
        excess_return = stats.annualized_return - benchmark.annualized_return

        # 计算信息比率（简化版：超额收益/跟踪误差）
        # 标准信息比率 = excess_return / tracking_error_std (日收益差分标准差)
        # 此处用最大回撤差分简化替代
        excess_volatility = abs(stats.max_drawdown - benchmark.max_drawdown) / 2
        information_ratio = excess_return / excess_volatility if excess_volatility > 0 else 0

        return StrategyComparisonResult(
            strategy_name=strategy_name,
            annual_return=round(stats.annualized_return, 2),
            max_drawdown=round(stats.max_drawdown, 2),
            excess_return=round(excess_return, 2),
            information_ratio=round(information_ratio, 2),
            sharpe_ratio=round(getattr(stats, 'sharpe_ratio', 0), 2),
            calmar_ratio=round(stats.annualized_return / stats.max_drawdown, 2) if stats.max_drawdown > 0 else 0,
            win_rate=round(stats.win_rate, 2),
            profit_loss_ratio=round(getattr(stats, 'profit_loss_ratio', 0), 2),
            total_trades=stats.total_trades
        )

    def get_best_strategy(self, results: Dict[str, StrategyComparisonResult]) -> str:
        """获取最优策略（综合评分）

        Raises:
            ValueError: 如果没有可用的策略结果
        """
        if not results:
            raise ValueError("No strategy results available for comparison")

        best_name = None
        best_score = -float('inf')

        for name, result in results.items():
            # 综合评分：年化收益 * 0.4 + (100-最大回撤) * 0.3 + 胜率 * 0.2 + 信息比率 * 10 * 0.1
            score = (
                result.annual_return * 0.4 +
                (100 - result.max_drawdown) * 0.3 +
                result.win_rate * 0.2 +
                result.information_ratio * 10 * 0.1
            )
            if score > best_score:
                best_score = score
                best_name = name

        return best_name
