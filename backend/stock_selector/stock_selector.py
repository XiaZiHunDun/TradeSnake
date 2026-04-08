"""
股票筛选器 - 主入口类

整合所有组件，提供统一的股票筛选接口。

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple, Any, Protocol, Callable

from .enums import PoolTier, EventType
from .pool_manager import PoolManager
from .rebalancer import Rebalancer
from .event_trigger import EventTrigger, TriggerEvent
from .financial_watcher import FinancialWatcher, FinancialWarning
from .types import StockInfo, StockSnapshot
from . import config

logger = logging.getLogger(__name__)


class SelectorCallback(Protocol):
    """选择器回调协议"""

    def on_pool_changed(self, tier: PoolTier, added: List[str], removed: List[str]) -> None:
        """池变更回调"""
        ...

    def on_stock_upgraded(self, code: str, from_tier: PoolTier, to_tier: PoolTier) -> None:
        """晋级回调"""
        ...

    def on_stock_downgraded(self, code: str, from_tier: PoolTier, to_tier: PoolTier) -> None:
        """降级回调"""
        ...

    def on_event_triggered(self, code: str, event: TriggerEvent) -> None:
        """事件触发回调"""
        ...

    def on_financial_warning(self, code: str, warnings: List[FinancialWarning]) -> None:
        """财务预警回调"""
        ...


class StockSelector:
    """
    股票筛选器主类

    整合 PoolManager, Rebalancer, EventTrigger, FinancialWatcher
    提供统一的股票筛选和池管理接口
    """

    def __init__(self):
        # 核心组件
        self._pm = PoolManager()
        self._rebalancer = Rebalancer(self._pm)
        self._event_trigger = EventTrigger(self._pm)
        self._financial_watcher = FinancialWatcher(self._pm)

        # 回调
        self._callbacks: List[SelectorCallback] = []

        # 初始化状态
        self._initialized = False

        logger.info("StockSelector 初始化完成")

    # -------------------- 初始化 --------------------

    def initialize(self, stock_list: List[Dict], market_data: Dict, financial_data: Dict) -> None:
        """
        初始化股票池

        Args:
            stock_list: 股票基础信息列表 [{
                code: str,
                name: str,
                is_st: bool,
                listing_days: int,
                in_hs300: bool,
                in_zz500: bool,
                in_zz1000: bool,
            }]
            market_data: 市场数据 {code: {daily_volume_20d, turnover_rate, ...}}
            financial_data: 财务数据 {code: {...}}
        """
        logger.info(f"开始初始化股票池，共 {len(stock_list)} 只股票")

        # 分类处理
        core_stocks = []
        active_stocks = []
        observe_stocks = []

        for stock in stock_list:
            code = stock["code"]
            info = self._create_stock_info(stock, market_data.get(code, {}), financial_data.get(code, {}))

            # 应用硬性排除
            if self._is_excluded(info, market_data.get(code, {})):
                logger.debug(f"股票 {code} 被硬性排除")
                continue

            # 判断初始池
            tier = self._classify_initial_tier(stock, market_data.get(code, {}))
            if tier == PoolTier.CORE:
                core_stocks.append((code, info))
            elif tier == PoolTier.ACTIVE:
                active_stocks.append((code, info))
            else:
                observe_stocks.append((code, info))

        # 加入各池（按优先级）
        # 1. 先加入核心池（沪深300、中证500优先）
        for code, info in core_stocks:
            self._pm.add_stock(code, PoolTier.CORE, info, self._get_initial_reason(stock, market_data.get(code, {})))

        # 2. 加入活跃池
        for code, info in active_stocks:
            self._pm.add_stock(code, PoolTier.ACTIVE, info, self._get_initial_reason(stock, market_data.get(code, {})))

        # 3. 加入观察池
        for code, info in observe_stocks:
            self._pm.add_stock(code, PoolTier.OBSERVE, info, self._get_initial_reason(stock, market_data.get(code, {})))

        self._initialized = True
        logger.info(f"股票池初始化完成: {self._pm.get_pool_stats()}")

    def _create_stock_info(self, stock: Dict, market: Dict, financial: Dict) -> StockInfo:
        """创建股票信息对象"""
        return StockInfo(
            code=stock["code"],
            name=stock.get("name", ""),
            tier=PoolTier.OBSERVE,  # 临时值，会在add时更新
            tier_entry_date=date.today(),
            tier_reason="",
            market_cap=market.get("market_cap", 0),
            daily_volume_20d=market.get("daily_volume_20d", 0),
            turnover_rate=market.get("turnover_rate", 0),
            is_st=stock.get("is_st", False),
            listing_days=stock.get("listing_days", 0),
            in_hs300=stock.get("in_hs300", False),
            in_zz500=stock.get("in_zz500", False),
            in_zz1000=stock.get("in_zz1000", False),
        )

    def _is_excluded(self, info: StockInfo, market: Dict) -> bool:
        """检查是否硬性排除"""
        exclude_config = config.EXCLUDE_CONFIG

        # ST股票排除
        if exclude_config["exclude_st"] and info.is_st:
            return True

        # 次新股排除
        if info.listing_days < exclude_config["new_stock_days"]:
            return True

        # 僵尸股排除
        zombie_days = exclude_config["zombie_days"]
        if market.get("volume_below_threshold_days", 0) >= zombie_days:
            return True

        return False

    def _classify_initial_tier(self, stock: Dict, market: Dict) -> PoolTier:
        """分类初始池"""
        # 沪深300或中证500成分 -> 核心池
        if stock.get("in_hs300") or stock.get("in_zz500"):
            return PoolTier.CORE

        # 中证1000成分 -> 活跃池
        if stock.get("in_zz1000"):
            return PoolTier.ACTIVE

        # 成交额前300 -> 核心池
        if market.get("volume_rank", 999) <= 300:
            return PoolTier.CORE

        # 成交额前500 -> 活跃池
        if market.get("volume_rank", 999) <= 500:
            return PoolTier.ACTIVE

        # 其他 -> 观察池
        return PoolTier.OBSERVE

    def _get_initial_reason(self, stock: Dict, market: Dict) -> str:
        """获取初始入池原因"""
        if stock.get("in_hs300"):
            return "沪深300成分"
        if stock.get("in_zz500"):
            return "中证500成分"
        if stock.get("in_zz1000"):
            return "中证1000成分"
        if market.get("volume_rank", 999) <= 300:
            return f"成交额排名 {market.get('volume_rank')}"
        if market.get("volume_rank", 999) <= 500:
            return f"成交额排名 {market.get('volume_rank')}"
        return "满足准入条件"

    # -------------------- 查询接口 --------------------

    def get_pool(self, tier: PoolTier) -> List[str]:
        """获取指定池的股票列表"""
        return self._pm.get_pool(tier)

    def get_all_analysable_codes(self) -> List[str]:
        """
        获取所有可分析的股票代码（核心池 + 活跃池）

        这是与 engine 模块对接的主要接口
        """
        return self._pm.get_pool(PoolTier.CORE) + self._pm.get_pool(PoolTier.ACTIVE)

    def get_stock_tier(self, code: str) -> Optional[PoolTier]:
        """获取股票所在池"""
        return self._pm.get_stock_tier(code)

    def should_include(self, code: str) -> Tuple[bool, str]:
        """
        检查股票是否应该被纳入分析范围

        Returns:
            (should_include, reason)
        """
        tier = self._pm.get_stock_tier(code)

        if tier is None:
            return False, "不在任何池中"

        if tier == PoolTier.TEMP:
            return True, "临时池（事件驱动分析）"

        if tier == PoolTier.CORE or tier == PoolTier.ACTIVE:
            return True, f"{tier.value}池"

        if tier == PoolTier.OBSERVE:
            return False, "观察池不自动分析"

        return False, "未知"

    # -------------------- 刷新和事件处理 --------------------

    def refresh_pools(self, market_data: Dict) -> Dict[str, Any]:
        """
        盘后批处理：重新评估池状态

        Args:
            market_data: 市场数据 {code: {...}}

        Returns:
            处理结果统计
        """
        logger.info("开始盘后池刷新")

        # 1. 评估晋级/降级
        eval_results = self._rebalancer.evaluate_all(market_data)

        # 2. 执行再平衡
        rebalance_results = self._rebalancer.execute_rebalance(
            upgrade_codes=eval_results.get("upgrade", []),
            downgrade_codes=eval_results.get("downgrade", []),
            evict_codes=eval_results.get("evict", []),
        )

        # 3. 清理临时池过期股票
        expired_temp = self._pm.cleanup_expired_temp()

        stats = {
            "upgrades": len([r for r in rebalance_results.values() if r]),
            "downgrades": len([r for r in rebalance_results.values() if not r]),
            "evicted": len(eval_results.get("evict", [])),
            "expired_temp": len(expired_temp),
        }

        logger.info(f"盘后池刷新完成: {stats}")
        return stats

    def on_market_data_update(self, code: str, name: str, market_data: Dict) -> Optional[TriggerEvent]:
        """
        市场数据更新时调用（盘中）

        检查是否触发事件
        """
        event = self._event_trigger.check_event(code, name, market_data)
        if event:
            self._event_trigger.handle_event(event)

            # 触发回调
            for callback in self._callbacks:
                try:
                    callback.on_event_triggered(code, event)
                except Exception as e:
                    logger.error(f"事件回调失败: {e}")

        return event

    def on_financial_data_update(self, code: str, name: str, financial_data: Dict) -> List[FinancialWarning]:
        """
        财务数据更新时调用

        检查财务预警
        """
        warnings = self._financial_watcher.check_warning(code, name, financial_data)

        if warnings:
            # 检查是否需要降级
            tier = self._pm.get_stock_tier(code)
            if tier:
                should_downgrade, reason = self._financial_watcher.should_downgrade(code, tier, financial_data)
                if should_downgrade:
                    if tier != PoolTier.OBSERVE:
                        tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]
                        current_idx = tier_order.index(tier)
                        lower_tier = tier_order[current_idx - 1]
                        self._pm.downgrade(code, lower_tier, f"财务预警: {reason}")

            # 触发回调
            for callback in self._callbacks:
                try:
                    callback.on_financial_warning(code, warnings)
                except Exception as e:
                    logger.error(f"财务预警回调失败: {e}")

        return warnings

    # -------------------- 白名单/黑名单 --------------------

    def add_whitelist(self, code: str, expire_days: int = 30) -> None:
        """添加白名单"""
        self._pm.add_whitelist(code, expire_days)

    def add_blacklist(self, code: str) -> None:
        """添加黑名单"""
        self._pm.add_blacklist(code)

    def remove_from_whitelist(self, code: str) -> None:
        """移除白名单"""
        self._pm.remove_from_whitelist(code)

    def remove_from_blacklist(self, code: str) -> None:
        """移除黑名单"""
        self._pm.remove_from_blacklist(code)

    # -------------------- 回调注册 --------------------

    def register_callback(self, callback: SelectorCallback) -> None:
        """注册回调"""
        self._callbacks.append(callback)

    # -------------------- 状态查询 --------------------

    def get_pool_stats(self) -> Dict[str, int]:
        """获取各池统计"""
        return self._pm.get_pool_stats()

    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    def get_change_history(self, limit: int = 100):
        """获取变更历史"""
        return self._pm.get_change_history(limit)
