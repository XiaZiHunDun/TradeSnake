"""
分析引擎模块 - Engine v19.7
============================
职责：战力计算、风险评估、历史追踪

子模块：
- cp_engine: 战力计算核心
- risk_analyzer: 风险评估
- history: 战力历史
- constants: 常量配置
- indicators: 技术指标 v18.2+v19.6（新增分钟级均线）
- cache: 因子级缓存 v18.2
- parallel: 并行计算 v18.2
- trading_time: 交易时间判断
- refresh_strategy: 刷新策略 v19.7

v19.7新增：
- refresh_strategy 模块（从stock_selector迁移更新策略逻辑）
- cp_history 迁移到 data_manager 统一管理

v19.6新增：
- real_time_score 实时因子（基于1分钟K线）
- calculate_real_time_score 方法
"""

from .cp_engine import (
    CPEngine, StockCP, CashCP, TradeDecision, create_stock_from_raw,
    WEIGHTS, TRADE_COST, TOTAL_TRADE_COST_RATE,
    DataValidator, ValidationResult
)
from .risk_analyzer import RiskAnalyzer, KellyCalculator
from .history import (
    save_history, load_history, get_stock_history,
    calc_momentum_nd, get_momentum_3d, get_momentum_5d,
    get_cp_changes, get_historical_rankings, get_ranking_changes
)
from .refresh_strategy import get_refresh_interval, get_market_phase
from .trading_time import is_trading_time, get_trading_status
from .indicators import TechnicalIndicators
from .cache import FactorCache, get_factor_cache, cache_stock_factors, get_cached_stock_factors
from .parallel import ParallelCalculator, get_parallel_calculator

__all__ = [
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
]
