"""每日交易信号生成器"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class SignalLevel(Enum):
    """信号档位"""
    STRONG_BUY = ("strong_buy", "🟢")
    WATCH = ("watch", "🟡")
    EMPTY = ("empty", "🔴")

@dataclass
class DailySignal:
    """每日信号"""
    level: str
    emoji: str
    kelly_position: float
    risk_level: str
    predicted_gain_5d: float
    up_probability_5d: float
    is_mature: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            'level': self.level,
            'emoji': self.emoji,
            'kelly_position': round(self.kelly_position, 2),
            'risk_level': self.risk_level,
            'predicted_gain_5d': round(self.predicted_gain_5d, 2),
            'up_probability_5d': round(self.up_probability_5d, 3),
            'is_mature': self.is_mature,
            'reason': self.reason
        }


class DailySignalGenerator:
    """每日信号生成器

    规则：
    毕业前：只允许执行"强烈买入"档位
    毕业后：可执行所有档位（强烈买入/观望/空仓）
    """

    STRONG_BUY_KELLY_MIN = 8.0
    STRONG_BUY_PROB_MIN = 0.6
    STRONG_BUY_GAIN_MIN = 5.0

    def generate(
        self,
        kelly_position: float,
        risk_level: str,
        predicted_gain_5d: float,
        up_probability_5d: float,
        is_mature: bool
    ) -> DailySignal:
        """生成每日交易信号"""
        is_strong_buy = (
            kelly_position > self.STRONG_BUY_KELLY_MIN and
            risk_level == 'acceptable' and
            up_probability_5d > self.STRONG_BUY_PROB_MIN and
            predicted_gain_5d > self.STRONG_BUY_GAIN_MIN
        )

        is_empty = (
            risk_level == 'high' or
            up_probability_5d < 0.5 or
            predicted_gain_5d < 0
        )

        if not is_mature:
            if is_strong_buy:
                return DailySignal(
                    level='strong_buy',
                    emoji='🟢',
                    kelly_position=kelly_position,
                    risk_level=risk_level,
                    predicted_gain_5d=predicted_gain_5d,
                    up_probability_5d=up_probability_5d,
                    is_mature=is_mature,
                    reason='毕业前只允许强烈买入交易'
                )
            else:
                return DailySignal(
                    level='empty',
                    emoji='🔴',
                    kelly_position=kelly_position,
                    risk_level=risk_level,
                    predicted_gain_5d=predicted_gain_5d,
                    up_probability_5d=up_probability_5d,
                    is_mature=is_mature,
                    reason='策略未达毕业标准，禁止非强烈买入交易'
                )

        if is_strong_buy:
            return DailySignal(
                level='strong_buy',
                emoji='🟢',
                kelly_position=kelly_position,
                risk_level=risk_level,
                predicted_gain_5d=predicted_gain_5d,
                up_probability_5d=up_probability_5d,
                is_mature=is_mature,
                reason='强烈买入信号'
            )
        elif is_empty:
            return DailySignal(
                level='empty',
                emoji='🔴',
                kelly_position=kelly_position,
                risk_level=risk_level,
                predicted_gain_5d=predicted_gain_5d,
                up_probability_5d=up_probability_5d,
                is_mature=is_mature,
                reason='高风险或预测下跌，禁止交易'
            )
        else:
            return DailySignal(
                level='watch',
                emoji='🟡',
                kelly_position=kelly_position,
                risk_level=risk_level,
                predicted_gain_5d=predicted_gain_5d,
                up_probability_5d=up_probability_5d,
                is_mature=is_mature,
                reason='中等机会，等待更明确信号'
            )