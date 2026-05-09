"""
账户管理 - Account Management v19.1
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from .database import get_db
from backend.engine import TRADE_COST

# 交易费用（统一从 engine.constants 导入）
COMMISSION_RATE = TRADE_COST['commission']
MIN_COMMISSION = TRADE_COST['min_commission']
STAMP_TAX_RATE = TRADE_COST['stamp_tax']
TRANSFER_FEE_RATE = TRADE_COST['transfer_fee']


class Account:
    """模拟交易账户 v19.1"""

    def __init__(self):
        self.db = get_db()

    @property
    def cash(self) -> float:
        """可用资金"""
        return self.db.get_account().get('cash', 0)

    @property
    def frozen_cash(self) -> float:
        """冻结资金（挂单未成交）"""
        # 从pending订单计算冻结资金
        pending = self.db.get_pending_orders()
        frozen = sum(o.get('frozen_amount', 0) for o in pending if o.get('action') == 'buy')
        return frozen

    @property
    def initial_cash(self) -> float:
        """初始资金"""
        return self.db.get_account().get('initial_cash', 20000)

    @property
    def total_assets(self) -> float:
        """总资产 = 可用资金 + 冻结资金 + 持仓市值"""
        return self.cash + self.frozen_cash + self.get_market_value()

    @property
    def total_profit(self) -> float:
        """总盈亏"""
        return self.total_assets - self.initial_cash

    @property
    def profit_rate(self) -> float:
        """盈亏比例"""
        if self.initial_cash <= 0:
            return 0
        return (self.total_profit / self.initial_cash) * 100

    @property
    def peak_assets(self) -> float:
        """历史最高总资产（用于计算组合回撤）"""
        return self.db.get_account().get('peak_assets', self.initial_cash)

    def update_peak_assets(self) -> bool:
        """更新历史最高总资产（当总资产创新高时调用）"""
        current = self.total_assets
        peak = self.peak_assets
        if current > peak:
            account = self.db.get_account()
            account['peak_assets'] = current
            return self.db.update_account(**account)
        return False

    def get_market_value(self) -> float:
        """获取持仓总市值（使用SQLite stocks表，无网络请求）"""
        import logging
        logger = logging.getLogger(__name__)

        holdings = self.db.get_holdings()
        total = 0.0
        for h in holdings:
            code = h.get('code', '')
            quantity = h.get('total_quantity', 0)
            try:
                # 使用SQLite stocks表的价格（避免网络请求）
                lookup_code = code.replace('sh', '').replace('sz', '')
                stock = self.db.get_stock(lookup_code)
                if stock and stock.get('price', 0) > 0:
                    total += stock.get('price', 0) * quantity
            except Exception as e:
                logger.warning(f"get_market_value: 获取 {code} 市价失败: {e}")
        return total

    def get_summary(self) -> Dict:
        """获取账户摘要"""
        return {
            'cash': round(self.cash, 2),
            'frozen_cash': round(self.frozen_cash, 2),
            'initial_cash': round(self.initial_cash, 2),
            'total_market_value': round(self.get_market_value(), 2),
            'total_assets': round(self.total_assets, 2),
            'total_profit': round(self.total_profit, 2),
            'profit_rate': round(self.profit_rate, 2),
            'updated_at': datetime.now().isoformat()
        }

    def update_cash(self, new_cash: float) -> bool:
        """更新现金"""
        return self.db.update_account(new_cash)

    def calculate_freeze(self, quantity: int, price: float, is_buy: bool = True) -> float:
        """计算冻结金额（v19.1新增）

        买入冻结 = 数量×价格 + 预估佣金 + 预估过户费
        """
        amount = quantity * price
        if is_buy:
            commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
            transfer_fee = amount * TRANSFER_FEE_RATE
            return round(amount + commission + transfer_fee, 2)
        return round(amount, 2)

    def freeze_for_order(self, order_id: int, code: str, amount: float) -> bool:
        """为委托单冻结资金（v19.1新增）"""
        # 冻结资金通过创建订单时记录，不需要单独操作
        # 此方法保留用于接口一致性
        return True

    def unfreeze_for_order(self, order_id: int, unfilled_amount: float,
                          actual_cost: float, order_id_ref: int = None) -> bool:
        """解冻剩余资金（v19.1新增）

        Args:
            order_id: 订单ID
            unfilled_amount: 未成交金额
            actual_cost: 实际成交金额
            order_id_ref: 关联订单ID
        """
        if unfilled_amount <= 0:
            return True

        # 资金已扣减，只需记录解冻流水
        self.db.record_flow({
            'change_type': 'buy_unfreeze',
            'amount': unfilled_amount,
            'balance_after': self.cash + unfilled_amount,
            'order_id': order_id_ref,
            'remark': f'委托单{order_id}解冻'
        })
        return True

    def can_buy(self, price: float, quantity: int) -> Tuple[bool, str]:
        """检查是否可以买入"""
        freeze_amount = self.calculate_freeze(quantity, price, is_buy=True)
        available = self.cash

        if available < freeze_amount:
            return False, f"资金不足，需要{freeze_amount:.2f}元（含预估费用），可用{available:.2f}元"

        if quantity <= 0:
            return False, "买入数量必须大于0"

        return True, "可以买入"

    def can_sell(self, code: str, quantity: int) -> Tuple[bool, str]:
        """检查是否可以卖出（T+1限制）"""
        holding = self.db.get_holding(code)
        if not holding:
            return False, f"没有持有{code}"

        available = self.db.get_today_bought_quantity(code)
        total_quantity = holding.get('total_quantity', 0)
        sellable = total_quantity - available

        if quantity > sellable:
            return False, f"可卖数量不足，持有{total_quantity}股，今日买入{available}股（需T+1）"

        if quantity <= 0:
            return False, "卖出数量必须大于0"

        return True, "可以卖出"

    def deduct_cost(self, total_cost: float) -> bool:
        """扣除实际成交成本（v19.1新增）"""
        new_cash = self.cash - total_cost
        self.db.update_account(new_cash)
        return True

    def add_proceeds(self, proceeds: float) -> bool:
        """增加卖出收入（v19.1新增）"""
        new_cash = self.cash + proceeds
        self.db.update_account(new_cash)
        return True

    def record_commission(self, order_id: int, commission: float, stamp_tax: float = 0,
                         transfer_fee: float = 0) -> None:
        """记录费用流水（v19.1新增）"""
        if commission > 0:
            self.db.record_flow({
                'change_type': 'commission',
                'amount': -commission,
                'balance_after': self.cash,
                'order_id': order_id,
                'remark': f'佣金'
            })
        if stamp_tax > 0:
            self.db.record_flow({
                'change_type': 'stamp_tax',
                'amount': -stamp_tax,
                'balance_after': self.cash,
                'order_id': order_id,
                'remark': f'印花税'
            })
        if transfer_fee > 0:
            self.db.record_flow({
                'change_type': 'transfer_fee',
                'amount': -transfer_fee,
                'balance_after': self.cash,
                'order_id': order_id,
                'remark': f'过户费'
            })

    def reset(self) -> bool:
        """重置账户"""
        self.db.delete_all_holdings()
        self.db.init_account()
        # 清空流水（可选）
        return True
