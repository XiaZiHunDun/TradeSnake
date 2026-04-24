"""交易成本模型 v1.0"""

from dataclasses import dataclass


@dataclass
class CostResult:
    commission: float      # 佣金
    stamp_tax: float       # 印花税（仅卖出）
    transfer_fee: float    # 过户费（沪市双向）
    slippage: float        # 滑点
    total_cost: float      # 总成本

    def total(self) -> float:
        return self.total_cost


# 费率配置
COMMISSION_RATE = 0.0001       # 万1
MIN_COMMISSION = 5.0           # 最低佣金5元
STAMP_TAX_RATE = 0.0005        # 千0.5（卖出时）
TRANSFER_FEE_RATE = 0.00001    # 千0.01（沪市双向，深市免）
SLIPPAGE_RATE = 0.001          # 0.1%


class CostModel:
    """交易成本计算模型"""

    def __init__(
        self,
        commission_rate: float = COMMISSION_RATE,
        min_commission: float = MIN_COMMISSION,
        stamp_tax_rate: float = STAMP_TAX_RATE,
        transfer_fee_rate: float = TRANSFER_FEE_RATE,
        slippage_rate: float = SLIPPAGE_RATE,
    ):
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.stamp_tax_rate = stamp_tax_rate
        self.transfer_fee_rate = transfer_fee_rate
        self.slippage_rate = slippage_rate

    def calculate(self, amount: float, action: str, is_shanghai: bool = True) -> CostResult:
        """计算交易成本

        Args:
            amount: 成交金额
            action: 'buy' 或 'sell'
            is_shanghai: 是否沪市（影响过户费）

        Returns:
            CostResult: 各成本明细
        """
        # 佣金（双向）
        commission = max(amount * self.commission_rate, self.min_commission)

        # 印花税（仅卖出）
        stamp_tax = amount * self.stamp_tax_rate if action == 'sell' else 0.0

        # 过户费（沪市双向，深市免）
        transfer_fee = amount * self.transfer_fee_rate if is_shanghai else 0.0

        # 滑点（双向，金额比例）
        slippage = amount * self.slippage_rate

        total = commission + stamp_tax + transfer_fee + slippage

        return CostResult(
            commission=round(commission, 2),
            stamp_tax=round(stamp_tax, 2),
            transfer_fee=round(transfer_fee, 2),
            slippage=round(slippage, 2),
            total_cost=round(total, 2)
        )


def calculate_total_cost(amount: float, action: str, is_shanghai: bool = True) -> CostResult:
    """计算交易成本（便捷函数）

    Args:
        amount: 成交金额
        action: 'buy' 或 'sell'
        is_shanghai: 是否沪市（影响过户费）

    Returns:
        CostResult: 各成本明细

    Raises:
        ValueError: action 不是 'buy' 或 'sell'
    """
    if action not in ('buy', 'sell'):
        raise ValueError(f"Invalid action: {action}. Must be 'buy' or 'sell'.")
    model = CostModel()
    return model.calculate(amount, action, is_shanghai)


def apply_cost_to_capital(capital: float, amount: float, action: str, is_shanghai: bool = True) -> float:
    """计算扣成本后的资金变化

    Args:
        capital: 当前资金
        amount: 成交金额
        action: 'buy' 或 'sell'

    Returns:
        扣成本后的资金
    """
    cost = calculate_total_cost(amount, action, is_shanghai)
    if action == 'buy':
        return capital - amount - cost.total_cost
    else:  # sell
        return capital + amount - cost.total_cost