"""
智能推荐模块 - Recommender v18.5
================================
职责：基于分析引擎给出买卖建议

支持三大操作场景：
1. 换股：卖出A，买入B
2. 纯买入：空仓/轻仓直接买入
3. 纯卖出：持仓止盈/止损卖出

v18.5 新增：
- 预测融合（v19.8）：战力与预测引擎结果融合
"""

from .recommend_engine import RecommendEngine, get_recommend_engine, RecommenderCallback
from .filters import StockFilter
from .swap_calculator import SwapCalculator
from .buy_analyzer import BuyAnalyzer, BuySignal
from .sell_analyzer import SellAnalyzer, SellSignal
from .fusion import PredictionFusion, FusionResult
from .prompts import (
    generate_stock_prompt,
    generate_highlights,
    generate_risk_warnings,
    generate_swap_prompt,
    PromptsGenerator
)

__all__ = [
    # 核心引擎
    'RecommendEngine',
    'get_recommend_engine',
    'RecommenderCallback',

    # 过滤器
    'StockFilter',

    # 换股计算
    'SwapCalculator',

    # 买入分析
    'BuyAnalyzer',
    'BuySignal',

    # 卖出分析
    'SellAnalyzer',
    'SellSignal',

    # 预测融合 v19.8
    'PredictionFusion',
    'FusionResult',

    # 推荐理由
    'generate_stock_prompt',
    'generate_highlights',
    'generate_risk_warnings',
    'generate_swap_prompt',
    'PromptsGenerator',
]
