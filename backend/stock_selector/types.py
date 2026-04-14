"""
类型定义
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

from .enums import PoolTier, EventType, FinancialWarningLevel


@dataclass
class StockInfo:
    """股票基础信息"""
    code: str              # 股票代码（6位数字）
    name: str              # 股票名称
    tier: PoolTier         # 当前所在池
    tier_entry_date: date  # 入池日期
    tier_reason: str       # 入池原因

    # 市值和流动性
    market_cap: float = 0          # 流通市值（万元）
    daily_volume_20d: float = 0     # 近20日日均成交额（万元）
    turnover_rate: float = 0        # 换手率（%）

    # 战力分数（由 engine 模块计算后回填，用于再平衡排序）
    cp_score: float = 0            # 战力分数

    # 基本面
    is_st: bool = False             # 是否ST
    listing_days: int = 0           # 上市天数
    in_hs300: bool = False         # 是否沪深300成分
    in_zz500: bool = False         # 是否中证500成分
    in_zz1000: bool = False        # 是否中证1000成分

    # 财务预警
    financial_warning: FinancialWarningLevel = FinancialWarningLevel.NONE
    warning_start_date: Optional[date] = None

    # 白名单/黑名单
    is_whitelisted: bool = False
    is_blacklisted: bool = False
    whitelist_expire_date: Optional[date] = None

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def is_blacklisted_stock(self) -> bool:
        """是否是黑名单股票"""
        return self.is_blacklisted

    def is_expired_whitelist(self) -> bool:
        """白名单是否过期"""
        if not self.is_whitelisted:
            return False
        if self.whitelist_expire_date is None:
            return True
        return date.today() > self.whitelist_expire_date


@dataclass
class TempStockInfo:
    """临时池股票信息"""
    code: str
    name: str
    event_type: EventType
    trigger_reason: str
    trigger_time: datetime
    expire_time: datetime  # 7天后过期
    result: Optional[str] = None  # 处理结果：keep/remove

    def is_expired(self) -> bool:
        """是否已过期"""
        return datetime.now() > self.expire_time


@dataclass
class StockSnapshot:
    """股票快照（用于计算）"""
    code: str
    name: str
    tier: PoolTier

    # 市场数据
    price: float = 0
    change_pct: float = 0
    volume: float = 0
    turnover_rate: float = 0

    # 战力相关
    cp_score: float = 0
    cp_rank: int = 0

    # 时间戳
    snapshot_time: datetime = field(default_factory=datetime.now)


@dataclass
class PoolChange:
    """股票池变更记录"""
    code: str
    action: str  # add/remove/upgrade/downgrade/evict
    from_tier: Optional[PoolTier]
    to_tier: Optional[PoolTier]
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EvictionCandidate:
    """挤出候选"""
    code: str
    tier: PoolTier
    reason: str
    priority: int  # 越大约先被挤出

    def __lt__(self, other):
        return self.priority > other.priority  # 优先级高的先被挤出
