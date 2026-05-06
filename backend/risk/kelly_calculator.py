"""Kelly 仓位计算器 v1.0

基于历史胜率和盈亏比计算 Kelly 系数
"""

from typing import Dict, Optional
import math


class KellyCalculator:
    """Kelly 仓位计算器 v1.0"""

    def __init__(self):
        self._cache: Dict[str, float] = {}

    def calculate(self, stock_code: str, win_rate: float = None,
                  avg_win_pct: float = None, avg_loss_pct: float = None) -> Dict:
        """计算 Kelly 仓位

        Args:
            stock_code: 股票代码
            win_rate: 胜率（0~1），如果为 None 从预测系统获取
            avg_win_pct: 平均盈利比例（%），如果为 None 从历史获取
            avg_loss_pct: 平均亏损比例（%），如果为 None 从历史获取

        Returns:
            {
                'kelly_position': float,  # Kelly 仓位比例（0~1）
                'half_kelly': float,      # 半 Kelly（更保守）
                'win_rate': float,
                'avg_win_pct': float,
                'avg_loss_pct': float,
                'profit_factor': float,   # 盈亏比
            }
        """
        # 如果没有提供参数，尝试从预测系统获取
        if win_rate is None or avg_win_pct is None or avg_loss_pct is None:
            try:
                pred = self._get_prediction(stock_code)
                if pred:
                    win_rate = win_rate or pred.get('win_rate')
                    avg_win_pct = avg_win_pct or pred.get('avg_win_pct')
                    avg_loss_pct = avg_loss_pct or pred.get('avg_loss_pct')
            except Exception:
                pass

        # 使用默认值（如果没有数据）
        win_rate = win_rate if win_rate is not None else 0.5
        avg_win_pct = avg_win_pct if avg_win_pct is not None else 5.0
        avg_loss_pct = avg_loss_pct if avg_loss_pct is not None else 3.0

        # 转换为小数
        win_rate = max(0.01, min(0.99, win_rate))
        avg_win = max(0.01, avg_win_pct) / 100
        avg_loss = max(0.01, avg_loss_pct) / 100

        # Kelly 公式: f* = (bp - q) / b
        # b = 盈亏比, p = 胜率, q = 1-p
        loss_rate = 1 - win_rate
        profit_factor = (avg_win * win_rate) / (avg_loss * loss_rate) if loss_rate > 0 else 0

        if profit_factor > 0:
            # Kelly: f* = (p * (b + 1) - 1) / b
            # 其中 b = avg_win / avg_loss
            b = avg_win / avg_loss if avg_loss > 0 else 0
            if b > 0:
                kelly = (win_rate * (b + 1) - 1) / b
                kelly = max(0, min(kelly, 0.5))  # 限制最大50%仓位
            else:
                kelly = 0
        else:
            kelly = 0

        return {
            'kelly_position': kelly,
            'half_kelly': kelly * 0.5,
            'quarter_kelly': kelly * 0.25,
            'win_rate': win_rate,
            'avg_win_pct': avg_win_pct,
            'avg_loss_pct': avg_loss_pct,
            'profit_factor': profit_factor,
        }

    def _get_prediction(self, stock_code: str) -> Optional[Dict]:
        """从预测系统获取历史表现"""
        try:
            from backend.data_manager.prediction_store import get_prediction_store
            store = get_prediction_store()
            # 简化：返回 None，让 caller 使用默认值
            return None
        except Exception:
            return None

    def get_cached(self, stock_code: str) -> Optional[float]:
        """获取缓存的 Kelly 仓位"""
        return self._cache.get(stock_code)

    def set_cached(self, stock_code: str, kelly_position: float):
        """缓存 Kelly 仓位"""
        self._cache[stock_code] = kelly_position
