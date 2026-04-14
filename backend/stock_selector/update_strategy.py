"""
数据更新频率策略提供者

与 data_manager 模块联动，根据股票池层级提供差异化更新策略：

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3

核心接口（供 data_manager 调用）：
- get_update_interval(tier, market_status) -> int
- get_batch_priority() -> List[str]
- get_codes_for_update(tier) -> List[str]
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from .enums import PoolTier
from .pool_manager import PoolManager
from . import config

logger = logging.getLogger(__name__)


class UpdateStrategyProvider:
    """
    数据更新频率策略提供者

    负责：
    1. 根据池层级返回差异化更新间隔
    2. 提供批量更新优先级排序
    3. 标识需要更新的股票代码
    """

    # 交易时段定义
    TRADING_MORNING_START = "09:30"
    TRADING_MORNING_END = "11:30"
    TRADING_AFTERNOON_START = "13:00"
    TRADING_AFTERNOON_END = "15:00"

    def __init__(self, pool_manager: PoolManager):
        self._pm = pool_manager

        # 基础更新间隔配置（秒）
        self._base_intervals = {
            PoolTier.CORE: 300,       # 5分钟
            PoolTier.ACTIVE: 1800,    # 30分钟
            PoolTier.OBSERVE: 21600,  # 6小时
            PoolTier.TEMP: 60,        # 1分钟
        }

        # 盘中快照间隔（核心池额外）
        self._snapshot_interval = 300  # 5分钟

    def get_update_interval(self, tier: PoolTier, market_status: str = "trading") -> int:
        """
        获取指定池的更新间隔

        Args:
            tier: 股票池层级
            market_status: 市场状态 ("trading"=盘中, "closed"=盘后, "holiday"=节假日)

        Returns:
            更新间隔（秒）
        """
        base_interval = self._base_intervals.get(tier, 1800)

        # 盘中状态：核心池缩短间隔
        if market_status == "trading" and tier == PoolTier.CORE:
            return min(base_interval, self._snapshot_interval)

        # 盘后状态：所有池延长间隔
        if market_status == "closed":
            return base_interval * 2

        # 节假日：进一步延长
        if market_status == "holiday":
            return base_interval * 4

        return base_interval

    def get_batch_priority(self) -> List[str]:
        """
        获取批量更新优先级排序的股票代码

        Returns:
            按优先级排序的代码列表
            优先级：核心池 > 活跃池 > 观察池
        """
        priority_codes = []

        # 核心池优先
        priority_codes.extend(self._pm.get_pool(PoolTier.CORE))

        # 活跃池次之
        priority_codes.extend(self._pm.get_pool(PoolTier.ACTIVE))

        # 观察池最后
        priority_codes.extend(self._pm.get_pool(PoolTier.OBSERVE))

        return priority_codes

    def get_codes_for_update(self, tier: PoolTier, limit: Optional[int] = None) -> List[str]:
        """
        获取指定池需要更新的股票代码

        Args:
            tier: 股票池层级
            limit: 限制数量

        Returns:
            股票代码列表
        """
        codes = self._pm.get_pool(tier)
        if limit:
            codes = codes[:limit]
        return codes

    def get_stock_tier(self, code: str) -> Optional[PoolTier]:
        """
        获取股票所在池

        Args:
            code: 股票代码

        Returns:
            股票池层级，如果不存在则返回 None
        """
        return self._pm.get_stock_tier(code)

    def get_update_plan(self, market_status: str = "trading") -> Dict[str, List[str]]:
        """
        获取完整的更新计划

        Args:
            market_status: 市场状态

        Returns:
            {
                "core": [codes],
                "active": [codes],
                "observe": [codes],
                "temp": [codes],
            }
        """
        return {
            tier.value: self.get_codes_for_update(tier)
            for tier in PoolTier
        }

    def get_trading_session(self) -> str:
        """
        获取当前交易时段

        Returns:
            "morning" | "afternoon" | "closed" | "holiday"
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        # 简单判断（实际应结合日期）
        if current_time < self.TRADING_MORNING_START:
            return "pre_trading"
        elif self.TRADING_MORNING_START <= current_time <= self.TRADING_MORNING_END:
            return "morning"
        elif self.TRADING_AFTERNOON_START <= current_time <= self.TRADING_AFTERNOON_END:
            return "afternoon"
        else:
            return "closed"

    def should_update_now(self, tier: PoolTier, last_update_time: datetime) -> bool:
        """
        检查是否应该现在更新

        Args:
            tier: 股票池层级
            last_update_time: 上次更新时间

        Returns:
            是否应该更新
        """
        market_status = self.get_trading_session()
        if market_status == "closed":
            return False  # 盘后不更新

        interval = self.get_update_interval(tier, market_status)
        elapsed = (datetime.now() - last_update_time).total_seconds()

        return elapsed >= interval


class DataUpdateCoordinator:
    """
    数据更新协调器

    整合 stock_selector 的 UpdateStrategyProvider 与 data_manager 的更新调度
    """

    def __init__(self, pool_manager: PoolManager):
        self._strategy = UpdateStrategyProvider(pool_manager)

    def get_strategy(self) -> UpdateStrategyProvider:
        """获取策略提供者"""
        return self._strategy

    def build_update_schedule(self) -> Dict:
        """
        构建更新调度计划

        Returns:
            {
                "intervals": {tier: seconds},
                "priorities": [codes],
                "trading_session": str,
            }
        """
        session = self._strategy.get_trading_session()

        # 确定市场状态
        if session == "closed":
            market_status = "closed"
        elif session in ("morning", "afternoon"):
            market_status = "trading"
        else:
            market_status = "holiday"

        return {
            "intervals": {
                tier.value: self._strategy.get_update_interval(tier, market_status)
                for tier in PoolTier
            },
            "priorities": self._strategy.get_batch_priority(),
            "trading_session": session,
            "market_status": market_status,
        }
