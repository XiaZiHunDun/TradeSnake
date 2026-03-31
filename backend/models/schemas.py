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
    total_cp: float
    risk_score: float = 0
    risk_level: str = '较低'
    # 扩展字段
    pb: float = 0  # 市净率
    gross_margin: float = 0  # 毛利率
    revenue: float = 0  # 主营收入(亿)
    cashflow: float = 0  # 经营现金流(亿)
    debt_ratio: float = 0  # 资产负债率


class CPListResponse(BaseModel):
    """战力榜单响应"""
    total: int
    data: List[StockCPData]
    updated_at: str


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
    total_cp: float
    risk_score: float = 0
    risk_level: str = '较低'
    # 扩展字段
    pb: float = 0  # 市净率
    gross_margin: float = 0  # 毛利率
    revenue: float = 0  # 主营收入(亿)
    cashflow: float = 0  # 经营现金流(亿)
    debt_ratio: float = 0  # 资产负债率


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
