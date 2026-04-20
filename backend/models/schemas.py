"""
数据模型 - TradeSnake Models
"""

from pydantic import BaseModel
from typing import List, Optional, Dict


class StockCPData(BaseModel):
    """股票战力数据"""
    code: str
    name: str
    price: float
    pe: float
    roe: float
    net_profit_growth: float
    revenue_growth: float
    change_pct: float
    growth_score: float
    value_score: float
    momentum_score: float
    quality_score: float = 0
    total_cp: float
    risk_score: float = 0
    risk_level: str = '较低'
    # 扩展字段
    peg: float = 0  # PEG估值
    pb: float = 0  # 市净率
    gross_margin: float = 0  # 毛利率
    revenue: float = 0  # 主营收入(亿)
    cashflow: float = 0  # 经营现金流(亿)
    debt_ratio: float = 0  # 资产负债率
    dividend_yield: float = 0  # 股息率(%)
    market_cap: float = 0  # 市值(亿)
    high: float = 0  # 最高价
    low: float = 0  # 最低价
    data_quality: str = 'low'  # 数据质量: high/medium/low
    # 板块信息
    board_type: str = 'main'  # 板块类型: main/gem/star/bge
    board_name: str = '主板'  # 板块显示名称
    can_trade_newbie: bool = True  # 新手是否可以交易
    trade_requirement: str = '新手可交易'  # 交易权限要求
    # 新增字段
    sector: str = ''  # 所属行业板块
    momentum_3d: float = 0  # 3日动量
    momentum_5d: float = 0  # 5日动量
    net_benefit_hint: str = ''  # 净收益提示
    # 安全性指标
    current_ratio: float = 0  # 流动比率
    interest_coverage: float = 0  # 利息保障倍数
    deducted_net_profit: float = 0  # 扣非净利润(亿)
    # v19.9.5 融合推荐字段
    kelly_position: float = 0  # Kelly建议仓位比例（%）
    predicted_gain_5d: float = 0  # 预测5日涨幅（%）
    up_probability_5d: float = 0  # 5日上涨概率（0-1）
    prediction_confidence: float = 0  # 预测置信度（0-1）
    fused_score: float = 0  # 融合得分


class CPListResponse(BaseModel):
    """战力榜单响应"""
    total: int
    data: List["SingleStockResponse"]
    updated_at: Optional[str] = None
    error: Optional[str] = None


class SwapSuggestion(BaseModel):
    """换股建议"""
    from_code: str
    from_name: str
    from_cp: float
    to_code: str
    to_name: str
    to_cp: float
    cp_improvement: float
    trade_cost: float
    net_benefit: float
    holding_days_equivalent: int
    action_level: str  # strong_buy/buy/hold/danger
    action_label: str


class RecommendResponse(BaseModel):
    """增强版推荐响应"""
    category: str
    total: int
    data: List[StockCPData]
    swap_suggestions: List[SwapSuggestion] = []
    portfolio_diversity: Dict[str, int] = {}
    filters_applied: Dict = {}
    risk_preference: str = 'aggressive'
    error: Optional[str] = None


class SingleStockResponse(BaseModel):
    """单只股票响应"""
    code: str
    name: str
    price: float
    pe: float
    roe: float
    net_profit_growth: float
    revenue_growth: float
    change_pct: float
    growth_score: float
    value_score: float
    momentum_score: float
    quality_score: float = 0
    total_cp: float
    risk_score: float = 0
    risk_level: str = '较低'
    # 扩展字段
    peg: float = 0  # PEG估值
    pb: float = 0  # 市净率
    gross_margin: float = 0  # 毛利率
    revenue: float = 0  # 主营收入(亿)
    cashflow: float = 0  # 经营现金流(亿)
    debt_ratio: float = 0  # 资产负债率
    dividend_yield: float = 0  # 股息率(%)
    market_cap: float = 0  # 市值(亿)
    high: float = 0  # 最高价
    low: float = 0  # 最低价
    data_quality: str = 'low'  # 数据质量: high/medium/low
    # 板块信息
    board_type: str = 'main'  # 板块类型: main/gem/star/bge
    board_name: str = '主板'  # 板块显示名称
    can_trade_newbie: bool = True  # 新手是否可以交易
    trade_requirement: str = '新手可交易'  # 交易权限要求
    # 新增字段
    sector: str = ''  # 所属行业板块
    momentum_3d: float = 0  # 3日动量
    momentum_5d: float = 0  # 5日动量
    # 安全性指标
    current_ratio: float = 0  # 流动比率
    interest_coverage: float = 0  # 利息保障倍数
    deducted_net_profit: float = 0  # 扣非净利润(亿)
    # v19.9.5 融合推荐字段
    kelly_position: float = 0  # Kelly建议仓位比例（%）
    predicted_gain_5d: float = 0  # 预测5日涨幅（%）
    up_probability_5d: float = 0  # 5日上涨概率（0-1）
    prediction_confidence: float = 0  # 预测置信度（0-1）
    fused_score: float = 0  # 融合得分


class Holding(BaseModel):
    """持仓"""
    code: str
    name: str
    quantity: int
    cost_price: float


class PersonalCPResponse(BaseModel):
    """个人战力响应"""
    total_cp: float
    holdings: List[Dict]
    updated_at: str


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: str
    data_fresh: bool
    last_update: Optional[str] = None
    stocks_count: int = 0


class MarketStatsResponse(BaseModel):
    """市场统计响应"""
    total_stocks: int
    avg_cp: float
    high_cp_count: int
    mid_cp_count: int
    low_cp_count: int
    avg_change: float
    rising_stocks: int
    falling_stocks: int
    unchanged_stocks: int


class TradeCostDetail(BaseModel):
    """交易成本明细"""
    principal: float
    sell_commission: float
    sell_stamp_tax: float
    sell_transfer_fee: float
    buy_commission: float
    buy_transfer_fee: float
    total_cost: float
    cost_rate: float


class TradeDecisionResponse(BaseModel):
    """换股决策响应 v15"""
    from_cp: float
    to_cp: float
    cp_diff: float
    expected_return: float
    holding_days: int
    gross_profit: float
    trade_cost: float
    net_profit: float
    net_return: float
    action: str
    action_level: str
    action_color: str
    action_label: str
    principal: float
    cost_breakdown: TradeCostDetail


class CashOpportunityResponse(BaseModel):
    """现金机会成本响应 v15"""
    principal: float
    days: int
    daily_cost_rate: float
    opportunity_cost: float
    equivalent_cp_loss: float
    hint: str


class FactorDetail(BaseModel):
    """战力因子详情"""
    name: str
    weight: str
    raw_score: float
    contribution: float
    detail: str


class RiskDetail(BaseModel):
    """风险详情"""
    score: float
    level: str
    items: list
    adjustment: str


class CPExplanationResponse(BaseModel):
    """战力分解说明 v16"""
    code: str
    name: str
    total_cp: float
    factors: list
    risk: RiskDetail
    data_quality: str
    summary: str


class HoldingItem(BaseModel):
    """持仓项"""
    code: str
    name: str
    quantity: int
    cost_price: float


class HoldingsImportRequest(BaseModel):
    """持仓导入请求"""
    holdings: List[HoldingItem]


class HoldingsExportResponse(BaseModel):
    """持仓导出响应"""
    holdings: List[HoldingItem]
    total_count: int
    export_time: str


class UserProfile(BaseModel):
    """用户约束配置"""
    capital: float = 20000  # 资金量，默认2万
    allowed_boards: List[str] = ['main']  # 允许交易的板块（仅支持主板）
    risk_preference: str = 'aggressive'  # 风险偏好: conservative/balanced/aggressive
    consider_dividend: bool = True  # 是否考虑股息
    keep_cash_reserve: bool = False  # 是否预留现金
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserProfileResponse(BaseModel):
    """用户配置响应"""
    profile: UserProfile
    affordable_stocks_count: int = 0  # 当前可买股票数量
    filter_summary: str = ""  # 筛选条件说明


# ==================== 模拟交易相关模型 ====================

class AccountResponse(BaseModel):
    """账户摘要"""
    cash: float  # 可用资金
    initial_cash: float  # 初始资金
    total_market_value: float = 0  # 持仓总市值
    total_assets: float = 0  # 总资产 = 现金 + 市值
    total_profit: float = 0  # 总盈亏
    profit_rate: float = 0  # 盈亏比例


class HoldingDetail(BaseModel):
    """持仓明细（含实时价格和盈亏）"""
    code: str
    name: str
    quantity: int  # 持股数量
    cost_price: float  # 成本价
    current_price: float = 0  # 当前价
    market_value: float = 0  # 市值
    profit: float = 0  # 盈亏金额
    profit_rate: float = 0  # 盈亏比例
    bought_at: str = ""  # 最新买入时间
    can_sell: int = 0  # 可卖出数量（不含今日买入）
    on_cooldown: bool = False  # 是否在交易冷却期内
    cooldown_days_remaining: int = 0  # 冷却期剩余天数


class PortfolioResponse(BaseModel):
    """持仓明细响应"""
    holdings: List[HoldingDetail]
    total_market_value: float
    total_profit: float
    cash: float
    total_assets: float


class TradeRequest(BaseModel):
    """交易请求"""
    code: str
    quantity: int  # 买卖数量，必须是100的倍数


class TradeCostBreakdown(BaseModel):
    """交易成本明细"""
    commission: float  # 佣金
    stamp_tax: float  # 印花税（仅卖出）
    transfer_fee: float  # 过户费
    total_cost: float  # 总成本


class TradeResponse(BaseModel):
    """交易响应"""
    success: bool
    action: str  # buy/sell
    code: str
    name: str
    quantity: int
    price: float
    total_amount: float  # 成交金额
    cost_detail: TradeCostBreakdown
    cash_after: float  # 交易后现金
    message: str = ""


class TradeHistoryItem(BaseModel):
    """交易历史项"""
    id: int
    code: str
    name: str
    action: str  # buy/sell
    quantity: int
    price: float
    commission: float
    stamp_tax: float
    transfer_fee: float
    total_amount: float
    recorded_at: str


class TradeHistoryResponse(BaseModel):
    """交易历史响应"""
    trades: List[TradeHistoryItem]
    total_count: int


# ==================== 预测引擎Schema ====================

class GainPredictionItem(BaseModel):
    """涨幅预测项"""
    code: str
    name: str
    predicted_gain_3d: float  # 预测3日涨幅%
    predicted_gain_5d: float  # 预测5日涨幅%
    confidence: float  # 置信度 0-1
    confidence_interval_3d: tuple  # 3日置信区间 (min, max)
    confidence_interval_5d: tuple  # 5日置信区间 (min, max)
    features: Dict[str, float]  # 主要特征值
    model_version: str = "rule_v19.8"


class GainPredictionResponse(BaseModel):
    """涨幅预测响应"""
    predictions: List[GainPredictionItem]
    calculated_at: str
    data_timestamp: str
    stock_count: int
    distribution: Dict[str, float]  # 预测分布统计
    avg_confidence: float


class ProbabilityPredictionItem(BaseModel):
    """上涨概率预测项"""
    code: str
    name: str
    up_probability_3d: float  # 3日上涨概率 0-1
    up_probability_5d: float  # 5日上涨概率 0-1
    confidence: float  # 置信度 0-1
    risk_level: str  # high/medium/low
    features: Dict[str, float]  # 主要特征值
    model_version: str = "rule_v19.8"


class ProbabilityPredictionResponse(BaseModel):
    """上涨概率预测响应"""
    predictions: List[ProbabilityPredictionItem]
    calculated_at: str
    data_timestamp: str
    stock_count: int
