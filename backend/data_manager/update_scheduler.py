"""
数据更新调度器

基于股票池分层的更新调度器：
- 订阅 stock_selector 的池状态变化
- 根据各池优先级调度 data_manager 的更新任务
- 盘中/盘后差异化更新策略

设计文档: docs/plans/DATA_MANAGER_ARCHITECTURE.md v18.2
"""

import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class UpdateScheduler:
    """
    基于股票池分层的更新调度器

    与 stock_selector 模块联动：
    - 使用 UpdateStrategyProvider 获取更新策略
    - 根据池层级确定更新频率
    - 盘中优先更新核心池，盘后批量处理
    """

    def __init__(self, data_manager, update_strategy_provider):
        """
        Args:
            data_manager: DataManager 实例
            update_strategy_provider: UpdateStrategyProvider 实例（来自 stock_selector）
        """
        self.dm = data_manager
        self.strategy = update_strategy_provider

        # 上次更新时间记录 {code: timestamp}
        self.last_update_time: Dict[str, float] = {}

        # 更新统计
        self.update_stats = {
            "total_updates": 0,
            "failed_updates": 0,
            "last_batch_time": None,
        }

    def trading_day_update(self, limit_per_batch: int = 50) -> Dict[str, Any]:
        """
        盘中按优先级更新（每次调用处理一批）

        Args:
            limit_per_batch: 每批处理数量限制

        Returns:
            更新结果统计
        """
        start_time = time.time()
        priority_codes = self.strategy.get_batch_priority()

        # 获取当前交易时段
        session = self.strategy.get_trading_session()
        market_status = "trading" if session in ("morning", "afternoon") else "closed"

        updated = []
        skipped = []
        failed = []

        count = 0

        for code in priority_codes:
            if count >= limit_per_batch:
                break

            # 获取该股票所在池和更新间隔
            tier = self._get_tier_for_code(code)
            if tier is None:
                continue

            interval = self.strategy.get_update_interval(tier, market_status)

            if interval <= 0:
                skipped.append(code)
                continue

            # 检查是否应该更新
            if self._should_update(code, interval):
                try:
                    self.dm.update_single_stock(code)
                    self.last_update_time[code] = time.time()
                    updated.append(code)
                    count += 1
                except Exception as e:
                    logger.error(f"更新股票 {code} 失败: {e}")
                    failed.append(code)

        # 更新统计
        self.update_stats["total_updates"] += len(updated)
        self.update_stats["failed_updates"] += len(failed)
        self.update_stats["last_batch_time"] = datetime.now()

        elapsed = time.time() - start_time

        return {
            "updated": len(updated),
            "skipped": len(skipped),
            "failed": len(failed),
            "elapsed_seconds": round(elapsed, 2),
            "session": session,
        }

    def after_market_update(self) -> Dict[str, Any]:
        """
        盘后批量更新

        Returns:
            更新结果统计
        """
        start_time = time.time()

        # 获取所有需要更新的股票
        plan = self.strategy.get_update_plan(market_status="closed")

        updated = []
        failed = []

        for tier_name, codes in plan.items():
            for code in codes:
                try:
                    self.dm.update_single_stock(code)
                    self.last_update_time[code] = time.time()
                    updated.append(code)
                except Exception as e:
                    logger.error(f"盘后更新股票 {code} 失败: {e}")
                    failed.append(code)

                # 每处理10个休息一下，避免请求过快
                if len(updated) % 10 == 0:
                    time.sleep(0.1)

        self.update_stats["total_updates"] += len(updated)
        self.update_stats["failed_updates"] += len(failed)
        self.update_stats["last_batch_time"] = datetime.now()

        elapsed = time.time() - start_time

        logger.info(f"盘后更新完成：成功 {len(updated)}，失败 {len(failed)}，耗时 {elapsed:.2f}秒")

        return {
            "updated": len(updated),
            "failed": len(failed),
            "elapsed_seconds": round(elapsed, 2),
        }

    def _should_update(self, code: str, interval: int) -> bool:
        """
        检查是否需要更新

        Args:
            code: 股票代码
            interval: 更新间隔（秒）

        Returns:
            是否应该更新
        """
        if interval <= 0:
            return False

        last = self.last_update_time.get(code, 0)
        elapsed = time.time() - last

        return elapsed >= interval

    def _get_tier_for_code(self, code: str):
        """
        获取股票所在池

        尝试从 stock_selector 获取，如果不可用则返回默认值
        """
        # 尝试从 strategy 获取
        if hasattr(self.strategy, "get_stock_tier"):
            return self.strategy.get_stock_tier(code)

        # 如果 strategy 是 UpdateStrategyProvider
        if hasattr(self.strategy, "get_codes_for_update"):
            for tier in ["core", "active", "observe"]:
                if code in self.strategy.get_codes_for_update(tier):
                    from ..stock_selector.enums import PoolTier
                    return PoolTier.CORE if tier == "core" else (
                        PoolTier.ACTIVE if tier == "active" else PoolTier.OBSERVE
                    )

        return None

    def force_update(self, code: str) -> bool:
        """
        强制更新单只股票

        Args:
            code: 股票代码

        Returns:
            是否成功
        """
        try:
            self.dm.update_single_stock(code)
            self.last_update_time[code] = time.time()
            self.update_stats["total_updates"] += 1
            return True
        except Exception as e:
            logger.error(f"强制更新股票 {code} 失败: {e}")
            self.update_stats["failed_updates"] += 1
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取更新统计"""
        return {
            **self.update_stats,
            "last_batch_time": self.update_stats["last_batch_time"].isoformat() if self.update_stats["last_batch_time"] else None,
        }

    def reset_stats(self) -> None:
        """重置统计"""
        self.update_stats = {
            "total_updates": 0,
            "failed_updates": 0,
            "last_batch_time": None,
        }


class StockSelectorCallback:
    """
    实现 stock_selector.SelectorCallback，将池变动映射到 UpdateScheduler。

    用法：
        scheduler = UpdateScheduler(dm, strategy_provider)
        selector.register_callback(StockSelectorCallback(scheduler))
    """

    def __init__(self, scheduler: UpdateScheduler):
        self.scheduler = scheduler

    def on_pool_changed(self, tier, added: List[str], removed: List[str]) -> None:
        for code in added:
            self.scheduler.last_update_time[code] = 0
        for code in removed:
            self.scheduler.last_update_time.pop(code, None)
        if added or removed:
            logger.info(
                "UpdateScheduler 池更新: tier=%s added=%s removed=%s",
                getattr(tier, "value", tier),
                added,
                removed,
            )

    def on_stock_upgraded(self, code: str, from_tier, to_tier) -> None:
        self.scheduler.last_update_time.pop(code, None)

    def on_stock_downgraded(self, code: str, from_tier, to_tier) -> None:
        pass

    def on_event_triggered(self, code: str, event) -> None:
        pass

    def on_financial_warning(self, code: str, warnings) -> None:
        pass

    def on_pool_update_strategy_changed(
        self, tier: "PoolTier", action: str, new_codes: List[str]
    ) -> None:
        """
        更新策略变化通知

        这是 UpdateStrategyProvider 主动推送的通知
        """
        logger.info(f"更新策略变化: {tier.value} - {action} - {new_codes}")
