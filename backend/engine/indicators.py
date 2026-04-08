"""
技术指标模块 v18.2+v19.6

提供股票技术指标计算（MA/MACD/RSI）
使用 pandas 实现，无需安装 ta-lib

参考专家评审建议：
- 引入趋势类指标（MA）辅助判断
- 引入动量类指标（MACD、RSI）验证战力信号
- v19.6: 新增分钟级均线计算（real_time_score用）
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple


class TechnicalIndicators:
    """
    技术指标计算器 v18.2

    支持指标：
    - MA: 移动平均线（5/10/20/60日）
    - MACD: 指数平滑异同移动平均线
    - RSI: 相对强弱指数
    """

    # MA周期配置
    MA_PERIODS = {
        'MA5': 5,
        'MA10': 10,
        'MA20': 20,
        'MA60': 60
    }

    # MACD参数
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9

    # RSI参数
    RSI_PERIOD = 14

    @classmethod
    def calculate_ma(cls, prices: List[float], period: int = 5) -> float:
        """
        计算移动平均线

        Args:
            prices: 价格序列（从旧到新）
            period: 周期

        Returns:
            MA值，如果数据不足返回 None
        """
        if len(prices) < period:
            return None

        return sum(prices[-period:]) / period

    @classmethod
    def calculate_all_ma(cls, prices: List[float]) -> Dict[str, float]:
        """
        计算所有常用MA

        Args:
            prices: 价格序列

        Returns:
            {'MA5': value, 'MA10': value, 'MA20': value, 'MA60': value}
        """
        result = {}
        for name, period in cls.MA_PERIODS.items():
            ma = cls.calculate_ma(prices, period)
            result[name] = round(ma, 2) if ma is not None else None
        return result

    @classmethod
    def calculate_macd(
        cls,
        prices: List[float],
        fast: int = None,
        slow: int = None,
        signal: int = None
    ) -> Dict[str, Optional[float]]:
        """
        计算MACD指标

        Args:
            prices: 价格序列（从旧到新）
            fast: 快线周期（默认12）
            slow: 慢线周期（默认26）
            signal: 信号线周期（默认9）

        Returns:
            {'macd': DIF, 'signal': DEA, 'histogram': MACD柱}
        """
        if fast is None:
            fast = cls.MACD_FAST
        if slow is None:
            slow = cls.MACD_SLOW
        if signal is None:
            signal = cls.MACD_SIGNAL

        if len(prices) < slow:
            return {'macd': None, 'signal': None, 'histogram': None}

        # 使用 pandas 计算 EMA
        df = pd.DataFrame({'price': prices})

        # 计算快速和慢速EMA
        ema_fast = df['price'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['price'].ewm(span=slow, adjust=False).mean()

        # DIF = EMA_fast - EMA_slow
        dif = ema_fast - ema_slow

        # DEA = Signal线（DIF的EMA）
        dea = dif.ewm(span=signal, adjust=False).mean()

        # MACD柱 = (DIF - DEA) * 2
        macd_hist = (dif - dea) * 2

        return {
            'macd': round(dif.iloc[-1], 4) if not dif.empty else None,
            'signal': round(dea.iloc[-1], 4) if not dea.empty else None,
            'histogram': round(macd_hist.iloc[-1], 4) if not macd_hist.empty else None
        }

    @classmethod
    def calculate_rsi(cls, prices: List[float], period: int = None) -> Optional[float]:
        """
        计算RSI相对强弱指数

        Args:
            prices: 价格序列（从旧到新）
            period: 周期（默认14）

        Returns:
            RSI值 (0-100)，数据不足返回 None
        """
        if period is None:
            period = cls.RSI_PERIOD

        if len(prices) < period + 1:
            return None

        # 计算价格变化
        deltas = pd.Series(prices).diff()

        # 分离上涨和下跌
        gains = deltas.clip(lower=0)
        losses = -deltas.clip(upper=0)

        # 计算平均涨跌（使用指数移动平均）
        avg_gain = gains.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = losses.ewm(alpha=1/period, adjust=False).mean()

        # 计算RS和RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return round(rsi.iloc[-1], 2)

    @classmethod
    def get_technical_signal(cls, prices: List[float]) -> Dict:
        """
        综合技术指标信号 v18.2

        Args:
            prices: 价格序列（从旧到新，需要至少60个数据点）

        Returns:
            技术分析信号和建议
        """
        result = {
            'ma': cls.calculate_all_ma(prices),
            'macd': cls.calculate_macd(prices),
            'rsi': cls.calculate_rsi(prices),
            'signal': 'neutral',
            'confidence': 0,
            'suggestion': ''
        }

        # 收集信号
        signals = []

        # MA信号
        ma = result['ma']
        if ma['MA5'] and ma['MA10'] and ma['MA20']:
            if ma['MA5'] > ma['MA10'] > ma['MA20']:
                signals.append(('MA多头排列', 0.7, 'short'))
            elif ma['MA5'] < ma['MA10'] < ma['MA20']:
                signals.append(('MA空头排列', -0.7, 'short'))
            elif ma['MA5'] > ma['MA20']:
                signals.append(('MA偏多', 0.3, 'long'))
            else:
                signals.append(('MA偏空', -0.3, 'short'))

        # MACD信号
        macd = result['macd']
        if macd['histogram'] is not None:
            if macd['histogram'] > 0 and macd['macd'] > macd['signal']:
                signals.append(('MACD金叉', 0.6, 'long'))
            elif macd['histogram'] < 0 and macd['macd'] < macd['signal']:
                signals.append(('MACD死叉', -0.6, 'short'))

        # RSI信号
        rsi = result['rsi']
        if rsi is not None:
            if rsi > 75:
                signals.append(('RSI超买', -0.5, 'short'))
            elif rsi < 25:
                signals.append(('RSI超卖', 0.5, 'long'))
            elif rsi > 60:
                signals.append(('RSI偏强', 0.3, 'long'))
            elif rsi < 40:
                signals.append(('RSI偏弱', -0.3, 'short'))

        # 综合判断
        if not signals:
            result['signal'] = 'neutral'
            result['confidence'] = 0
            result['suggestion'] = '技术指标信号不明朗，建议观望'
        else:
            # 加权计算信号强度
            total_weight = sum(abs(s[1]) for s in signals)
            weighted_signal = sum(s[1] for s in signals)

            if weighted_signal > 0.5 and total_weight > 1.0:
                result['signal'] = 'bullish'
                result['confidence'] = min(abs(weighted_signal) / total_weight * 100, 100)
                result['suggestion'] = '技术面偏多 ' + ' '.join(s[0] for s in signals if s[2] == 'long')
            elif weighted_signal < -0.5 and total_weight > 1.0:
                result['signal'] = 'bearish'
                result['confidence'] = min(abs(weighted_signal) / total_weight * 100, 100)
                result['suggestion'] = '技术面偏空 ' + ' '.join(s[0] for s in signals if s[2] == 'short')
            else:
                result['signal'] = 'neutral'
                result['confidence'] = min(total_weight * 30, 50)
                result['suggestion'] = '技术面中性 ' + '|'.join(s[0] for s in signals)

        return result

    @classmethod
    def calculate_trend_strength(cls, prices: List[float]) -> float:
        """
        计算趋势强度（基于MA角度）

        Args:
            prices: 价格序列

        Returns:
            趋势强度 (0-100)
        """
        if len(prices) < 20:
            return 50  # 数据不足返回中性

        # 计算MA20
        ma20_current = sum(prices[-20:]) / 20
        ma20_prev = sum(prices[-21:-1]) / 20

        if ma20_prev == 0:
            return 50

        # MA变化率作为趋势强度指标
        change_rate = (ma20_current - ma20_prev) / ma20_prev * 100

        # 将变化率转换为0-100
        # ±2%变化率对应50，±10%对应100或0
        if change_rate >= 5:
            strength = min(50 + (change_rate - 5) * 10, 100)
        elif change_rate <= -5:
            strength = max(50 + (change_rate + 5) * 10, 0)
        else:
            strength = 50

        return round(strength, 1)

    @classmethod
    def calculate_volatility(cls, prices: List[float], period: int = 20) -> float:
        """
        计算历史波动率（年化）

        Args:
            prices: 价格序列（从旧到新）
            period: 计算周期，默认20日

        Returns:
            年化波动率 (%)
        """
        if len(prices) < period:
            return 0.0

        # 计算日收益率
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] != 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)

        if len(returns) < 2:
            return 0.0

        # 计算标准差
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5

        # 年化波动率（日波动率 × sqrt(252)）
        annual_volatility = std_dev * (252 ** 0.5) * 100

        return round(annual_volatility, 2)

    @classmethod
    def calculate_daily_volatility(cls, prices: List[float], period: int = 20) -> float:
        """
        计算日波动率 v18.4

        Args:
            prices: 价格序列（从旧到新）
            period: 计算周期，默认20日

        Returns:
            日波动率 (%)
        """
        if len(prices) < period:
            return 0.0

        # 计算日收益率
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] != 0:
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)

        if len(returns) < 2:
            return 0.0

        # 计算标准差作为日波动率
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        daily_volatility = (variance ** 0.5) * 100

        return round(daily_volatility, 2)

    @classmethod
    def calculate_turnover_rate(cls, volume: float, circulating_shares: float) -> float:
        """
        计算换手率 v18.4

        Args:
            volume: 当日成交量（股数）
            circulating_shares: 流通股本（股数）

        Returns:
            换手率 (小数，如 0.05 表示 5%)
        """
        if circulating_shares <= 0:
            return 0.0

        turnover = volume / circulating_shares
        return round(turnover, 4)

    @classmethod
    def calculate_avg_daily_amount(cls, amounts: List[float], period: int = 20) -> float:
        """
        计算日均成交额 v18.4

        Args:
            amounts: 成交额序列（从旧到新）
            period: 计算周期，默认20日

        Returns:
            日均成交额 (元)
        """
        if not amounts:
            return 0.0

        recent = amounts[-period:] if len(amounts) >= period else amounts
        return sum(recent) / len(recent) if recent else 0.0

    # ==================== 分钟级指标（v19.6） ====================

    @classmethod
    def calculate_minute_ma(cls, prices: List[float], period: int = 5) -> Optional[float]:
        """
        计算分钟级移动平均线 v19.6

        Args:
            prices: 价格序列（从旧到新，分钟K线数据）
            period: 周期，默认5分钟

        Returns:
            均线值，如果数据不足返回 None
        """
        if len(prices) < period:
            return None

        return sum(prices[-period:]) / period

    @classmethod
    def calculate_minute_ma_change(
        cls,
        current_ma: float,
        open_ma: float
    ) -> float:
        """
        计算分钟均线变化率 v19.6

        Args:
            current_ma: 当前均线值
            open_ma: 开盘时均线值

        Returns:
            变化率 (%)
        """
        if open_ma == 0 or open_ma is None:
            return 0.0

        return (current_ma - open_ma) / open_ma * 100

    @classmethod
    def calculate_volume_ratio(
        cls,
        current_volume: float,
        avg_volume_5: float
    ) -> float:
        """
        计算成交量比率 v19.6

        Args:
            current_volume: 当前成交量
            avg_volume_5: 5分钟平均成交量

        Returns:
            成交量比率
        """
        if avg_volume_5 == 0 or avg_volume_5 is None:
            return 1.0

        return current_volume / avg_volume_5


def add_technical_indicators(stock_data: Dict, price_history: List[float] = None) -> Dict:
    """
    为股票数据添加技术指标 v18.2

    Args:
        stock_data: 股票数据字典（包含 price, prices 列表等）
        price_history: 价格历史（可选）

    Returns:
        添加技术指标后的股票数据
    """
    if price_history is None:
        # 尝试从 stock_data 获取
        price_history = stock_data.get('price_history', [])

    if len(price_history) < 20:
        # 数据不足，添加默认值
        stock_data['technical'] = {
            'ma': {'MA5': None, 'MA10': None, 'MA20': None, 'MA60': None},
            'macd': {'macd': None, 'signal': None, 'histogram': None},
            'rsi': None,
            'signal': 'insufficient_data',
            'suggestion': '价格历史不足，无法计算技术指标',
            # v18.4 新增
            'volatility_20d': 0.0,
            'daily_volatility': 0.0,
        }
        return stock_data

    # 计算技术指标
    stock_data['technical'] = TechnicalIndicators.get_technical_signal(price_history)

    # v18.4 新增波动率指标
    stock_data['technical']['volatility_20d'] = TechnicalIndicators.calculate_daily_volatility(price_history, 20)
    stock_data['technical']['daily_volatility'] = TechnicalIndicators.calculate_daily_volatility(price_history, 20)

    return stock_data
