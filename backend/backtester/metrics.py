"""
绩效指标计算 - Metrics v19.3
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class Trade:
    """交易记录"""
    signal_date: str           # 信号日
    trade_date: str           # 成交日
    code: str                  # 股票代码
    name: str                  # 股票名称
    action: str               # 'buy' / 'sell'
    price: float              # 成交价
    quantity: int              # 成交数量
    amount: float              # 成交金额
    commission: float = 0      # 佣金
    stamp_tax: float = 0      # 印花税（卖出时）
    transfer_fee: float = 0   # 过户费
    profit: float = 0         # 盈亏（卖出时）
    reason: str = ''          # 原因：'rebalance'/'stop_loss'/'max_days'

    def to_dict(self) -> Dict:
        return {
            'signal_date': self.signal_date,
            'trade_date': self.trade_date,
            'code': self.code,
            'name': self.name,
            'action': self.action,
            'price': self.price,
            'quantity': self.quantity,
            'amount': round(self.amount, 2),
            'commission': round(self.commission, 2),
            'stamp_tax': round(self.stamp_tax, 2),
            'transfer_fee': round(self.transfer_fee, 2),
            'profit': round(self.profit, 2) if self.profit else 0,
            'reason': self.reason
        }


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str           # 策略名称
    start_date: str             # 开始日期
    end_date: str               # 结束日期
    initial_capital: float      # 初始资金
    final_capital: float        # 最终资金

    # 绩效指标
    total_return: float = 0         # 总收益率%
    annual_return: float = 0        # 年化收益率%
    benchmark_return: float = 0     # 基准收益率%
    excess_return: float = 0        # 超额收益率%
    sharpe_ratio: float = 0         # 夏普比率
    calmar_ratio: float = 0         # 卡玛比率
    max_drawdown: float = 0         # 最大回撤%
    volatility: float = 0            # 年化波动率%
    max_consecutive_win: int = 0    # 最大连续盈利天数
    max_consecutive_loss: int = 0   # 最大连续亏损天数

    # 交易指标
    total_trades: int = 0          # 总交易次数
    winning_trades: int = 0        # 盈利次数
    losing_trades: int = 0         # 亏损次数
    win_rate: float = 0            # 交易胜率%
    profit_loss_ratio: float = 0   # 盈亏比
    trimmed_profit_loss_ratio: float = 0  # 截尾盈亏比（去除5%极端值）
    avg_holding_days: float = 0  # 平均持仓天数

    # 交易记录
    trades: List[Trade] = field(default_factory=list)

    # 净值曲线
    equity_curve: Dict = field(default_factory=dict)  # {date: total_value}
    net_value_curve: Dict = field(default_factory=dict)  # {date: net_value}
    benchmark_curve: Dict = field(default_factory=dict)  # {date: value}

    # 持仓记录
    positions_history: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'strategy_name': self.strategy_name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'final_capital': round(self.final_capital, 2),

            # 绩效指标
            'total_return': round(self.total_return, 2),
            'annual_return': round(self.annual_return, 2),
            'benchmark_return': round(self.benchmark_return, 2),
            'excess_return': round(self.excess_return, 2),
            'sharpe_ratio': round(self.sharpe_ratio, 2),
            'calmar_ratio': round(self.calmar_ratio, 2),
            'max_drawdown': round(self.max_drawdown, 2),
            'volatility': round(self.volatility, 2),
            'max_consecutive_win': self.max_consecutive_win,
            'max_consecutive_loss': self.max_consecutive_loss,

            # 交易指标
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate, 2),
            'profit_loss_ratio': round(self.profit_loss_ratio, 2),
            'trimmed_profit_loss_ratio': round(self.trimmed_profit_loss_ratio, 2),
            'avg_holding_days': round(self.avg_holding_days, 1),

            # 交易记录
            'trades': [t.to_dict() for t in self.trades],
        }


class Metrics:
    """绩效指标计算工具 v19.3"""

    RISK_FREE_RATE = 0.03  # 无风险利率 3%
    TRADING_DAYS = 250  # 年化交易日

    @classmethod
    def _trim_extremes(cls, values: List[float], trim_pct: float = 0.05) -> List[float]:
        """截尾处理：去除极端值（前后各trim_pct）

        Args:
            values: 数值列表
            trim_pct: 截尾比例（默认5%，即前后各去除5%）

        Returns:
            截尾后的列表
        """
        if not values or len(values) < 4:
            return values
        n = len(values)
        trim_count = max(1, int(n * trim_pct))
        sorted_vals = sorted(values)
        # 确保不会切掉太多
        if trim_count >= n // 2:
            return values
        return sorted_vals[trim_count:-trim_count]

    @classmethod
    def calculate_trimmed_profit_loss_ratio(cls, trades: List[Trade], trim_pct: float = 0.05) -> float:
        """计算截尾后的盈亏比（去除极端值）

        Args:
            trades: 交易记录列表
            trim_pct: 截尾比例（默认5%）

        Returns:
            截尾后的盈亏比
        """
        if not trades:
            return 0.0

        profits = [t.profit for t in trades if t.profit > 0]
        losses = [abs(t.profit) for t in trades if t.profit < 0]

        if not profits or not losses:
            return 0.0

        # 截尾处理
        trimmed_profits = cls._trim_extremes(profits, trim_pct)
        trimmed_losses = cls._trim_extremes(losses, trim_pct)

        if not trimmed_profits or not trimmed_losses:
            return 0.0

        avg_profit = sum(trimmed_profits) / len(trimmed_profits)
        avg_loss = sum(trimmed_losses) / len(trimmed_losses)

        return avg_profit / avg_loss if avg_loss > 0 else 0.0

    @classmethod
    def calculate_metrics(cls, equity_curve: Dict[str, float],
                         benchmark_curve: Optional[Dict[str, float]] = None,
                         trades: List[Trade] = None,
                         initial_capital: float = 20000) -> Dict:
        """计算所有绩效指标

        Args:
            equity_curve: 净值曲线 {date: value}
            benchmark_curve: 基准净值曲线
            trades: 交易记录列表
            initial_capital: 初始资金

        Returns:
            绩效指标字典
        """
        dates = sorted(equity_curve.keys())
        if not dates:
            return {}

        values = [equity_curve[d] for d in dates]

        # 基本收益指标
        final_value = values[-1]
        total_return = (final_value - initial_capital) / initial_capital * 100

        # 年化收益率
        # 注意：return_periods = len(dates) - 1，因为有N个日期就有N-1个收益率
        return_periods = len(dates) - 1
        annual_return = ((1 + total_return / 100) ** (cls.TRADING_DAYS / return_periods) - 1) * 100 if return_periods > 0 else 0

        # 基准收益
        benchmark_return = 0
        excess_return = 0
        if benchmark_curve:
            bm_dates = sorted(benchmark_curve.keys())
            if bm_dates:
                bm_start = benchmark_curve.get(bm_dates[0], 1)
                bm_end = benchmark_curve.get(bm_dates[-1], 1)
                if bm_start > 0:
                    benchmark_return = (bm_end - bm_start) / bm_start * 100
                excess_return = total_return - benchmark_return

        # 计算每日收益率
        daily_returns = []
        for i in range(1, len(values)):
            if values[i-1] > 0:
                ret = (values[i] - values[i-1]) / values[i-1]
                daily_returns.append(ret)

        # 波动率
        volatility = cls._calculate_volatility(daily_returns)

        # 夏普比率
        sharpe_ratio = cls._calculate_sharpe(annual_return, volatility)

        # 最大回撤
        max_drawdown = cls._calculate_max_drawdown(values)

        # 卡玛比率
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # 连续盈亏天数
        max_consecutive_win, max_consecutive_loss = cls._calculate_consecutive_days(daily_returns)

        # 交易统计
        total_trades = len(trades) if trades else 0
        winning_trades = len([t for t in trades if t.profit > 0]) if trades else 0
        losing_trades = len([t for t in trades if t.profit < 0]) if trades else 0
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

        # 盈亏比（按金额）
        if trades:
            avg_profit = sum(t.profit for t in trades if t.profit > 0) / winning_trades if winning_trades > 0 else 0
            avg_loss = abs(sum(t.profit for t in trades if t.profit < 0) / losing_trades) if losing_trades > 0 else 0
            profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
            # 截尾盈亏比
            trimmed_profit_loss_ratio = cls.calculate_trimmed_profit_loss_ratio(trades)
        else:
            profit_loss_ratio = 0
            trimmed_profit_loss_ratio = 0

        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'benchmark_return': benchmark_return,
            'excess_return': excess_return,
            'sharpe_ratio': sharpe_ratio,
            'calmar_ratio': calmar_ratio,
            'max_drawdown': max_drawdown,
            'volatility': volatility,
            'max_consecutive_win': max_consecutive_win,
            'max_consecutive_loss': max_consecutive_loss,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'trimmed_profit_loss_ratio': trimmed_profit_loss_ratio,
        }

    @staticmethod
    def _calculate_volatility(daily_returns: List[float]) -> float:
        """计算年化波动率"""
        if not daily_returns or len(daily_returns) < 2:
            return 0
        import statistics
        std = statistics.stdev(daily_returns)
        return std * (250 ** 0.5) * 100  # 年化波动率

    @classmethod
    def _calculate_sharpe(cls, annual_return: float, volatility: float) -> float:
        """计算夏普比率

        Args:
            annual_return: 年化收益率（百分比形式，如 25.0 表示 25%）
            volatility: 年化波动率（百分比形式，如 15.0 表示 15%）

        Returns:
            夏普比率
        """
        if volatility == 0:
            return 0
        # annual_return 和 volatility 都是百分比形式（如 25.0 表示 25%）
        # 无风险利率也是百分比形式（如 3.0 表示 3%）
        return (annual_return - cls.RISK_FREE_RATE * 100) / volatility

    @staticmethod
    def _calculate_max_drawdown(values: List[float]) -> float:
        """计算最大回撤（基于净值）

        使用滚动最大值计算最大回撤百分比
        """
        if not values or len(values) < 2:
            return 0

        peak = values[0]
        max_dd = 0.0

        for value in values:
            if value > peak:
                peak = value
            if peak > 0:
                dd = (peak - value) / peak
                max_dd = max(max_dd, dd)

        return max_dd * 100  # 返回百分比

    @staticmethod
    def _calculate_consecutive_days(daily_returns: List[float]) -> tuple:
        """计算最大连续盈亏天数"""
        if not daily_returns:
            return 0, 0

        max_win = 0
        max_loss = 0
        current_win = 0
        current_loss = 0

        for ret in daily_returns:
            if ret > 0:
                current_win += 1
                current_loss = 0
                max_win = max(max_win, current_win)
            elif ret < 0:
                current_loss += 1
                current_win = 0
                max_loss = max(max_loss, current_loss)
            else:
                current_win = 0
                current_loss = 0

        return max_win, max_loss
