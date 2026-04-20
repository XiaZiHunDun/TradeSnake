"""
涨幅预测引擎 - Gain Predictor v19.8
"""

from .predictor import (
    GainPredictor,
    GainPrediction,
    GainPredictionResult,
    get_gain_predictor,
    save_predictions_to_store,
)
from .features import (
    calculate_features,
    calculate_batch_features,
    GLOBAL_AVG_VOLATILITY,
)

__all__ = [
    'GainPredictor',
    'GainPrediction',
    'GainPredictionResult',
    'get_gain_predictor',
    'save_predictions_to_store',
    'calculate_features',
    'calculate_batch_features',
    'GLOBAL_AVG_VOLATILITY',
]
