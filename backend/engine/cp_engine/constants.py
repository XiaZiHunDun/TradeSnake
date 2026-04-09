"""
引擎常量配置 - Engine Constants
==============================
战力公式权重、交易成本等常量配置
"""

# 战力公式权重 v19.6（赚钱版）
# 成长(30%) + 价值(25%) + 质量(20%) + 动量(8%) + 实时(2%) + 风险调整(10%)
# v19.6改动：新增real_time_score(2%)，基于1分钟K线，仅核心池计算
WEIGHTS = {
    'growth': 0.30,
    'value': 0.25,
    'quality': 0.20,
    'momentum': 0.08,  # 从0.10降到0.08
    'real_time': 0.02,  # 新增实时因子（v19.6）
    'risk_penalty': 0.10
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
RISK_FREE_RATE = 0.02

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
