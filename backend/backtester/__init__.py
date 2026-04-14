"""
回测验证模块 - Backtester v19.8
================================
职责：历史数据回测、策略验证、绩效评估

核心流程：
1. T日收盘：获取战力数据 → 策略选股 → 生成调仓信号
2. T+1日收盘：执行成交 → 更新持仓 → 记录净值

主要类：
- Backtest: 回测引擎
- PositionManager: 持仓管理器 v19.8新增
- Strategy: 策略基类
- StockFactor: 股票因子数据
- BacktestResult: 回测结果
- Metrics: 绩效指标计算
- BacktestVerifier: 回测验证器 v19.7新增
"""

from .backtest import (
    Backtest,
    BacktestEngine,
    Position,
    PositionManager,
)
from .strategies import (
    Strategy,
    StockFactor,
    TopNStrategy,
    ValueStrategy,
    GrowthStrategy,
    MomentumStrategy,
    CustomStrategy,
    MultiFactorStrategy,
)
from .metrics import (
    Trade,
    BacktestResult,
    Metrics,
)
from .reports import generate_report, save_report
from .verification import (
    BacktestVerifier,
    BacktestReportStore,
    SwapVerification,
    CPPredictionAccuracy,
    GainPredictionAccuracy,
    ProbabilityPredictionAccuracy,
    verify_swap_effectiveness,
    verify_cp_prediction_accuracy,
    verify_gain_prediction_accuracy,
    verify_probability_prediction_accuracy,
    get_verification_report,
    save_verification_report,
    save_backtest_report,
    get_report_store,
)

__all__ = [
    # 回测引擎
    'Backtest',
    'BacktestEngine',
    'Position',
    'PositionManager',

    # 策略
    'Strategy',
    'StockFactor',
    'TopNStrategy',
    'ValueStrategy',
    'GrowthStrategy',
    'MomentumStrategy',
    'CustomStrategy',
    'MultiFactorStrategy',

    # 指标与结果
    'Trade',
    'BacktestResult',
    'Metrics',

    # 报告
    'generate_report',
    'save_report',

    # 回测验证
    'BacktestVerifier',
    'BacktestReportStore',
    'SwapVerification',
    'CPPredictionAccuracy',
    'GainPredictionAccuracy',
    'ProbabilityPredictionAccuracy',
    'verify_swap_effectiveness',
    'verify_cp_prediction_accuracy',
    'verify_gain_prediction_accuracy',
    'verify_probability_prediction_accuracy',
    'get_verification_report',
    'save_verification_report',
    'save_backtest_report',
    'get_report_store',
]
