"""
完整回测引擎 - Full Backtest Engine v1.0

基于历史战力数据进行真实收益率回测
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math

from .strategies import Strategy, TopNStrategy, ValueStrategy, GrowthStrategy, MomentumStrategy
from .metrics import BacktestResult, Trade


@dataclass
class Position:
    """持仓"""
    code: str
    name: str
    quantity: int = 0
    avg_cost: float = 0.0
    buy_date: str = ''
    holding_days: int = 0


@dataclass
class BacktestTrade:
    """回测交易记录"""
    date: str
    action: str  # 'buy' or 'sell'
    code: str
    name: str
    price: float
    quantity: int
    amount: float
    commission: float
    reason: str = ''


@dataclass
class BacktestStats:
    """回测统计"""
    initial_capital: float
    final_value: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    equity_curve: List[Dict] = field(default_factory=list)
    trades: List[Dict] = field(default_factory=list)


class FullBacktestEngine:
    """完整回测引擎 v1.0"""

    # 交易费用
    COMMISSION_RATE = 0.0003  # 0.03%
    MIN_COMMISSION = 5.0
    STAMP_TAX_RATE = 0.001   # 0.1% (卖出时收取)
    TRANSFER_FEE_RATE = 0.00002  # 0.002%

    def __init__(self):
        from backend.data_manager.cp_history_store import get_cp_history_store
        from backend.data_manager.duckdb_store import get_duckdb_store

        self.cp_store = get_cp_history_store()
        self.duckdb = get_duckdb_store()

        # 策略映射
        self.strategies = {
            'top': TopNStrategy(n=10),
            'value': ValueStrategy(n=10),
            'growth': GrowthStrategy(n=10),
            'momentum': MomentumStrategy(n=10),
        }

    def run(
        self,
        start_date: str,
        end_date: str,
        strategy_name: str = 'top',
        top_n: int = 10,
        initial_capital: float = 20000.0
    ) -> BacktestStats:
        """
        执行完整回测

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            strategy_name: 策略名称 (top/value/growth/momentum)
            top_n: 持仓数量
            initial_capital: 初始资金

        Returns:
            BacktestStats: 回测统计结果
        """
        # 获取策略
        strategy = self.strategies.get(strategy_name, TopNStrategy(n=top_n))
        if hasattr(strategy, 'n'):
            strategy.n = top_n

        # 获取交易日列表
        trading_dates = self._get_trading_dates(start_date, end_date)
        if len(trading_dates) < 2:
            raise ValueError("交易日数据不足")

        # 初始化状态
        cash = initial_capital
        positions: Dict[str, Position] = {}
        pending_bought: Set[str] = set()
        trades: List[BacktestTrade] = []
        equity_curve: List[Dict] = []

        # 按日期遍历
        for i in range(len(trading_dates) - 1):
            signal_date = trading_dates[i]
            trade_date = trading_dates[i + 1]

            # 获取信号日的战力数据
            cp_data = self._get_cp_at_date(signal_date)
            if not cp_data:
                continue

            # 策略选股 - 按战力排序取top_n
            stock_factors = self._build_stock_factors(cp_data)
            target_codes = strategy.select_stocks(signal_date, stock_factors, top_n)

            # 检查持仓超时
            for code in list(positions.keys()):
                positions[code].holding_days += 1
                if positions[code].holding_days > 5:  # 最大持仓5天
                    self._execute_sell(positions, cash, trades, code, trade_date, 'max_days')

            # 调仓
            current_codes = set(positions.keys())
            new_codes = set(target_codes[:top_n])

            # 卖出不在新目标中的持仓
            for code in current_codes - new_codes:
                self._execute_sell(positions, cash, trades, code, trade_date, 'rebalance')

            # 买入新目标
            for code in new_codes - current_codes:
                self._execute_buy(positions, cash, trades, pending_bought, code, trade_date)

            # 记录净值
            total_value = cash + sum(
                pos.quantity * self._get_price(pos.code, trade_date)
                for pos in positions.values()
            )
            equity_curve.append({
                'date': trade_date,
                'total_value': total_value,
                'cash': cash,
                'position_value': total_value - cash
            })

            # 清除当日买入记录
            pending_bought.clear()

        # 计算统计
        return self._calculate_stats(
            initial_capital, cash, positions, equity_curve, trades
        )

    def _get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        result = self.duckdb.query(f"""
            SELECT DISTINCT trade_date
            FROM daily_kline
            WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
            ORDER BY trade_date
        """)
        if result.success:
            return result.data['trade_date'].dt.strftime('%Y-%m-%d').tolist()
        return []

    def _get_cp_at_date(self, date: str) -> List[Dict]:
        """获取指定日期的战力数据"""
        return self.cp_store.get_cp_history_by_date(date)

    def _get_price(self, code: str, date: str) -> float:
        """获取指定日期的收盘价"""
        result = self.duckdb.get_klines(code, end_date=date, limit=1)
        if result.success and result.data is not None and len(result.data) > 0:
            return float(result.data.iloc[0]['close'])
        return 0.0

    def _build_stock_factors(self, cp_data: List[Dict]) -> Dict[str, 'StockFactor']:
        """将战力数据转换为 StockFactor 字典"""
        from .strategies import StockFactor

        result = {}
        for item in cp_data:
            factor = StockFactor(
                code=item.get('code', ''),
                name=item.get('name', ''),
                date=item.get('recorded_at', ''),
                close=item.get('price', 0) or item.get('close', 0),
                change_pct=item.get('change_pct', 0),
                total_cp=item.get('total_cp', 0),
                growth_score=item.get('growth_score', 0),
                value_score=item.get('value_score', 0),
                momentum_score=item.get('momentum_score', 0),
                quality_score=item.get('quality_score', 0),
                is_limit_up=item.get('change_pct', 0) >= 9.9,
                is_limit_down=item.get('change_pct', 0) <= -9.9,
                is_suspended=False
            )
            result[factor.code] = factor
        return result

    def _execute_buy(self, positions: Dict, cash: float, trades: List,
                     pending_bought: Set, code: str, date: str):
        """执行买入"""
        price = self._get_price(code, date)
        if price <= 0:
            return

        # 获取股票名称
        cp_data = self._get_cp_at_date(date)
        name = next((s['name'] for s in cp_data if s['code'] == code), code)

        # 计算可买入数量（100股整数倍）
        # 考虑交易费用
        available_cash = cash * 0.99  # 预留1%费用
        max_qty = int(available_cash / price) // 100 * 100
        if max_qty < 100:
            return

        # 计算费用
        gross_amount = price * max_qty
        commission = max(gross_amount * self.COMMISSION_RATE, self.MIN_COMMISSION)
        transfer_fee = gross_amount * self.TRANSFER_FEE_RATE
        total_cost = gross_amount + commission + transfer_fee

        if total_cost > cash:
            # 资金不足，减少数量
            max_qty = int((cash * 0.99) / (price * (1 + self.COMMISSION_RATE + self.TRANSFER_FEE_RATE))) // 100 * 100
            if max_qty < 100:
                return
            gross_amount = price * max_qty
            commission = max(gross_amount * self.COMMISSION_RATE, self.MIN_COMMISSION)
            transfer_fee = gross_amount * self.TRANSFER_FEE_RATE
            total_cost = gross_amount + commission + transfer_fee

        # 执行
        cash -= total_cost
        positions[code] = Position(
            code=code,
            name=name,
            quantity=max_qty,
            avg_cost=price,
            buy_date=date,
            holding_days=0
        )
        pending_bought.add(code)

        trades.append(BacktestTrade(
            date=date,
            action='buy',
            code=code,
            name=name,
            price=price,
            quantity=max_qty,
            amount=gross_amount,
            commission=commission + transfer_fee
        ))

    def _execute_sell(self, positions: Dict, cash: float, trades: List,
                     code: str, date: str, reason: str):
        """执行卖出"""
        if code not in positions:
            return

        pos = positions[code]
        price = self._get_price(code, date)
        if price <= 0:
            return

        # 计算费用
        gross_amount = price * pos.quantity
        commission = max(gross_amount * self.COMMISSION_RATE, self.MIN_COMMISSION)
        stamp_tax = gross_amount * self.STAMP_TAX_RATE
        transfer_fee = gross_amount * self.TRANSFER_FEE_RATE
        total_cost = commission + stamp_tax + transfer_fee

        net_amount = gross_amount - total_cost
        cash += net_amount

        trades.append(BacktestTrade(
            date=date,
            action='sell',
            code=code,
            name=pos.name,
            price=price,
            quantity=pos.quantity,
            amount=net_amount,
            commission=total_cost,
            reason=reason
        ))

        del positions[code]

    def _calculate_stats(self, initial_capital: float, final_cash: float,
                        positions: Dict, equity_curve: List[Dict],
                        trades: List[BacktestTrade]) -> BacktestStats:
        """计算回测统计"""
        # 计算最终市值
        last_date = equity_curve[-1]['date'] if equity_curve else ''
        final_value = final_cash + sum(
            pos.quantity * self._get_price(pos.code, last_date)
            for pos in positions.values()
        )

        total_return = (final_value - initial_capital) / initial_capital

        # 年化收益率（假设一年250个交易日）
        days = len(equity_curve) if equity_curve else 1
        annualized_return = (1 + total_return) ** (250 / days) - 1 if days > 0 else 0

        # 计算夏普比率和最大回撤
        sharpe = 0.0
        max_drawdown = 0.0

        if len(equity_curve) > 1:
            returns = []
            prev_value = equity_curve[0]['total_value']
            for eq in equity_curve[1:]:
                ret = (eq['total_value'] - prev_value) / prev_value
                returns.append(ret)
                prev_value = eq['total_value']

            if returns:
                mean_ret = sum(returns) / len(returns)
                std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / len(returns))
                if std_ret > 0:
                    sharpe = (mean_ret / std_ret) * math.sqrt(250)

            # 最大回撤
            peak = equity_curve[0]['total_value']
            for eq in equity_curve:
                if eq['total_value'] > peak:
                    peak = eq['total_value']
                drawdown = (peak - eq['total_value']) / peak if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        # 胜率
        sell_trades = [t for t in trades if t.action == 'sell']
        win_count = 0
        for t in sell_trades:
            if t.amount > 0:  # 简化判断
                win_count += 1
        win_rate = win_count / len(sell_trades) if sell_trades else 0

        return BacktestStats(
            initial_capital=initial_capital,
            final_value=final_value,
            total_return=total_return * 100,
            annualized_return=annualized_return * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown * 100,
            win_rate=win_rate * 100,
            total_trades=len(trades),
            equity_curve=equity_curve,
            trades=[{
                'date': t.date,
                'action': t.action,
                'code': t.code,
                'name': t.name,
                'price': t.price,
                'quantity': t.quantity,
                'amount': t.amount,
                'commission': t.commission,
                'reason': t.reason
            } for t in trades]
        )