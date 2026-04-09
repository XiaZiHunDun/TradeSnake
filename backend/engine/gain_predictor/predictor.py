"""
涨幅预测器模块

基于技术指标的规则模型预测股票未来N日涨幅：
- 每日收盘后执行一次
- 预测结果存储到 prediction_store（90天）

设计文档：docs/plans/engine/gain_predictor/GAIN_PREDICTOR.md
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from .features import calculate_features, GLOBAL_AVG_VOLATILITY


# 板块涨跌幅限制配置
BOARD_LIMIT_CONFIG = {
    'main': 10,      # 主板
    'chinext': 20,   # 创业板
    'star': 20,      # 科创板
    'bj': 30,        # 北交所
}


@dataclass
class GainPrediction:
    """单只股票涨幅预测"""
    code: str
    name: str
    predicted_gain_3d: float  # 预测3日涨幅%
    predicted_gain_5d: float  # 预测5日涨幅%
    confidence: float  # 置信度 0-1
    confidence_interval_3d: Tuple[float, float]  # 3日置信区间
    confidence_interval_5d: Tuple[float, float]  # 5日置信区间
    features: Dict[str, float]  # 主要特征值
    model_version: str = "rule_v19.8"


@dataclass
class GainPredictionResult:
    """批量涨幅预测结果"""
    predictions: List[GainPrediction]
    calculated_at: str
    data_timestamp: str
    stock_count: int
    distribution: Dict[str, float]  # 预测分布统计
    avg_confidence: float


class GainPredictor:
    """涨幅预测器"""

    def __init__(self):
        self.model_version = "rule_v19.8"

    def predict(self, klines_dict: Dict[str, List[Dict]]) -> GainPredictionResult:
        """批量预测股票涨幅

        Args:
            klines_dict: {code: [klines]} 股票代码到K线数据的映射
                        K线按日期升序排列

        Returns:
            GainPredictionResult 批量预测结果
        """
        predictions = []
        total_confidence = 0.0

        for code, klines in klines_dict.items():
            if not klines:
                continue

            name = klines[-1].get('name', klines[-1].get('code', code))
            features = calculate_features(klines)

            pred = self._predict_single(code, name, features, klines)
            if pred:
                predictions.append(pred)
                total_confidence += pred.confidence

        # 排序：按预测5日涨幅降序
        predictions.sort(key=lambda x: x.predicted_gain_5d, reverse=True)

        # 计算分布统计
        distribution = self._calc_distribution(predictions)

        avg_confidence = total_confidence / len(predictions) if predictions else 0.0

        return GainPredictionResult(
            predictions=predictions,
            calculated_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            data_timestamp=klines[-1].get('date', datetime.now().strftime("%Y-%m-%d")) if klines_dict else "",
            stock_count=len(predictions),
            distribution=distribution,
            avg_confidence=avg_confidence
        )

    def _predict_single(self, code: str, name: str,
                       features: Dict[str, float],
                       klines: List[Dict]) -> Optional[GainPrediction]:
        """预测单只股票涨幅"""
        if len(klines) < 5:
            return None

        # ========== 综合预测公式 ==========
        # predicted = 动量因子 × 波动率调整 + 趋势加成 + RSI调整 + MACD调整

        # 动量因子
        momentum = (features.get('gain_3d', 0) * 0.4 +
                   features.get('gain_5d', 0) * 0.3 +
                   features.get('gain_10d', 0) * 0.3)

        # 波动率调整
        volatility = features.get('volatility_20d', GLOBAL_AVG_VOLATILITY)
        volatility_factor = min(volatility / 30.0, 1.5)

        # 趋势加成
        ma_position = features.get('ma_position', 1.0)
        trend_bonus = (ma_position - 1.0) * 20 if ma_position > 1 else 0

        # RSI调整（超买超卖修正）
        rsi = features.get('rsi_14', 50)
        rsi_bonus = 0
        if rsi < 30:
            rsi_bonus = (30 - rsi) / 10 * 1.5  # 超卖加成
        elif rsi > 70:
            rsi_bonus = (70 - rsi) / 10 * 1.5  # 超买减成

        # MACD调整（金叉死叉信号）
        macd_cross = features.get('macd_cross', 0)
        macd_bonus = macd_cross * 1.0  # 金叉+1，死叉-1

        # 综合预测
        predicted = (momentum * volatility_factor + trend_bonus +
                     rsi_bonus + macd_bonus)

        # ========== 涨跌停处理 ==========
        predicted = self._apply_limit_adjustment(predicted, klines)

        # ========== 置信度计算 ==========
        confidence = min(0.6 + 0.4 * (1 - volatility / 50), 0.95)

        # ========== 置信区间 ==========
        interval_width = volatility * 0.4 * confidence
        confidence_interval_3d = (
            max(predicted - interval_width, -30),
            min(predicted + interval_width, 30)
        )
        confidence_interval_5d = (
            max(predicted * 1.5 - interval_width * 1.5, -50),
            min(predicted * 1.5 + interval_width * 1.5, 50)
        )

        # ========== 预测3日和5日 ==========
        # 3日预测：主要基于短期动量和RSI
        predicted_gain_3d = (features.get('gain_3d', 0) * 0.6 +
                            rsi_bonus * 0.5 +
                            macd_bonus * 0.3)
        predicted_gain_3d = self._apply_limit_adjustment(predicted_gain_3d, klines)

        # 5日预测：使用综合预测
        predicted_gain_5d = predicted

        # 限制在合理范围内
        predicted_gain_3d = max(-30.0, min(30.0, predicted_gain_3d))
        predicted_gain_5d = max(-50.0, min(50.0, predicted_gain_5d))

        return GainPrediction(
            code=code,
            name=name,
            predicted_gain_3d=round(predicted_gain_3d, 2),
            predicted_gain_5d=round(predicted_gain_5d, 2),
            confidence=round(confidence, 3),
            confidence_interval_3d=tuple(round(x, 2) for x in confidence_interval_3d),
            confidence_interval_5d=tuple(round(x, 2) for x in confidence_interval_5d),
            features={
                'gain_3d': round(float(features.get('gain_3d', 0)), 2),
                'gain_5d': round(float(features.get('gain_5d', 0)), 2),
                'volatility_20d': round(float(features.get('volatility_20d', 0)), 2),
                'rsi_14': round(float(features.get('rsi_14', 50)), 1),
            },
            model_version=self.model_version
        )

    def _apply_limit_adjustment(self, predicted: float, klines: List[Dict]) -> float:
        """应用涨跌停限制调整"""
        if not klines:
            return predicted

        today_change = klines[-1].get('change_pct', 0)
        board_type = self._get_board_type(klines[-1].get('code', ''))
        limit_pct = BOARD_LIMIT_CONFIG.get(board_type, 10)

        # 涨停
        if today_change >= limit_pct - 0.1:
            return float(max(predicted, 5.0))  # 最低5%涨幅

        # 跌停
        if today_change <= -limit_pct + 0.1:
            return float(min(predicted, -3.0))  # 最高-3%跌幅

        # 正常：限制在板块涨跌幅内
        return float(max(-limit_pct, min(limit_pct, predicted)))

    def _get_board_type(self, code: str) -> str:
        """根据代码判断板块类型"""
        if code.startswith('300'):
            return 'chinext'
        elif code.startswith('688'):
            return 'star'
        elif code.startswith('8') or code.startswith('4'):
            return 'bj'
        else:
            return 'main'

    def _calc_distribution(self, predictions: List[GainPrediction]) -> Dict[str, float]:
        """计算预测分布统计"""
        if not predictions:
            return {}

        gains = [p.predicted_gain_5d for p in predictions]

        return {
            'mean': round(sum(gains) / len(gains), 2),
            'min': round(min(gains), 2),
            'max': round(max(gains), 2),
            'positive_count': sum(1 for g in gains if g > 0),
            'negative_count': sum(1 for g in gains if g < 0),
        }

    def to_dict(self, result: GainPredictionResult) -> Dict:
        """转换为字典格式"""
        return {
            'predictions': [
                {
                    'code': p.code,
                    'name': p.name,
                    'predicted_gain_3d': p.predicted_gain_3d,
                    'predicted_gain_5d': p.predicted_gain_5d,
                    'confidence': p.confidence,
                    'confidence_interval_3d': p.confidence_interval_3d,
                    'confidence_interval_5d': p.confidence_interval_5d,
                    'features': p.features,
                    'model_version': p.model_version,
                }
                for p in result.predictions
            ],
            'calculated_at': result.calculated_at,
            'data_timestamp': result.data_timestamp,
            'stock_count': result.stock_count,
            'distribution': result.distribution,
            'avg_confidence': result.avg_confidence,
        }

    def save_to_store(self, result: GainPredictionResult, date: str = None) -> int:
        """保存预测结果到 prediction_store

        Args:
            result: 预测结果
            date: 日期，默认当天

        Returns:
            保存的股票数量
        """
        from data_manager.prediction_store import get_prediction_store

        if date is None:
            from datetime import datetime
            date = datetime.now().strftime("%Y-%m-%d")

        predictions = [
            {
                'code': p.code,
                'name': p.name,
                'predicted_gain_3d': p.predicted_gain_3d,
                'predicted_gain_5d': p.predicted_gain_5d,
                'confidence': p.confidence,
                'confidence_interval_3d': p.confidence_interval_3d,
                'confidence_interval_5d': p.confidence_interval_5d,
                'features': p.features,
                'model_version': p.model_version,
            }
            for p in result.predictions
        ]

        store = get_prediction_store()
        return store.record_gain_predictions(predictions, date)


# 全局实例
_predictor: Optional[GainPredictor] = None


def get_gain_predictor() -> GainPredictor:
    """获取 GainPredictor 单例"""
    global _predictor
    if _predictor is None:
        _predictor = GainPredictor()
    return _predictor
