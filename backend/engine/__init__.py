"""
分析引擎模块 - Engine v19.8
===========================
职责：战力计算、风险评估、历史追踪、预测分析

子模块：
- cp_engine: 战力计算核心
- gain_predictor: 涨幅预测引擎
- probability_predictor: 上涨概率预测引擎
"""

from .cp_engine import (
    CPEngine, StockCP, CashCP, TradeDecision, create_stock_from_raw,
    WEIGHTS, TRADE_COST, TOTAL_TRADE_COST_RATE,
    DataValidator, ValidationResult,
    RiskAnalyzer, KellyCalculator,
    save_history, load_history, get_stock_history,
    calc_momentum_nd, get_momentum_3d, get_momentum_5d,
    get_cp_changes, get_historical_rankings, get_ranking_changes,
    get_refresh_interval, get_market_phase,
    is_trading_time, get_trading_status,
    TechnicalIndicators,
    FactorCache, get_factor_cache, cache_stock_factors, get_cached_stock_factors,
    ParallelCalculator, get_parallel_calculator,
)

# 预测引擎
from .gain_predictor import (
    GainPredictor, GainPrediction, GainPredictionResult,
    get_gain_predictor,
)
from .probability_predictor import (
    ProbabilityPredictor, ProbabilityPrediction, ProbabilityPredictionResult,
    get_probability_predictor,
)

__all__ = [
    # 战力引擎
    'CPEngine', 'StockCP', 'CashCP', 'TradeDecision', 'create_stock_from_raw',
    'WEIGHTS', 'TRADE_COST', 'TOTAL_TRADE_COST_RATE',
    'DataValidator', 'ValidationResult',
    'RiskAnalyzer', 'KellyCalculator',
    'save_history', 'load_history', 'get_stock_history',
    'calc_momentum_nd', 'get_momentum_3d', 'get_momentum_5d',
    'get_cp_changes', 'get_historical_rankings', 'get_ranking_changes',
    'get_refresh_interval', 'get_market_phase',
    'is_trading_time', 'get_trading_status',
    'TechnicalIndicators',
    'FactorCache', 'get_factor_cache', 'cache_stock_factors', 'get_cached_stock_factors',
    'ParallelCalculator', 'get_parallel_calculator',
    # 预测引擎
    'GainPredictor', 'GainPrediction', 'GainPredictionResult', 'get_gain_predictor',
    'ProbabilityPredictor', 'ProbabilityPrediction', 'ProbabilityPredictionResult', 'get_probability_predictor',
]
