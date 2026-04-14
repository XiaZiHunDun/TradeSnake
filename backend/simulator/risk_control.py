"""
风控限制 - RiskControl v19.1
"""

from typing import Dict, List, Tuple, Optional
from .database import get_db


class RiskControl:
    """风控限制 v19.1

    单人模拟炒股风控规则：
    1. 单股持仓上限：30%总资产
    2. 单日买入限额：80%总资产
    3. 单日交易次数上限：10次
    4. 最小买入单位：100股（1手）
    5. 涨跌停限制
    6. T+1限制
    7. 流动性检查（成交量）
    """

    # 风控参数
    MAX_POSITION_RATIO = 0.30  # 单股持仓上限30%
    MAX_DAILY_BUY_RATIO = 0.80  # 单日买入限额80%
    MAX_DAILY_TRADES = 10  # 单日交易次数
    MIN_TRADE_UNIT = 100  # 最小买入单位（1手=100股）
    MIN_LIQUIDITY_RATIO = 0.01  # 最小成交量比例（占流通股本1%）

    @classmethod
    def check_all(cls, action: str, code: str, quantity: int,
                  price: float, account, portfolio) -> Tuple[bool, str]:
        """综合风控检查

        Args:
            action: 'buy' | 'sell'
            code: 股票代码
            quantity: 数量
            price: 价格
            account: Account实例
            portfolio: Portfolio实例

        Returns:
            (can_trade, reason): 是否可以交易，原因
        """
        # 1. 基础检查
        if quantity <= 0:
            return False, "交易数量必须大于0"

        if quantity % cls.MIN_TRADE_UNIT != 0:
            return False, f"交易数量必须是{cls.MIN_TRADE_UNIT}的整数倍"

        # 2. 涨跌停检查
        from backend.data_manager.fetcher import get_single_stock_data
        stock = get_single_stock_data(code)
        if stock:
            if action == 'buy' and stock.get('is_limit_up'):
                return False, "涨停无法买入"
            if action == 'sell' and stock.get('is_limit_down'):
                return False, "跌停无法卖出"

        # 3. 买入检查
        if action == 'buy':
            # 资金检查
            can_buy, reason = account.can_buy(price, quantity)
            if not can_buy:
                return False, reason

            # 单股持仓上限检查
            total_assets = account.total_assets
            position_value = quantity * price
            current_holding = portfolio.get_holding(code)
            current_value = current_holding.get('total_quantity', 0) * price if current_holding else 0

            new_position_ratio = (current_value + position_value) / total_assets if total_assets > 0 else 1
            if new_position_ratio > cls.MAX_POSITION_RATIO:
                max_quantity = int((total_assets * cls.MAX_POSITION_RATIO - current_value) / price)
                max_quantity = (max_quantity // cls.MIN_TRADE_UNIT) * cls.MIN_TRADE_UNIT
                return False, f"单股持仓上限{cls.MAX_POSITION_RATIO*100}%，最多买入{max_quantity}股"

            # 单日买入限额检查
            today_buy_amount = cls._get_today_buy_amount(code)
            if today_buy_amount + position_value > total_assets * cls.MAX_DAILY_BUY_RATIO:
                available = total_assets * cls.MAX_DAILY_BUY_RATIO - today_buy_amount
                max_q = int(available / price)
                max_q = (max_q // cls.MIN_TRADE_UNIT) * cls.MIN_TRADE_UNIT
                return False, f"单日买入限额{cls.MAX_DAILY_BUY_RATIO*100}%，剩余可用额度约{max_q}股"

            # 单日交易次数检查
            if cls._get_today_trade_count() >= cls.MAX_DAILY_TRADES:
                return False, f"单日交易次数已达上限{cls.MAX_DAILY_TRADES}次"

        # 4. 卖出检查
        elif action == 'sell':
            can_sell, reason = account.can_sell(code, quantity)
            if not can_sell:
                return False, reason

            # 持仓数量检查
            holding = portfolio.get_holding(code)
            if not holding:
                return False, f"没有持有{code}"
            if holding.get('total_quantity', 0) < quantity:
                return False, f"持仓不足，持有{holding.get('total_quantity', 0)}股"

        # 5. 流动性检查（可选，仅做提示）
        if stock and action == 'buy':
            avg_volume = stock.get('avg_daily_amount_20d', 0)
            if avg_volume > 0:
                position_value = quantity * price
                if position_value / avg_volume > 0.1:  # 超过日均成交额10%
                    # 仅做警告，不阻止
                    pass

        return True, "风控检查通过"

    @classmethod
    def _get_today_buy_amount(cls, code: str = None) -> float:
        """获取今日买入总额"""
        db = get_db()
        today = db.get_today_date()

        trades = db.get_trades(limit=10000)
        today_buys = [t for t in trades
                     if t.get('action') == 'buy'
                     and t.get('created_at', '').startswith(today)]

        if code:
            today_buys = [t for t in today_buys if t.get('code') == code]

        return sum(t.get('total_amount', 0) for t in today_buys)

    @classmethod
    def _get_today_trade_count(cls) -> int:
        """获取今日交易次数"""
        db = get_db()
        today = db.get_today_date()

        trades = db.get_trades(limit=10000)
        today_trades = [t for t in trades
                       if t.get('created_at', '').startswith(today)]

        return len(today_trades)

    @classmethod
    def check_position_limit(cls, code: str, quantity: int, price: float,
                             total_assets: float, current_quantity: int) -> Tuple[bool, str]:
        """检查单股持仓上限"""
        if total_assets <= 0:
            return False, "总资产无效"

        new_value = (current_quantity + quantity) * price
        ratio = new_value / total_assets

        if ratio > cls.MAX_POSITION_RATIO:
            max_q = int(total_assets * cls.MAX_POSITION_RATIO / price)
            max_q = (max_q // cls.MIN_TRADE_UNIT) * cls.MIN_TRADE_UNIT
            return False, f"单股持仓上限{cls.MAX_POSITION_RATIO*100}%，最多持有{max_q}股"

        return True, "持仓检查通过"

    @classmethod
    def check_daily_buy_limit(cls, today_buy_amount: float, position_value: float,
                              total_assets: float) -> Tuple[bool, str]:
        """检查单日买入限额"""
        if total_assets <= 0:
            return False, "总资产无效"

        if today_buy_amount + position_value > total_assets * cls.MAX_DAILY_BUY_RATIO:
            available = total_assets * cls.MAX_DAILY_BUY_RATIO - today_buy_amount
            return False, f"单日买入限额{cls.MAX_DAILY_BUY_RATIO*100}%，剩余可用额度约{available:.2f}元"

        return True, "日买入限额检查通过"

    @classmethod
    def check_liquidity(cls, code: str, quantity: int, price: float) -> Tuple[bool, str]:
        """检查流动性是否充足（警告级别）"""
        from backend.data_manager.fetcher import get_single_stock_data

        stock = get_single_stock_data(code)
        if not stock:
            return True, "流动性检查通过（无数据）"

        avg_volume = stock.get('avg_daily_amount_20d', 0)
        if avg_volume <= 0:
            return True, "流动性检查通过（无成交量数据）"

        position_value = quantity * price
        liquidity_ratio = position_value / avg_volume

        if liquidity_ratio > 0.1:
            return False, f"买入金额{position_value:.2f}元超过日均成交额{avg_volume:.2f}元的10%，流动性可能不足"

        return True, "流动性检查通过"
