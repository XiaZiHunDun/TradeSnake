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
            trades = [t for t in trades if t.get('created_at', '') >= start_date]
        if end_date:
            trades = [t for t in trades if t.get('created_at', '') <= end_date]

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

        # 按股票分组计算盈亏
        stock_profits: Dict[str, List[float]] = {}

        for trade in sell_trades:
            code = trade.get('code')
            if code not in stock_profits:
                stock_profits[code] = []
            # 简化：卖出收入 - 印花税 - 佣金 = 净利润
            stock_profits[code].append(trade.get('total_amount', 0))

        # 计算每只股票的盈亏
        for code, profits in stock_profits.items():
            if profits:
                # 简化处理：取平均
                avg_profit = sum(profits) / len(profits)
                total_profit += avg_profit
                if avg_profit > 0:
                    winning_trades += 1
                    max_profit = max(max_profit, avg_profit)
                elif avg_profit < 0:
                    losing_trades += 1
                    max_loss = min(max_loss, avg_profit)

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
            sell_date = datetime.fromisoformat(sell.get('created_at', datetime.now().isoformat()))

            # 查找对应的买入交易
            buy_trades = [t for t in self.db.get_trades(limit=10000)
                         if t.get('action') == 'buy' and t.get('code') == code
                         and t.get('created_at', '') < sell.get('created_at', '')]

            if buy_trades:
                # 找最早的买入
                earliest_buy = min(buy_trades, key=lambda x: x.get('created_at', ''))
                buy_date = datetime.fromisoformat(earliest_buy.get('created_at', datetime.now().isoformat()))
                holding_days = (sell_date - buy_date).days
                holding_days_list.append(holding_days)

        return sum(holding_days_list) / len(holding_days_list) if holding_days_list else 0

    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤（简化版）"""
        # 获取账户历史资产曲线
        flows = self.db.get_account_flows(limit=10000)
        if not flows:
            return 0

        # 构建资产曲线
        assets_history = []
        current_assets = self.db.get_account().get('initial_cash', 20000)

        # 按时间排序
        flows_sorted = sorted(flows, key=lambda x: x.get('created_at', ''))

        for flow in flows_sorted:
            change_type = flow.get('change_type', '')
            amount = abs(flow.get('amount', 0))

            if change_type in ('buy', 'sell', 'dividend'):
                if change_type == 'buy':
                    current_assets -= amount
                elif change_type == 'sell':
                    current_assets += amount
                elif change_type == 'dividend':
                    current_assets += amount

                assets_history.append(current_assets)

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
            created_at = t.get('created_at', '')
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at)
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

        # 简化计算
        total_profit = sum(t.get('total_amount', 0) for t in sell_trades) - \
                       sum(t.get('total_amount', 0) for t in buy_trades)

        return [{
            'year': year,
            'month': month,
            'total_trades': len(monthly_trades),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'total_profit': round(total_profit, 2)
        }]
