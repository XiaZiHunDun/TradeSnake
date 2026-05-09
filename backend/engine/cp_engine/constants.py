"""
引擎常量配置 - Engine Constants
==============================
战力公式权重、交易成本等常量配置
"""

# 战力公式权重 v21（数据驱动版）
# 基于 414 天 Alpha 分析 (2024-04-15~2026-04-23):
# growth IC=+0.0104 (t=2.46 显著), momentum IC=+0.0090 (t=1.71 边界)
# value IC=-0.0089 (反转), quality IC=-0.0027 (无效)
# 结论: growth 是唯一真正 alpha 因子，momentum 边界有效，value/quality 应清零/最小化
WEIGHTS = {
    'growth': 0.50,      # 唯一显著正 IC (t=2.46)，大幅增配
    'value': 0.00,       # IC=-0.009，反转因子，清零
    'quality': 0.05,     # IC=-0.003，几乎无效，降到最低
    'momentum': 0.28,    # t=1.71 边界显著，保持适度权重
    'real_time': 0.02,   # 不变
    'risk_penalty': 0.10 # 不变（惩罚项，不参与因子归一化）
}

# 动量子因子权重 v20.1（反转主导）
# Alpha 数据: 短期反转 IC 为正（跌多反弹），中期动量 IC 为负
MOMENTUM_WEIGHTS = {
    'short_reversal': 0.50,
    'medium_momentum': 0.15,
    'volume_confirm': 0.20,
    'daily_change': 0.15,
}

# 动量计算参数
MOMENTUM_PARAMS = {
    'reversal_days': 5,
    'momentum_days': 20,
    'momentum_skip_days': 5,
    'volume_lookback': 10,
    'volume_avg_days': 20,
}

# A股交易费用（2024年最新标准）
TRADE_COST = {
    'commission': 0.0003,       # 券商佣金：万分之三
    'stamp_tax': 0.0005,        # 印花税：万分之五，仅卖出时收取
    'transfer_fee': 0.00001,    # 过户费：十万分之一，沪市双向，深市免
    'min_commission': 5.0,     # 最低佣金：5元/笔
}

# 完整换股一次的成本比率
SELL_COST_RATE = TRADE_COST['commission'] + TRADE_COST['stamp_tax'] + TRADE_COST['transfer_fee']
BUY_COST_RATE = TRADE_COST['commission'] + TRADE_COST['transfer_fee']
TOTAL_TRADE_COST_RATE = SELL_COST_RATE + BUY_COST_RATE

# 最小有意义交易量
MIN_TRADE_VALUE = 50000

# 现金CP配置
CASH_CP_BASELINE = 50
RISK_FREE_RATE = 0.03  # 无风险利率 3%（与其他模块保持一致）

# 财报发布月份
EARNINGS_SEASON_MONTHS = [4, 7, 10]

# 仓位集中度阈值
CONCENTRATION_THRESHOLDS = {
    'high': 70,
    'medium': 50,
    'low': 30
}

# 小额账户阈值
SMALL_ACCOUNT_THRESHOLD = 5000
MIN_MEANINGFUL_TRADE = 50000

# 实盘风控参数（v19.10）
RISK_MANAGEMENT = {
    'enabled': True,                    # 总开关
    'stop_loss_pct': -0.07,             # 固定止损 -7%
    'trailing_stop_pct': -0.08,         # 尾随止损：从最高价回撤 8%（v21 walk_forward 全局最优点）
    'portfolio_drawdown_limit': -0.15,  # 组合最大回撤 -15%
    'portfolio_drawdown_action': 'reduce',  # 'reduce'(减半仓位) 或 'clear'(清仓)
    'use_kelly_sizing': True,           # 是否使用 Kelly 计算仓位
    'kelly_fraction': 0.5,              # Kelly 系数折扣（半 Kelly，更保守）
    'max_single_position_pct': 0.20,    # 单只股票最大仓位占比 20%
    'market_regime_enabled': True,      # 是否启用市场环境识别
    'market_ma_period': 20,             # 大盘 MA 周期
    'bull_position_pct': 1.0,           # 牛市仓位 100%
    'bear_position_pct': 0.5,           # 熊市仓位 50%
}
