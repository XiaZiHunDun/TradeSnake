"""风控机制 v1.0"""

from dataclasses import dataclass, field
from typing import List

@dataclass
class RiskConfig:
    """风控配置"""
    stop_loss: float = -0.10           # 个股止损 -10%
    max_daily_loss: float = -0.03      # 单日最大亏损 -3%
    consecutive_loss_days: int = 3      # 连续亏损天数阈值
    market_filter_down: float = -0.02  # 大盘跌幅超过此值减半持仓
    market_filter_exit: float = -0.04  # 大盘跌幅超过此值空仓
    single_position_limit: float = 0.15 # 单只仓位上限 15%
    observation_days: int = 2          # 空仓观望天数


class RiskController:
    """风控控制器 v1.0"""

    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()
        self.consecutive_loss_count = 0
        self.daily_returns: List[float] = []
        self.total_loss = 0.0
        self.protection_active = False
        self.protection_remaining_days = 0

    def is_normal(self) -> bool:
        return not self.protection_active

    def should_protect(self) -> bool:
        return self.consecutive_loss_count >= self.config.consecutive_loss_days

    def check_market_filter(self, market_change_pct: float) -> str:
        """检查大盘过滤

        Args:
            market_change_pct: 大盘当日涨跌幅%

        Returns:
            'normal' / 'reduce' / 'exit'
        """
        if market_change_pct <= self.config.market_filter_exit:
            return 'exit'
        elif market_change_pct <= self.config.market_filter_down:
            return 'reduce'
        return 'normal'

    def record_daily_return(self, daily_return: float):
        """记录每日收益，用于连续亏损检测"""
        self.daily_returns.append(daily_return)
        if daily_return < 0:
            self.consecutive_loss_count += 1
        else:
            self.consecutive_loss_count = 0

    def record_trade_result(self, profit_pct: float):
        """记录交易结果"""
        if profit_pct < 0:
            self.total_loss += abs(profit_pct)

    def activate_protection(self):
        """激活保护机制"""
        self.protection_active = True
        self.protection_remaining_days = self.config.observation_days

    def tick_protection(self):
        """保护期倒计时"""
        if self.protection_remaining_days > 0:
            self.protection_remaining_days -= 1
        if self.protection_remaining_days <= 0:
            self.protection_active = False
            self.consecutive_loss_count = 0

    def should_stop_loss(self, position_return: float) -> bool:
        """检查是否应止损"""
        return position_return <= self.config.stop_loss

    def get_position_limit(self, market_action: str) -> float:
        """获取仓位限制

        Args:
            market_action: 'normal' / 'reduce' / 'exit'

        Returns:
            仓位比例 (0.0 ~ 1.0)
        """
        if market_action == 'exit':
            return 0.0
        elif market_action == 'reduce':
            return 0.5
        return 1.0

    def reset(self):
        """重置风控状态（新回测周期）"""
        self.consecutive_loss_count = 0
        self.daily_returns = []
        self.total_loss = 0.0
        self.protection_active = False
        self.protection_remaining_days = 0