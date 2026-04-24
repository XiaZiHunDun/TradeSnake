"""
交易统计 - Stats v19.1
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from .database import get_db


class Stats:
    """交易统计 v19.1"""

    def __init__(self):
        self.db = get_db()

    def get_summary(self, start_date: str = None, end_date: str = None) -> Dict:
        """获取交易统计摘要

        Args:
            start_date: 开始日期 (ISO格式)
            end_date: 结束日期 (ISO格式)

        Returns:
            统计摘要
        """
        trades = self.db.get_trades(limit=10000)
        if not trades:
            return self._empty_summary()

        # 按日期筛选
        if start_date:
            trades = [t for t in trades if t.get('recorded_at', '') >= start_date]
        if end_date:
            trades = [t for t in trades if t.get('recorded_at', '') <= end_date]

        if not trades:
            return self._empty_summary()

        # 基本统计
        total_trades = len(trades)
        buy_trades = [t for t in trades if t.get('action') == 'buy']
        sell_trades = [t for t in trades if t.get('action') == 'sell']

        # 盈亏统计
        winning_trades = 0
        losing_trades = 0
        total_profit = 0
        max_profit = 0
        max_loss = 0

        # 按股票分组计算盈亏（使用FIFO匹配买卖）
        stock_profits: Dict[str, List[float]] = {}

        for sell in sell_trades:
            code = sell.get('code')
            if code not in stock_profits:
                stock_profits[code] = []

            # 使用FIFO匹配对应的买入批次计算真实盈亏
            sell_quantity = sell.get('quantity', 0)

            # 卖出净收入（扣除费用后）- total_amount在卖出时已是扣税佣金净额
            net_sell_proceeds = sell.get('total_amount', 0)

            # 通过FIFO找到对应的买入成本
            matched_buy_cost = self._get_fifo_buy_cost(code, sell.get('recorded_at', ''), sell_quantity)

            # 真实盈亏 = 卖出净收入 - 买入成本
            real_profit = net_sell_proceeds - matched_buy_cost

            stock_profits[code].append(real_profit)

        # 计算每只股票的盈亏
        for code, profits in stock_profits.items():
            for profit in profits:
                total_profit += profit
                if profit > 0:
                    winning_trades += 1
                    max_profit = max(max_profit, profit)
                elif profit < 0:
                    losing_trades += 1
                    max_loss = min(max_loss, profit)

        # 胜率
        total_closed = winning_trades + losing_trades
        win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0

        # 平均持仓天数
        avg_holding_days = self._calculate_avg_holding_days(sell_trades)

        # 最大回撤（简化版）
        max_drawdown = self._calculate_max_drawdown()

        return {
            'total_trades': total_trades,
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'total_profit': round(total_profit, 2),
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'max_drawdown': round(max_drawdown, 2),
            'avg_holding_days': round(avg_holding_days, 1),
            'start_date': start_date,
            'end_date': end_date,
            'calculated_at': datetime.now().isoformat()
        }

    def _get_fifo_buy_cost(self, code: str, sell_date: str, sell_quantity: int) -> float:
        """通过FIFO匹配计算对应卖出的买入成本

        Args:
            code: 股票代码
            sell_date: 卖出日期（用于排除当日买入）
            sell_quantity: 卖出数量

        Returns:
            对应的买入成本总额
        """
        from datetime import datetime as dt

        # 获取该股票在卖出日前的所有买入批次（按时间顺序FIFO）
        batches = self.db.get_holding_batches_for_sell(code)
        # 过滤出在卖出日期之前的批次
        cutoff_date = dt.fromisoformat(sell_date).date() if sell_date else dt.now().date()
        eligible_batches = [
            b for b in batches
            if dt.fromisoformat(b.get('bought_at', dt.now().isoformat())).date() < cutoff_date
        ]

        total_cost = 0
        remaining = sell_quantity

        for batch in eligible_batches:
            if remaining <= 0:
                break
            batch_qty = batch.get('quantity', 0)
            reduce_qty = min(remaining, batch_qty)
            cost_price = batch.get('cost_price', 0)
            total_cost += reduce_qty * cost_price
            remaining -= reduce_qty

        return total_cost

    def _empty_summary(self) -> Dict:
        """返回空统计"""
        return {
            'total_trades': 0,
            'buy_trades': 0,
            'sell_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_profit': 0,
            'max_profit': 0,
            'max_loss': 0,
            'max_drawdown': 0,
            'avg_holding_days': 0,
            'start_date': None,
            'end_date': None,
            'calculated_at': datetime.now().isoformat()
        }

    def _calculate_avg_holding_days(self, sell_trades: List[Dict]) -> float:
        """计算平均持仓天数"""
        if not sell_trades:
            return 0

        holding_days_list = []
        for sell in sell_trades:
            code = sell.get('code')
            sell_date = datetime.fromisoformat(sell.get('recorded_at', datetime.now().isoformat()))

            # 查找对应的买入交易
            buy_trades = [t for t in self.db.get_trades(limit=10000)
                         if t.get('action') == 'buy' and t.get('code') == code
                         and t.get('recorded_at', '') < sell.get('recorded_at', '')]

            if buy_trades:
                # 找最早的买入
                earliest_buy = min(buy_trades, key=lambda x: x.get('recorded_at', ''))
                buy_date = datetime.fromisoformat(earliest_buy.get('recorded_at', datetime.now().isoformat()))
                holding_days = (sell_date - buy_date).days
                holding_days_list.append(holding_days)

        return sum(holding_days_list) / len(holding_days_list) if holding_days_list else 0

    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤（使用持仓快照）

        使用每日持仓快照表计算组合价值的最大回撤，
        比单纯用资金流水更准确。
        """
        # 尝试从持仓快照获取历史市值
        portfolio_history = self.db.get_portfolio_value_history()
        if not portfolio_history or len(portfolio_history) < 2:
            # 兜底：使用资金流水估算
            return self._calculate_max_drawdown_from_flows()

        # 使用快照中的总资产（total_value已包含现金+持仓市值）
        assets_history = []

        for snapshot in portfolio_history:
            market_value = snapshot.get('total_value', 0)
            assets_history.append(market_value)

        if not assets_history:
            return 0

        # 计算最大回撤
        peak = assets_history[0]
        max_drawdown = 0

        for assets in assets_history:
            if assets > peak:
                peak = assets
            drawdown = (peak - assets) / peak * 100 if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    def _calculate_max_drawdown_from_flows(self) -> float:
        """通过资金流水估算最大回撤（兜底方案）

        不考虑持仓市值变化，仅跟踪现金变化。
        注意：此方法不够准确，仅在无快照数据时使用。
        """
        flows = self.db.get_account_flows(limit=10000)
        if not flows:
            return 0

        initial_cash = self.db.get_account().get('initial_cash', 20000)
        current_cash = initial_cash
        peak = initial_cash
        max_drawdown = 0

        # 按时间排序
        flows_sorted = sorted(flows, key=lambda x: x.get('created_at', ''))

        for flow in flows_sorted:
            change_type = flow.get('change_type', '')
            amount = flow.get('amount', 0)

            # 买卖直接影响现金
            if change_type in ('buy', 'buy_freeze'):
                # 买入冻结/扣除
                current_cash += amount  # amount是负数
            elif change_type in ('sell', 'sell_proceeds', 'buy_refund', 'buy_unfreeze', 'dividend'):
                # 卖出收入/解冻/分红
                current_cash += amount  # amount是正数
            elif change_type == 'commission':
                current_cash += amount  # 佣金是负数

            # 更新峰值
            if current_cash > peak:
                peak = current_cash

            # 计算回撤
            if peak > 0:
                drawdown = (peak - current_cash) / peak * 100
                max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    def get_stock_stats(self, code: str) -> Dict:
        """获取单只股票交易统计"""
        trades = [t for t in self.db.get_trades(limit=10000) if t.get('code') == code]
        if not trades:
            return {}

        buy_trades = [t for t in trades if t.get('action') == 'buy']
        sell_trades = [t for t in trades if t.get('action') == 'sell']

        total_bought = sum(t.get('quantity', 0) for t in buy_trades)
        total_sold = sum(t.get('quantity', 0) for t in sell_trades)
        avg_buy_price = (sum(t.get('price', 0) * t.get('quantity', 0) for t in buy_trades) / total_bought
                        if total_bought > 0 else 0)
        avg_sell_price = (sum(t.get('price', 0) * t.get('quantity', 0) for t in sell_trades) / total_sold
                         if total_sold > 0 else 0)

        return {
            'code': code,
            'name': buy_trades[0].get('name', code) if buy_trades else code,
            'total_bought': total_bought,
            'total_sold': total_sold,
            'avg_buy_price': round(avg_buy_price, 2),
            'avg_sell_price': round(avg_sell_price, 2),
            'buy_count': len(buy_trades),
            'sell_count': len(sell_trades),
            'total_trades': len(trades)
        }

    def get_monthly_stats(self, year: int = None, month: int = None) -> List[Dict]:
        """获取月度统计"""
        if year is None:
            now = datetime.now()
            year = now.year
            month = now.month

        trades = self.db.get_trades(limit=10000)

        # 筛选月度数据
        monthly_trades = []
        for t in trades:
            recorded_at = t.get('recorded_at', '')
            if recorded_at:
                try:
                    dt = datetime.fromisoformat(recorded_at)
                    if dt.year == year and dt.month == month:
                        monthly_trades.append(t)
                except:
                    continue

        if not monthly_trades:
            return [{
                'year': year,
                'month': month,
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
                'total_profit': 0
            }]

        buy_trades = [t for t in monthly_trades if t.get('action') == 'buy']
        sell_trades = [t for t in monthly_trades if t.get('action') == 'sell']

        # 使用FIFO匹配计算真实月度盈亏
        total_profit = 0
        for sell in sell_trades:
            code = sell.get('code')
            sell_quantity = sell.get('quantity', 0)
            net_sell_proceeds = sell.get('total_amount', 0)
            matched_buy_cost = self._get_fifo_buy_cost(code, sell.get('recorded_at', ''), sell_quantity)
            total_profit += net_sell_proceeds - matched_buy_cost

        return [{
            'year': year,
            'month': month,
            'total_trades': len(monthly_trades),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'total_profit': round(total_profit, 2)
        }]
