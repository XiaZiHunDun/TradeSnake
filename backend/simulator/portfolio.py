"""
持仓管理 - Portfolio Management v19.1
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from .database import get_db


class Portfolio:
    """持仓管理 v19.1"""

    def __init__(self):
        self.db = get_db()

    def get_holdings(self) -> List[Dict]:
        """获取所有持仓"""
        return self.db.get_holdings()

    def get_holding(self, code: str) -> Optional[Dict]:
        """获取指定持仓"""
        return self.db.get_holding(code)

    def add_holding(self, code: str, name: str, quantity: int, cost_price: float,
                   bought_at: str = None, stop_loss: float = 0, take_profit: float = 0) -> int:
        """添加持仓批次（买入成交）

        Args:
            code: 股票代码
            name: 股票名称
            quantity: 数量
            cost_price: 成本价
            bought_at: 买入时间
            stop_loss: 止损价
            take_profit: 止盈价
        """
        return self.db.add_holding_batch(code, name, quantity, cost_price, bought_at, 0, stop_loss, take_profit)

    def reduce_holding(self, code: str, quantity: int) -> Tuple[bool, List[Dict]]:
        """减少持仓（FIFO）

        Returns:
            (success, batch_details): 是否成功，扣减的批次明细
        """
        batches = self.db.get_holding_batches_for_sell(code)
        if not batches:
            return False, []

        remaining = quantity
        details = []

        for batch in batches:
            if remaining <= 0:
                break
            batch_qty = batch.get('quantity', 0)
            reduce_qty = min(remaining, batch_qty)
            self.db.reduce_holding_batch(batch['id'], reduce_qty)
            details.append({
                'batch_id': batch['id'],
                'quantity': reduce_qty,
                'cost_price': batch.get('cost_price', 0)
            })
            remaining -= reduce_qty

        return remaining == 0, details

    def freeze_shares(self, code: str, quantity: int) -> bool:
        """卖出前冻结股份（v19.1新增）

        注意：单人模拟中，卖出直接冻结对应数量
        实际实现时通过T+1检查控制可卖数量
        """
        return True

    def unfreeze_shares(self, code: str, quantity: int) -> bool:
        """撤单时解冻剩余股份（v19.1新增）"""
        return True

    def get_holding_value(self, code: str, current_price: float) -> float:
        """计算持仓价值"""
        holding = self.db.get_holding(code)
        if not holding:
            return 0
        return holding.get('total_quantity', 0) * current_price

    def get_holding_profit(self, code: str, current_price: float) -> Dict:
        """计算持仓盈亏"""
        holding = self.db.get_holding(code)
        if not holding:
            return {'profit': 0, 'profit_rate': 0}

        quantity = holding.get('total_quantity', 0)
        cost_price = holding.get('avg_cost_price', 0)
        cost_total = cost_price * quantity
        value_total = current_price * quantity
        profit = value_total - cost_total
        profit_rate = (profit / cost_total * 100) if cost_total > 0 else 0

        return {
            'profit': round(profit, 2),
            'profit_rate': round(profit_rate, 2),
            'cost_total': round(cost_total, 2),
            'value_total': round(value_total, 2)
        }

    def get_position_ratio(self, code: str, total_assets: float) -> float:
        """获取持仓占比（v19.1新增）"""
        holding = self.db.get_holding(code)
        if not holding or total_assets <= 0:
            return 0
        quantity = holding.get('total_quantity', 0)
        return quantity / total_assets

    def get_total_value(self, prices: Dict[str, float]) -> float:
        """计算持仓总市值"""
        holdings = self.db.get_holdings()
        total = 0
        for h in holdings:
            code = h.get('code')
            quantity = h.get('total_quantity', 0)
            price = prices.get(code, 0)
            total += price * quantity
        return total

    def adjust_for_ex_rights(self, code: str, bonus_ratio: float = 0,
                            cash_dividend: float = 0) -> bool:
        """除权除息处理（v19.1新增）

        Args:
            code: 股票代码
            bonus_ratio: 送股比例（如0.5 = 每10股送5股）
            cash_dividend: 每股现金分红（含税，元/股）

        处理逻辑：
        1. 送股：持仓数量增加，成本价相应降低
        2. 现金分红：持仓成本价调减，分红入账
        """
        batches = self.db.get_holding_batches(code)
        if not batches:
            return False

        for batch in batches:
            old_qty = batch.get('quantity', 0)
            old_cost = batch.get('cost_price', 0)

            if old_qty <= 0 or old_cost <= 0:
                continue

            # 送股处理
            if bonus_ratio > 0:
                new_qty = int(old_qty * (1 + bonus_ratio))
                # 成本价相应降低
                new_cost = (old_qty * old_cost) / new_qty if new_qty > 0 else old_cost
            else:
                new_qty = old_qty
                new_cost = old_cost

            # 现金分红处理（扣税，简化处理按10%）
            if cash_dividend > 0:
                # 持有不足1月10%，1月-1年10%，超过1年0%（简化）
                holding_days = (datetime.now() - datetime.fromisoformat(batch.get('bought_at', datetime.now().isoformat()))).days
                if holding_days < 30:
                    tax_rate = 0.20
                elif holding_days < 365:
                    tax_rate = 0.10
                else:
                    tax_rate = 0
                net_dividend = cash_dividend * old_qty * (1 - tax_rate)

                # 成本价调减（使用完整分红金额，扣税仅影响实际到账）
                new_cost = new_cost - cash_dividend

                # 分红入账
                from .account import Account
                account = Account()
                account.add_proceeds(net_dividend)
                account.db.record_flow({
                    'change_type': 'dividend',
                    'amount': net_dividend,
                    'balance_after': account.cash,
                    'remark': f'{code}分红'
                })

            # 更新批次
            with self.db.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE holding_batches
                    SET quantity = ?, cost_price = ?
                    WHERE id = ?
                """, (new_qty, round(new_cost, 3), batch['id']))

        return True

    def clear_all(self) -> bool:
        """清空所有持仓"""
        return self.db.delete_all_holdings()

    def update_peak_prices(self, prices: Dict[str, float]) -> None:
        """批量更新持仓最高价（每日收盘后调用）

        Args:
            prices: 股票价格字典 {code: current_price}
        """
        self.db.update_all_peak_prices(prices)

    def get_positions_with_risk_info(self) -> List[Dict]:
        """获取带风控信息的持仓列表

        Returns:
            持仓列表，包含 current_price, peak_price, pnl_pct, drawdown_pct
        """
        holdings = self.get_holdings()
        if not holdings:
            return []

        # 获取当前价格
        prices = {}
        for h in holdings:
            code = h.get('code', '')
            lookup_code = code.replace('sh', '').replace('sz', '')
            stock = self.db.get_stock(lookup_code)
            if stock and stock.get('price', 0) > 0:
                prices[code] = stock.get('price', 0)

        result = []
        for h in holdings:
            code = h.get('code', '')
            current_price = prices.get(code, 0)
            cost_price = h.get('avg_cost_price', 0)
            peak_price = h.get('peak_price', current_price)

            info = {**h}
            info['current_price'] = current_price
            info['cost_price'] = cost_price
            info['peak_price'] = peak_price

            if cost_price > 0 and current_price > 0:
                info['pnl_pct'] = (current_price - cost_price) / cost_price
                info['drawdown_pct'] = (current_price - peak_price) / peak_price if peak_price > 0 else 0
            else:
                info['pnl_pct'] = 0
                info['drawdown_pct'] = 0

            result.append(info)

        return result

    def check_and_trigger_stops(self, current_prices: Dict[str, float]) -> List[Tuple[str, str, float]]:
        """检查所有持仓是否触发止损/止盈

        Args:
            current_prices: {code: current_price}

        Returns:
            List of (code, reason, price) 需要卖出的股票
            reason 是 'stop_loss' 或 'take_profit'
        """
        to_sell = []
        holdings = self.get_holdings()

        for position in holdings:
            code = position['code']
            stop_loss = position.get('stop_loss', 0)
            take_profit = position.get('take_profit', 0)

            if stop_loss <= 0 and take_profit <= 0:
                continue

            current_price = current_prices.get(code, 0)
            if current_price <= 0:
                continue

            # 检查止损
            if stop_loss > 0 and current_price <= stop_loss:
                to_sell.append((code, 'stop_loss', current_price))
                continue

            # 检查止盈
            if take_profit > 0 and current_price >= take_profit:
                to_sell.append((code, 'take_profit', current_price))
                continue

        return to_sell
