"""
仓位计算器

基于Kelly公式计算建议仓位：
- f* = p - (1-p)/b
- f* = 最佳仓位比例
- p = 胜率
- b = 赔率（盈亏比）

设计文档: docs/plans/RECOMMENDER_ARCHITECTURE.md v18.4
"""

from typing import Dict


class PositionCalculator:
    """
    Kelly仓位计算器

    使用半Kelly（KELLY_FRACTION=0.5）作为安全系数
    单只股票最大仓位20%
    """

    # 安全系数（半Kelly）
    KELLY_FRACTION = 0.5

    # 最大仓位比例（%）
    MAX_POSITION_PCT = 20.0

    # 最小仓位信号阈值
    SIGNAL_THRESHOLDS = {
        "strong_buy": 0.3,   # kelly > 0.3 -> 强烈买入
        "buy": 0.1,          # kelly > 0.1 -> 买入
        "hold": 0.0,         # kelly > 0 -> 持有
        "avoid": None,       # kelly <= 0 -> 回避
    }

    @classmethod
    def calculate_position(
        cls,
        win_rate: float,
        win_loss_ratio: float,
        principal: float,
        max_position_pct: float = None
    ) -> Dict:
        """
        计算建议仓位

        Args:
            win_rate: 胜率（0-1）
            win_loss_ratio: 盈亏比（盈利金额/亏损金额）
            principal: 本金（元）
            max_position_pct: 最大仓位比例（%），None则使用默认值

        Returns:
            {
                'kelly_raw': float,      # 原始Kelly值
                'kelly_safe': float,      # 安全Kelly值（半Kelly）
                'position_pct': float,    # 建议仓位比例（%）
                'position_amount': float, # 建议仓位金额（元）
                'shares': int,            # 建议买入股数（100的倍数）
                'signal': str,            # 信号强度
            }
        """
        if max_position_pct is None:
            max_position_pct = cls.MAX_POSITION_PCT

        # Kelly公式: f* = p - (1-p)/b
        if win_loss_ratio <= 0:
            kelly_raw = 0
        else:
            kelly_raw = win_rate - (1 - win_rate) / win_loss_ratio

        # 安全Kelly（半Kelly）
        kelly_safe = kelly_raw * cls.KELLY_FRACTION

        # 限制最大仓位
        position_pct = min(kelly_safe, max_position_pct / 100)

        # 确保非负
        position_pct = max(0, position_pct)

        # 计算金额
        position_amount = principal * position_pct

        # 调整为100的倍数（1手=100股，假设价格为10元则1手=1000元）
        # 这里简化处理，实际应根据价格计算
        shares = round(position_amount / 100) * 100

        # 信号强度
        signal = cls._get_signal(kelly_raw)

        return {
            "kelly_raw": kelly_raw,
            "kelly_safe": kelly_safe,
            "position_pct": position_pct * 100,
            "position_amount": position_amount,
            "shares": shares,
            "signal": signal,
        }

    @classmethod
    def _get_signal(cls, kelly: float) -> str:
        """根据Kelly值获取信号"""
        if kelly > cls.SIGNAL_THRESHOLDS["strong_buy"]:
            return "strong_buy"
        elif kelly > cls.SIGNAL_THRESHOLDS["buy"]:
            return "buy"
        elif kelly > cls.SIGNAL_THRESHOLDS["hold"]:
            return "hold"
        else:
            return "avoid"

    @classmethod
    def calculate_from_history(
        cls,
        trades: list,
        principal: float,
        max_position_pct: float = None
    ) -> Dict:
        """
        从历史交易记录计算仓位

        Args:
            trades: 历史交易列表 [{
                profit: float,  # 盈利金额
                loss: float,   # 亏损金额
            }] 或 [
                (profit, loss), ...
            ]
            principal: 本金

        Returns:
            仓位建议
        """
        if not trades:
            return cls.calculate_position(0, 0, principal, max_position_pct)

        # 计算胜率
        wins = sum(1 for t in trades if cls._get_profit(t) > 0)
        win_rate = wins / len(trades)

        # 计算盈亏比
        total_profit = sum(cls._get_profit(t) for t in trades if cls._get_profit(t) > 0)
        total_loss = abs(sum(cls._get_profit(t) for t in trades if cls._get_profit(t) < 0))

        wins_count = sum(1 for t in trades if cls._get_profit(t) > 0)
        losses_count = len(trades) - wins_count

        avg_win = total_profit / wins_count if wins_count > 0 else 0
        avg_loss = total_loss / losses_count if losses_count > 0 else 1

        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

        return cls.calculate_position(win_rate, win_loss_ratio, principal, max_position_pct)

    @classmethod
    def _get_profit(cls, trade) -> float:
        """从交易记录获取盈利金额"""
        if isinstance(trade, dict):
            return trade.get("profit", 0) - abs(trade.get("loss", 0))
        elif isinstance(trade, (list, tuple)) and len(trade) >= 2:
            return trade[0] - abs(trade[1])
        else:
            return 0

    @classmethod
    def get_signal_description(cls, signal: str) -> str:
        """获取信号描述"""
        descriptions = {
            "strong_buy": "强烈买入（Kelly > 30%，高胜率高盈亏比）",
            "buy": "买入（Kelly > 10%，正期望）",
            "hold": "持有（Kelly > 0，低期望）",
            "avoid": "回避（Kelly <= 0，负期望）",
        }
        return descriptions.get(signal, "未知信号")
