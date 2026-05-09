"""
预测融合器 - Prediction Fusion v19.8
=====================================
职责：融合战力评分与预测引擎结果

融合公式：
综合得分 = 战力权重 × cp_norm + 涨幅预测权重 × gain_norm × confidence + 上涨概率权重 × prob_norm × confidence

其中：
- cp_norm = total_cp / 100 (归一化到0-1)
- gain_norm = predicted_gain_5d / 50 (归一化到0-1，假设50%为上限)
- prob_norm = up_probability_5d (已是0-1)
- confidence = 预测置信度 (0-1)

设计文档: docs/plans/recommender/RECOMMENDER_OVERVIEW.md v19.8
"""

import ast
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from backend.engine import StockCP
from backend.engine.gain_predictor import GainPrediction
from backend.engine.probability_predictor import ProbabilityPrediction

logger = logging.getLogger(__name__)


def _safe_parse_interval(value, default: Tuple[float, float] = (0.0, 0.0)) -> Tuple[float, float]:
    """安全解析 confidence_interval，支持字符串/列表/元组格式，防止格式错误导致崩溃

    Args:
        value: confidence_interval 值，可能来自:
            - prediction_store 已解析的 tuple/list (P1 修复)
            - DB 返回的 JSON 字符串 (兼容旧逻辑)
        default: 解析失败时返回的默认值
    """
    if value is None:
        return default
    # P1 修复：prediction_store.get_gain_predictions() 已通过 _str_to_tuple 解析
    if isinstance(value, (tuple, list)):
        if len(value) == 2:
            return (float(value[0]), float(value[1]))
        return default
    # 兼容字符串格式（旧逻辑）
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, (tuple, list)) and len(parsed) == 2:
                return (float(parsed[0]), float(parsed[1]))
            return default
        except (ValueError, SyntaxError):
            return default
    return default


@dataclass
class FusionResult:
    """融合结果"""
    code: str
    name: str
    total_cp: float  # 战力评分
    predicted_gain_5d: float  # 预测5日涨幅
    up_probability_5d: float  # 5日上涨概率
    confidence: float  # 预测置信度
    risk_level: str  # 风险等级
    volatility_20d: float  # 20日波动率 (%，年化)
    fused_score: float  # 融合得分
    fused_rank: int  # 融合排名
    # 分项得分
    cp_score: float
    gain_score: float
    prob_score: float


class PredictionFusion:
    """预测融合器 - v19.8

    融合战力评分与预测引擎结果，优先推荐"战力高+预测好"的股票。

    融合公式：
    综合得分 = 战力权重 × cp_norm + 涨幅预测权重 × gain_norm × confidence
             + 上涨概率权重 × prob_norm × confidence

    其中：
    - cp_norm = total_cp / 100 (归一化到0-1)
    - gain_norm = predicted_gain_5d / 50 (归一化到0-1，假设50%为上限)
    - prob_norm = up_probability_5d (已是0-1)
    """

    # 权重配置
    WEIGHT_CONFIG = {
        'conservative': {'cp': 0.5, 'gain': 0.3, 'prob': 0.2},
        'balanced': {'cp': 0.4, 'gain': 0.35, 'prob': 0.25},
        'aggressive': {'cp': 0.3, 'gain': 0.4, 'prob': 0.3},
    }

    # 过滤条件
    FILTER_MIN_GAIN_5D = 0  # 预测涨幅必须>0（过滤预测下跌）
    FILTER_MIN_PROB_5D = 0.5  # 上涨概率必须>50%
    FILTER_MAX_RISK_LEVEL = 'high'  # 过滤高风险
    # 波动率过滤：年化波动率上限 40%（与 probability_predictor 的 40 阈值单位一致）
    FILTER_MAX_VOLATILITY = 40

    @classmethod
    def fuse(
        cls,
        stock: StockCP,
        gain_pred: Optional[GainPrediction] = None,
        prob_pred: Optional[ProbabilityPrediction] = None,
        risk_preference: str = 'balanced'
    ) -> FusionResult:
        """融合单只股票的多个数据源

        Args:
            stock: 股票战力数据
            gain_pred: 涨幅预测（可选）
            prob_pred: 上涨概率预测（可选）
            risk_preference: 风险偏好 (conservative/balanced/aggressive)

        Returns:
            FusionResult 融合结果
        """
        weights = cls.WEIGHT_CONFIG[risk_preference]

        # 获取预测数据（安全获取）
        predicted_gain_5d = gain_pred.predicted_gain_5d if gain_pred else 0
        up_probability_5d = prob_pred.up_probability_5d if prob_pred else 0.5
        confidence = gain_pred.confidence if gain_pred else (prob_pred.confidence if prob_pred else 0)
        risk_level = prob_pred.risk_level if prob_pred else cls._get_risk_level(stock)

        # 归一化
        cp_norm = stock.total_cp / 100.0  # 归一化到0-1
        gain_norm = max(0, min(1, predicted_gain_5d / 50.0))  # 限制在[0,1]
        prob_norm = up_probability_5d  # 已是0-1

        # 分项得分
        cp_score = weights['cp'] * cp_norm
        gain_score = weights['gain'] * gain_norm * confidence if confidence > 0 else 0
        prob_score = weights['prob'] * prob_norm * confidence if confidence > 0 else 0

        # 融合得分
        fused_score = cp_score + gain_score + prob_score

        return FusionResult(
            code=stock.code,
            name=stock.name,
            total_cp=stock.total_cp,
            predicted_gain_5d=predicted_gain_5d,
            up_probability_5d=up_probability_5d,
            confidence=confidence,
            risk_level=risk_level,
            volatility_20d=getattr(stock, 'volatility_20d', 0.0),
            fused_score=fused_score,
            fused_rank=0,  # 待排序后填充
            cp_score=cp_score,
            gain_score=gain_score,
            prob_score=prob_score
        )

    @classmethod
    def fuse_batch(
        cls,
        stocks: List[StockCP],
        gain_predictions: Dict[str, GainPrediction],
        prob_predictions: Dict[str, ProbabilityPrediction],
        risk_preference: str = 'balanced'
    ) -> List[FusionResult]:
        """批量融合

        Args:
            stocks: 股票列表
            gain_predictions: {code: GainPrediction}
            prob_predictions: {code: ProbabilityPrediction}
            risk_preference: 风险偏好

        Returns:
            融合结果列表（按融合得分降序）
        """
        results = []

        for stock in stocks:
            gain_pred = gain_predictions.get(stock.code)
            prob_pred = prob_predictions.get(stock.code)

            # 过滤条件
            filter_reason = cls._get_filter_reason(stock, gain_pred, prob_pred)
            if filter_reason:
                logger.info(f"Fusion filtered out {stock.code} ({stock.name}): {filter_reason}")
                continue

            result = cls.fuse(stock, gain_pred, prob_pred, risk_preference)
            results.append(result)

        # 按融合得分降序排序
        results.sort(key=lambda x: x.fused_score, reverse=True)

        # 填充排名
        for i, result in enumerate(results):
            result.fused_rank = i + 1

        return results

    @classmethod
    def _passes_filter(
        cls,
        stock: StockCP,
        gain_pred: Optional[GainPrediction],
        prob_pred: Optional[ProbabilityPrediction]
    ) -> bool:
        """检查是否通过过滤条件"""
        return cls._get_filter_reason(stock, gain_pred, prob_pred) is None

    @classmethod
    def _get_filter_reason(
        cls,
        stock: StockCP,
        gain_pred: Optional[GainPrediction],
        prob_pred: Optional[ProbabilityPrediction]
    ) -> Optional[str]:
        """返回过滤原因字符串，如果通过则返回 None"""
        # 预测涨幅过滤
        if gain_pred is None:
            return "gain_pred is None"
        if gain_pred.predicted_gain_5d < cls.FILTER_MIN_GAIN_5D:
            return f"predicted_gain_5d {gain_pred.predicted_gain_5d:.2f} < {cls.FILTER_MIN_GAIN_5D}"

        # 上涨概率过滤
        if prob_pred is None:
            return "prob_pred is None"
        if prob_pred.up_probability_5d < cls.FILTER_MIN_PROB_5D:
            return f"up_probability_5d {prob_pred.up_probability_5d:.3f} < {cls.FILTER_MIN_PROB_5D}"

        # 风险等级过滤：统一使用 _get_risk_level() 判断（与 fuse() 保持一致）
        risk_lvl = prob_pred.risk_level if prob_pred else cls._get_risk_level(stock)
        if risk_lvl == cls.FILTER_MAX_RISK_LEVEL:
            return f"risk_level={risk_lvl}"

        # 波动率过滤
        volatility = getattr(stock, 'volatility_20d', 0)
        if volatility > cls.FILTER_MAX_VOLATILITY:
            return f"volatility_20d {volatility:.2f} > {cls.FILTER_MAX_VOLATILITY:.2f}"

        return None

    @classmethod
    def _get_risk_level(cls, stock: StockCP) -> str:
        """从战力数据推断风险等级"""
        if stock.risk_score > 70:
            return 'high'
        elif stock.risk_score > 50:
            return 'medium'
        else:
            return 'low'

    @classmethod
    def to_dict(cls, result: FusionResult) -> Dict:
        """转换为字典格式"""
        return {
            'code': result.code,
            'name': result.name,
            'total_cp': round(result.total_cp, 1),
            'predicted_gain_5d': round(result.predicted_gain_5d, 2),
            'up_probability_5d': round(result.up_probability_5d, 3),
            'confidence': round(result.confidence, 3),
            'risk_level': result.risk_level,
            'volatility_20d': round(result.volatility_20d, 2),
            'fused_score': round(result.fused_score, 4),
            'fused_rank': result.fused_rank,
            'cp_score': round(result.cp_score, 4),
            'gain_score': round(result.gain_score, 4),
            'prob_score': round(result.prob_score, 4),
        }

    @classmethod
    def get_latest_predictions(cls, codes: List[str]) -> Tuple[Dict[str, GainPrediction], Dict[str, ProbabilityPrediction]]:
        """从 prediction_store 获取最新预测数据

        Args:
            codes: 股票代码列表

        Returns:
            (gain_predictions, prob_predictions) 预测字典
        """
        from backend.data_manager.prediction_store import get_prediction_store

        store = get_prediction_store()
        gain_predictions = {}
        prob_predictions = {}

        for code in codes:
            # 获取最新涨幅预测（优先今天，如果今天没预测则查近7天）
            gain_list = store.get_gain_predictions(code, days=7)
            if gain_list:
                latest = gain_list[0]
                gain_predictions[code] = GainPrediction(
                    code=latest['code'],
                    name=latest['name'],
                    predicted_gain_3d=latest['predicted_gain_3d'],
                    predicted_gain_5d=latest['predicted_gain_5d'],
                    confidence=latest['confidence'],
                    confidence_interval_3d=_safe_parse_interval(latest.get('confidence_interval_3d')),
                    confidence_interval_5d=_safe_parse_interval(latest.get('confidence_interval_5d')),
                    features=latest.get('features', {}),
                    model_version=latest.get('model_version', 'rule_v19.8')
                )

            # 获取最新概率预测（优先今天，如果今天没预测则查近7天）
            prob_list = store.get_probability_predictions(code, days=7)
            if prob_list:
                latest = prob_list[0]
                prob_predictions[code] = ProbabilityPrediction(
                    code=latest['code'],
                    name=latest['name'],
                    up_probability_3d=latest['up_probability_3d'],
                    up_probability_5d=latest['up_probability_5d'],
                    confidence=latest['confidence'],
                    confidence_interval_3d=_safe_parse_interval(latest.get('confidence_interval_3d')),
                    confidence_interval_5d=_safe_parse_interval(latest.get('confidence_interval_5d')),
                    risk_level=latest.get('risk_level', 'medium'),
                    features=latest.get('features', {}),
                    model_version=latest.get('model_version', 'rule_v19.8')
                )

        return gain_predictions, prob_predictions
