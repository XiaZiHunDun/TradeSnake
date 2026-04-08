"""
Stock Selector Module - 股票筛选模块

负责管理四层股票池：
- Core Pool (核心池): ~300只，沪深300 + 中证500 + 成交额Top300
- Active Pool (活跃池): ~500只，中证1000 + 换手率Top20%
- Observe Pool (观察池): ~1000只，满足准入条件的其他股票
- Temp Pool (临时池): 事件驱动，涨停/异动等

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

from .enums import PoolTier, EventType, FinancialWarningLevel
from .pool_manager import PoolManager
from .rebalancer import Rebalancer
from .event_trigger import EventTrigger
from .financial_watcher import FinancialWatcher
from .stock_selector import StockSelector, SelectorCallback
from .types import StockInfo, TempStockInfo, StockSnapshot
from .update_strategy import UpdateStrategyProvider

__all__ = [
    # 枚举类型
    "PoolTier",
    "EventType",
    "FinancialWarningLevel",
    # 核心组件
    "PoolManager",
    "Rebalancer",
    "EventTrigger",
    "FinancialWatcher",
    "StockSelector",
    # 策略组件
    "UpdateStrategyProvider",
    # 类型定义
    "SelectorCallback",
    "StockInfo",
    "TempStockInfo",
    "StockSnapshot",
]
