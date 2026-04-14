"""
换股计算器 - Swap Calculator
"""

from typing import List, Dict, Tuple
from backend.engine import TradeDecision, TRADE_COST


class SwapCalculator:
    """换股计算器"""

    @staticmethod
    def calculate_swap_benefit(
        from_cp: float,
        to_cp: float,
        principal: float = 100000,
        holding_days: int = 30
    ) -> Dict:
        """计算换股收益"""
        decision = TradeDecision.should_swap(from_cp, to_cp, principal, holding_days)

        return {
            'cp_diff': round(decision['cp_diff'], 1),
            'expected_return': round(decision['expected_return'] * 100, 2),
            'gross_profit': round(decision['gross_profit'], 2),
            'trade_cost': round(decision['trade_cost'], 2),
            'net_profit': round(decision['net_profit'], 2),
            'net_return': round(decision['net_return'] * 100, 2),
            'action': decision['action'],
            'action_level': decision['action_level'],
            'action_label': decision['action_label'],
            'cost_breakdown': decision['cost_breakdown']
        }

    @staticmethod
    def calculate_trade_cost(principal: float, is_sell: bool = True) -> Dict:
        """计算交易成本"""
        commission = max(principal * TRADE_COST['commission'], TRADE_COST['min_commission'])
        stamp_tax = principal * TRADE_COST['stamp_tax'] if is_sell else 0
        transfer_fee = principal * TRADE_COST['transfer_fee']

        total = commission + stamp_tax + transfer_fee

        return {
            'principal': principal,
            'commission': round(commission, 2),
            'stamp_tax': round(stamp_tax, 2),
            'transfer_fee': round(transfer_fee, 2),
            'total_cost': round(total, 2),
            'cost_rate': round(total / principal * 100, 3) if principal > 0 else 0
        }

    @staticmethod
    def find_best_swap(
        current_code: str,
        current_cp: float,
        candidate_stocks: List,
        principal: float = 100000,
        holding_days: int = 30
    ) -> Tuple[Dict, List[Dict]]:
        """找到最佳换股目标"""
        candidates = []

        for stock in candidate_stocks:
            if stock.code == current_code:
                continue
            if stock.total_cp <= current_cp:
                continue

            benefit = SwapCalculator.calculate_swap_benefit(
                current_cp, stock.total_cp, principal, holding_days
            )

            candidates.append({
                'code': stock.code,
                'name': stock.name,
                'cp': round(stock.total_cp, 1),
                **benefit
            })

        candidates.sort(key=lambda x: x['net_profit'], reverse=True)

        best = candidates[0] if candidates else None
        return best, candidates[:5]

    @staticmethod
    def calculate_breakeven_days(
        trade_cost: float,
        target_stock,
        swap_amount: float = 100000
    ) -> int:
        """计算回本天数 v18.4

        公式：交易总成本 / (目标股预期日均收益 × 换股资金)

        Args:
            trade_cost: 交易成本
            target_stock: 目标股票（StockCP）
            swap_amount: 换股资金

        Returns:
            回本天数，超过30天返回999
        """
        # 预期日均收益：使用股票的change_pct作为日均收益估计
        # 如果没有历史数据，使用0.3%（A股平均日收益率）
        daily_return = abs(target_stock.change_pct / 100) if target_stock.change_pct != 0 else 0.003

        daily_profit = swap_amount * daily_return

        if daily_profit <= 0:
            return 999

        breakeven = int(trade_cost / daily_profit)

        # 超过30天降级为hold
        if breakeven > 30:
            return 999

        return breakeven
