"""
上涨概率预测器模块

基于技术指标的规则模型预测股票未来N日上涨概率：
- 每日收盘后执行一次
- 预测结果存储到 prediction_store（90天）

设计文档：docs/plans/engine/probability_predictor/PROBABILITY_PREDICTOR.md
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

from .features import calculate_features, GLOBAL_AVG_VOLATILITY


@dataclass
class ProbabilityPrediction:
    """单只股票上涨概率预测"""
    code: str
    name: str
    up_probability_3d: float  # 3日上涨概率 0-1
    up_probability_5d: float  # 5日上涨概率 0-1
    confidence: float  # 置信度 0-1
    risk_level: str  # high/medium/low
    features: Dict[str, float]  # 主要特征值
    model_version: str = "rule_v19.8"


@dataclass
class ProbabilityPredictionResult:
    """批量概率预测结果"""
    predictions: List[ProbabilityPrediction]
    calculated_at: str
    data_timestamp: str
    stock_count: int


class ProbabilityPredictor:
    """上涨概率预测器"""

    def __init__(self):
        self.model_version = "rule_v19.8"

    def predict(self, klines_dict: Dict[str, List[Dict]]) -> ProbabilityPredictionResult:
        """批量预测股票上涨概率

        Args:
            klines_dict: {code: [klines]} 股票代码到K线数据的映射
                        K线按日期升序排列

        Returns:
            ProbabilityPredictionResult 批量预测结果
        """
        predictions = []

        for code, klines in klines_dict.items():
            if not klines:
                continue

            name = klines[-1].get('name', klines[-1].get('code', code))
            features = calculate_features(klines)

            pred = self._predict_single(code, name, features, klines)
            if pred:
                predictions.append(pred)

        # 排序：按5日上涨概率降序
        predictions.sort(key=lambda x: x.up_probability_5d, reverse=True)

        return ProbabilityPredictionResult(
            predictions=predictions,
            calculated_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            data_timestamp=klines[-1].get('date', datetime.now().strftime("%Y-%m-%d")) if klines_dict else "",
            stock_count=len(predictions),
        )

    def _predict_single(self, code: str, name: str,
                       features: Dict[str, float],
                       klines: List[Dict]) -> Optional[ProbabilityPrediction]:
        """预测单只股票上涨概率"""
        if len(klines) < 5:
            return None

        # ========== 综合得分计算 ==========
        # 综合得分 = 动量得分×50% + 趋势得分×20% + RSI得分×20% + KDJ得分×10%

        # 动量得分：归一化到 -1 ~ +1
        momentum_score = (features.get('gain_3d', 0) * 0.5 +
                         features.get('gain_5d', 0) * 0.3 +
                         features.get('gain_10d', 0) * 0.2) / 25.0
        momentum_score = max(-1, min(1, momentum_score))

        # 趋势得分：MA位置偏离
        ma_position = features.get('ma_position', 1.0)
        if ma_position >= 1.0:
            trend_score = (ma_position - 0.95) * 5  # 站上MA20为正
        else:
            trend_score = (ma_position - 1.05) * 5  # 跌破MA20为负
        trend_score = max(-0.5, min(0.5, trend_score))

        # RSI得分：超买超卖修正
        rsi = features.get('rsi_14', 50)
        if rsi < 30:
            rsi_score = (30 - rsi) / 20 * 0.15  # 超卖加成，最多+0.15
        elif rsi > 70:
            rsi_score = (70 - rsi) / 20 * 0.15  # 超买减成，最多-0.15
        else:
            rsi_score = 0
        rsi_score = max(-0.15, min(0.15, rsi_score))

        # KDJ得分：金叉死叉信号
        kdj_cross = features.get('kdj_cross', 0)
        kdj_j = features.get('kdj_j', 50)
        if kdj_cross > 0 and kdj_j > 0:
            kdj_score = 0.1  # 金叉且J>0为正
        elif kdj_cross < 0:
            kdj_score = -0.1  # 死叉为负
        else:
            kdj_score = 0

        # 综合得分
        combined_score = (momentum_score * 0.5 +
                         trend_score * 0.2 +
                         rsi_score * 0.2 +
                         kdj_score * 0.1)

        # ========== 概率转换 ==========
        # 上涨概率 = (综合得分 + 1) / 2
        up_probability = (combined_score + 1) / 2

        # ========== 涨跌停处理 ==========
        up_probability = self._apply_limit_adjustment(up_probability, klines)

        # ========== 置信度计算 ==========
        # confidence = min(0.5 + abs(综合得分) × 0.3, 0.9)
        confidence = min(0.5 + abs(combined_score) * 0.3, 0.9)

        # ========== 风险等级 ==========
        volatility = features.get('volatility_20d', GLOBAL_AVG_VOLATILITY)
        if volatility > 40:
            risk_level = 'high'
        elif volatility > 20:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        # ========== 预测3日和5日 ==========
        # 3日概率：更侧重短期动量和RSI
        momentum_3d = features.get('gain_3d', 0) / 20.0
        momentum_3d = max(-1, min(1, momentum_3d))
        combined_3d = (momentum_3d * 0.6 + rsi_score * 0.3 + kdj_score * 0.1)
        up_probability_3d = (combined_3d + 1) / 2
        up_probability_3d = self._apply_limit_adjustment(up_probability_3d, klines)

        # 5日概率：使用综合得分
        up_probability_5d = up_probability

        # 限制在 [0, 1] 范围内
        up_probability_3d = max(0.0, min(1.0, up_probability_3d))
        up_probability_5d = max(0.0, min(1.0, up_probability_5d))

        return ProbabilityPrediction(
            code=code,
            name=name,
            up_probability_3d=round(up_probability_3d, 3),
            up_probability_5d=round(up_probability_5d, 3),
            confidence=round(confidence, 3),
            risk_level=risk_level,
            features={
                'gain_3d': round(float(features.get('gain_3d', 0)), 2),
                'volatility_20d': round(float(features.get('volatility_20d', 0)), 2),
                'rsi_14': round(float(features.get('rsi_14', 50)), 1),
            },
            model_version=self.model_version
        )

    def _apply_limit_adjustment(self, probability: float, klines: List[Dict]) -> float:
        """应用涨跌停限制调整概率"""
        if not klines:
            return probability

        today_change = klines[-1].get('change_pct', 0)

        # 涨停：最低0.65
        if today_change >= 9.9:
            return max(probability + 0.15, 0.65)

        # 跌停：最高0.25
        if today_change <= -9.9:
            return min(probability - 0.15, 0.25)

        return probability

    def to_dict(self, result: ProbabilityPredictionResult) -> Dict:
        """转换为字典格式"""
        return {
            'predictions': [
                {
                    'code': p.code,
                    'name': p.name,
                    'up_probability_3d': p.up_probability_3d,
                    'up_probability_5d': p.up_probability_5d,
                    'confidence': p.confidence,
                    'risk_level': p.risk_level,
                    'features': p.features,
                    'model_version': p.model_version,
                }
                for p in result.predictions
            ],
            'calculated_at': result.calculated_at,
            'data_timestamp': result.data_timestamp,
            'stock_count': result.stock_count,
        }

    def save_to_store(self, result: ProbabilityPredictionResult, date: str = None) -> int:
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
                'up_probability_3d': p.up_probability_3d,
                'up_probability_5d': p.up_probability_5d,
                'confidence': p.confidence,
                'risk_level': p.risk_level,
                'features': p.features,
                'model_version': p.model_version,
            }
            for p in result.predictions
        ]

        store = get_prediction_store()
        return store.record_probability_predictions(predictions, date)


# 全局实例
_predictor: Optional[ProbabilityPredictor] = None


def get_probability_predictor() -> ProbabilityPredictor:
    """获取 ProbabilityPredictor 单例"""
    global _predictor
    if _predictor is None:
        _predictor = ProbabilityPredictor()
    return _predictor
