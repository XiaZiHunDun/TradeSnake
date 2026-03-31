"""
数据模型 - TradeSnake Models
"""

from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime


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
