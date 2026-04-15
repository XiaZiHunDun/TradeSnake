"""
涨幅预测特征计算模块

计算用于涨幅预测的技术指标特征：
- 动量：gain_3d, gain_5d, gain_10d, gain_20d
- 波动率：volatility_20d, atr_14
- 趋势：ma_position
- 技术指标：rsi_14, macd, macd_signal
- 市场状态：board_type, limit_type

设计文档：docs/plans/engine/gain_predictor/GAIN_PREDICTOR.md
"""

from typing import Dict, List, Optional, Tuple
import numpy as np


# 全局均值填充（当数据不足时使用）
GLOBAL_AVG_VOLATILITY = 25.0  # 默认20日波动率


def calculate_features(klines: List[Dict]) -> Dict[str, float]:
    """计算单只股票的特征

    Args:
        klines: 日K线列表，按日期升序排列

    Returns:
        特征字典
    """
    if not klines or len(klines) < 2:
        return _empty_features()

    closes = [float(k.get('close', 0)) for k in klines]
    highs = [float(k.get('high', 0)) for k in klines]
    lows = [float(k.get('low', 0)) for k in klines]
    volumes = [float(k.get('volume', 0)) for k in klines]

    features = {}

    # ========== 动量特征 ==========
    features['gain_3d'] = _calc_gain(closes, 3)
    features['gain_5d'] = _calc_gain(closes, 5)
    features['gain_10d'] = _calc_gain(closes, 10)
    features['gain_20d'] = _calc_gain(closes, 20)

    # ========== 波动率特征 ==========
    features['volatility_20d'] = _calc_volatility(closes, 20)
    features['atr_14'] = _calc_atr(highs, lows, closes, 14)

    # ========== 趋势特征 ==========
    ma20 = _calc_ma(closes, 20)
    features['ma_position'] = closes[-1] / ma20 if ma20 > 0 else 1.0

    ma10 = _calc_ma(closes, 10)
    features['ma10_position'] = closes[-1] / ma10 if ma10 > 0 else 1.0

    # ========== 技术指标 ==========
    features['rsi_14'] = _calc_rsi(closes, 14)

    macd_result = _calc_macd(closes)
    features['macd'] = macd_result['macd']
    features['macd_signal'] = macd_result['signal']

    # MACD金叉死叉信号：1=金叉且柱状图为正，-1=死叉且柱状图为负，0=无信号
    features['macd_cross'] = macd_result['cross']

    # ========== 市场状态特征 ==========
    # 涨跌停状态
    today_change = klines[-1].get('change_pct', 0) if klines else 0
    features['limit_up'] = 1 if today_change >= 9.9 else 0
    features['limit_down'] = 1 if today_change <= -9.9 else 0

    # 成交量异常度（今日量/20日均量）
    avg_volume_20d = np.mean(volumes[-20:]) if len(volumes) >= 20 else volumes[-1] if volumes else 1
    features['volume_ratio'] = volumes[-1] / avg_volume_20d if avg_volume_20d > 0 else 1.0

    # ========== 缺失值处理 ==========
    # 短期特征缺失用可用数据
    if len(klines) < 20 and features.get('volatility_20d', 0) == 0:
        features['volatility_20d'] = GLOBAL_AVG_VOLATILITY

    if len(klines) < 10 and features.get('ma_position', 0) == 0:
        features['ma_position'] = 1.0

    return features


def _empty_features() -> Dict[str, float]:
    """返回空特征"""
    return {
        'gain_3d': 0.0,
        'gain_5d': 0.0,
        'gain_10d': 0.0,
        'gain_20d': 0.0,
        'volatility_20d': GLOBAL_AVG_VOLATILITY,
        'atr_14': 0.0,
        'ma_position': 1.0,
        'ma10_position': 1.0,
        'rsi_14': 50.0,
        'macd': 0.0,
        'macd_signal': 0.0,
        'macd_cross': 0.0,
        'limit_up': 0.0,
        'limit_down': 0.0,
        'volume_ratio': 1.0,
    }


def _calc_gain(closes: List[float], days: int) -> float:
    """计算N日收益率"""
    if len(closes) < days:
        return 0.0
    return (closes[-1] - closes[-days]) / closes[-days] * 100 if closes[-days] != 0 else 0.0


def _calc_volatility(closes: List[float], days: int) -> float:
    """计算N日年化波动率"""
    if len(closes) < days:
        return 0.0

    returns = []
    for i in range(days):
        if i > 0 and closes[-i] != 0:
            returns.append((closes[-i] - closes[-i-1]) / closes[-i-1])
        else:
            returns.append(0.0)

    if not returns:
        return 0.0

    std = np.std(returns)
    return std * np.sqrt(250) * 100  # 年化波动率（百分比）


def _calc_atr(highs: List[float], lows: List[float], closes: List[float], days: int) -> float:
    """计算ATR指标"""
    if len(highs) < days + 1:
        return 0.0

    trs = []
    for i in range(days):
        high = highs[-i-1]
        low = lows[-i-1]
        prev_close = closes[-i-2] if i > 0 else lows[-i-1]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    return np.mean(trs) if trs else 0.0


def _calc_ma(closes: List[float], days: int) -> float:
    """计算简单移动平均"""
    if len(closes) < days:
        return closes[-1] if closes else 0.0
    return np.mean(closes[-days:])


def _calc_rsi(closes: List[float], days: int = 14) -> float:
    """计算RSI指标"""
    if len(closes) < days + 1:
        return 50.0

    gains = []
    losses = []
    for i in range(days):
        change = closes[-i-1] - closes[-i-2] if i > 0 else 0
        if change > 0:
            gains.append(change)
        else:
            losses.append(abs(change))

    avg_gain = np.mean(gains) if gains else 0.0
    avg_loss = np.mean(losses) if losses else 0.0

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return max(0, min(100, rsi))


def _calc_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
    """计算MACD指标

    Returns:
        {
            'macd': DIF线,
            'signal': DEA线,
            'cross': 金叉死叉信号 (1=金叉, -1=死叉, 0=无)
        }
    """
    if len(closes) < slow + signal:
        return {'macd': 0.0, 'signal': 0.0, 'cross': 0.0}

    # 计算EMA
    ema_fast = _calc_ema(closes, fast)
    ema_slow = _calc_ema(closes, slow)

    dif = ema_fast - ema_slow

    # 计算DEA线（信号线）
    macd_histories = []
    for i in range(slow, len(closes)):
        e_f = _calc_ema(closes[:i+1], fast)
        e_s = _calc_ema(closes[:i+1], slow)
        macd_histories.append(e_f - e_s)

    if len(macd_histories) < signal:
        dea = dif * 0.9  # 简化处理
    else:
        dea = np.mean(macd_histories[-signal:])

    # MACD柱状图
    histogram = (dif - dea) * 2  # 通常显示为 DIF - DEA 的2倍

    # 判断金叉死叉
    # 金叉：DIF从下方穿越DEA，且柱状图为正
    # 死叉：DIF从上方穿越DEA，且柱状图为负
    cross = 0
    if len(macd_histories) >= 2:
        prev_dif = macd_histories[-2]
        prev_dea = np.mean(macd_histories[-signal:]) if len(macd_histories) >= signal + 1 else prev_dif

        # 金叉：DIF上穿DEA
        if dif > dea and prev_dif <= prev_dea and histogram > 0:
            cross = 1
        # 死叉：DIF下穿DEA
        elif dif < dea and prev_dif >= prev_dea and histogram < 0:
            cross = -1

    return {
        'macd': dif,
        'signal': dea,
        'cross': cross
    }


def _calc_ema(closes: List[float], days: int) -> float:
    """计算指数移动平均"""
    if not closes:
        return 0.0

    multiplier = 2 / (days + 1)
    ema = closes[0]

    for price in closes[1:]:
        ema = (price - ema) * multiplier + ema

    return ema


def calculate_batch_features(klines_dict: Dict[str, List[Dict]]) -> Dict[str, Dict[str, float]]:
    """批量计算多只股票的特征

    Args:
        klines_dict: {code: [klines]} 股票代码到K线数据的映射

    Returns:
        {code: features} 股票代码到特征字典的映射
    """
    return {code: calculate_features(klines)
            for code, klines in klines_dict.items()}
