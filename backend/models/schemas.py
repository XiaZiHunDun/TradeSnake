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


class CPListResponse(BaseModel):
    """战力榜单响应"""
    total: int
    data: List[StockCPData]
    updated_at: Optional[str] = None
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
