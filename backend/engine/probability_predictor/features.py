"""
上涨概率预测特征计算模块

计算用于上涨概率预测的技术指标特征：
- 动量：gain_3d, gain_5d, gain_10d, gain_20d
- 波动率：volatility_20d, atr_14
- 趋势：ma_position
- 技术指标：rsi_14, kdj_k, kdj_d, kdj_j
- 市场状态：limit_up, limit_down (涨跌停标记)

设计文档：docs/plans/engine/probability_predictor/PROBABILITY_PREDICTOR.md
"""

from typing import Dict, List
import numpy as np


# 全局均值填充
GLOBAL_AVG_VOLATILITY = 25.0


def calculate_features(klines: List[Dict]) -> Dict[str, float]:
    """计算单只股票的概率预测特征

    Args:
        klines: 日K线列表，按日期升序排列

    Returns:
        特征字典
    """
    if not klines or len(klines) < 2:
        return _empty_features()

    # 确保按日期升序排列（DuckDB返回DESC降序，需排序处理）
    klines = sorted(klines, key=lambda x: x.get('trade_date', ''))

    # v19.9.11: 使用复权价格计算技术指标，避免除权除息造成的缺口
    adj_closes = []
    for k in klines:
        close = float(k.get('close', 0))
        adj_factor = float(k.get('adj_factor', 1.0))
        adj_close = float(k.get('adj_close', 0))
        if adj_factor > 1 and adj_close == 0:
            adj_close = close * adj_factor
        elif adj_close > 0:
            pass
        else:
            adj_close = close
        adj_closes.append(adj_close)

    closes = adj_closes  # 技术指标使用复权价格
    highs = [k.get('high', 0) for k in klines]
    lows = [k.get('low', 0) for k in klines]
    volumes = [k.get('volume', 0) for k in klines]

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

    # ========== 技术指标 ==========
    features['rsi_14'] = _calc_rsi(closes, 14)

    kdj = _calc_kdj(highs, lows, closes, 9, 3, 3)
    features['kdj_k'] = kdj['k']
    features['kdj_d'] = kdj['d']
    features['kdj_j'] = kdj['j']
    features['kdj_cross'] = kdj['cross']  # 金叉死叉信号

    # ========== 市场状态特征 ==========
    today_change = klines[-1].get('change_pct', 0) if klines else 0
    features['limit_up'] = 1 if today_change >= 9.9 else 0
    features['limit_down'] = 1 if today_change <= -9.9 else 0

    # ========== 缺失值处理 ==========
    if len(klines) < 20 and features.get('volatility_20d', 0) == 0:
        features['volatility_20d'] = GLOBAL_AVG_VOLATILITY

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
        'rsi_14': 50.0,
        'kdj_k': 50.0,
        'kdj_d': 50.0,
        'kdj_j': 50.0,
        'kdj_cross': 0.0,
        'limit_up': 0.0,
        'limit_down': 0.0,
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
    for i in range(1, days):
        if closes[-i-1] != 0:
            returns.append((closes[-i] - closes[-i-1]) / closes[-i-1])
        else:
            returns.append(0.0)

    if not returns:
        return 0.0

    std = np.std(returns)
    return std * np.sqrt(250) * 100


def _calc_atr(highs: List[float], lows: List[float], closes: List[float], days: int) -> float:
    """计算ATR指标"""
    if len(highs) < days + 2:
        return 0.0

    trs = []
    for i in range(days):
        high = highs[-i-1]
        low = lows[-i-1]
        prev_close = closes[-i-2] if i > 0 else closes[-2]
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
    for i in range(1, days):
        change = closes[-i-1] - closes[-i-2]
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


def _calc_kdj(highs: List[float], lows: List[float], closes: List[float],
              n: int = 9, m1: int = 3, m2: int = 3) -> Dict[str, float]:
    """计算KDJ指标

    Args:
        highs: 最高价列表
        lows: 最低价列表
        closes: 收盘价列表
        n: RSV周期（默认9）
        m1: K平滑因子（默认3）
        m2: D平滑因子（默认3）

    Returns:
        {
            'k': K值,
            'd': D值,
            'j': J值,
            'cross': 金叉死叉信号 (1=金叉, -1=死叉, 0=无)
        }
    """
    if len(closes) < n:
        return {'k': 50.0, 'd': 50.0, 'j': 50.0, 'cross': 0.0}

    # 计算RSV
    rsv_values = []
    for i in range(n - 1, len(closes)):
        high_n = max(highs[i-n+1:i+1])
        low_n = min(lows[i-n+1:i+1])
        close = closes[i]

        if high_n != low_n:
            rsv = (close - low_n) / (high_n - low_n) * 100
        else:
            rsv = 50.0
        rsv_values.append(rsv)

    if not rsv_values:
        return {'k': 50.0, 'd': 50.0, 'j': 50.0, 'cross': 0.0}

    # 计算K、D、J值（平滑方式）
    k_prev = 50.0
    d_prev = 50.0

    for rsv in rsv_values[:-1]:
        k = (2/3) * k_prev + (1/3) * rsv
        d = (2/3) * d_prev + (1/3) * k
        k_prev = k
        d_prev = d

    k = (2/3) * k_prev + (1/3) * rsv_values[-1]
    d = (2/3) * d_prev + (1/3) * k
    j = 3 * k - 2 * d

    # 判断金叉死叉
    # 需要至少两个K、D值来判断交叉
    if len(rsv_values) >= 2:
        k_values = []
        d_values = []
        kp, dp = 50.0, 50.0
        for rsv in rsv_values[:-1]:
            kp = (2/3) * kp + (1/3) * rsv
            dp = (2/3) * dp + (1/3) * kp
            k_values.append(kp)
            d_values.append(dp)

        prev_k = k_values[-2] if len(k_values) >= 2 else k_values[-1]
        prev_d = d_values[-2] if len(d_values) >= 2 else d_values[-1]

        # 金叉：K从下穿越D
        if k > d and prev_k <= prev_d and j > 0:
            cross = 1
        # 死叉：K从上穿越D
        elif k < d and prev_k >= prev_d:
            cross = -1
        else:
            cross = 0
    else:
        cross = 0

    return {
        'k': max(0, min(100, k)),
        'd': max(0, min(100, d)),
        'j': max(0, min(100, j)),
        'cross': cross
    }


def calculate_batch_features(klines_dict: Dict[str, List[Dict]]) -> Dict[str, Dict[str, float]]:
    """批量计算多只股票的特征

    Args:
        klines_dict: {code: [klines]} 股票代码到K线数据的映射

    Returns:
        {code: features} 股票代码到特征字典的映射
    """
    return {code: calculate_features(klines)
            for code, klines in klines_dict.items()}
