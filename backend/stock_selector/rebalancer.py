"""
再平衡器 - 负责池的动态调整

职责：
1. 评估股票的晋级/降级条件
2. 执行池的再平衡操作
3. 触发挤出机制

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple, Any

from .enums import PoolTier
from .pool_manager import PoolManager
from .types import StockInfo
from . import config

logger = logging.getLogger(__name__)


class Rebalancer:
    """再平衡器"""

    def __init__(self, pool_manager: PoolManager):
        self._pm = pool_manager

        # 各池的晋级候选队列
        self._upgrade_candidates: Dict[PoolTier, List[Tuple[str, float]]] = {
            PoolTier.OBSERVE: [],   # (code, score)
            PoolTier.ACTIVE: [],    # (code, score)
        }

        # 降级风险列表
        self._downgrade_risks: Dict[str, Dict[str, Any]] = {}

    def evaluate_all(self, market_data: Dict[str, Dict]) -> Dict[str, List[str]]:
        """
        评估所有股票的晋级/降级

        Args:
            market_data: 市场数据 {code: {volume, price, change_pct, ...}}

        Returns:
            评估结果 {
                "upgrade": [code, ...],
                "downgrade": [code, ...],
                "evict": [code, ...],
            }
        """
        results = {
            "upgrade": [],
            "downgrade": [],
            "evict": [],
        }

        # 评估晋级
        for tier in [PoolTier.OBSERVE, PoolTier.ACTIVE]:
            candidates = self._evaluate_upgrades(tier, market_data)
            for code, reason in candidates:
                if self.should_upgrade(code, tier, market_data.get(code, {})):
                    results["upgrade"].append(code)

        # 评估降级
        for tier in [PoolTier.CORE, PoolTier.ACTIVE]:
            for code in self._pm.get_pool(tier):
                should_down, reason = self.should_downgrade(
                    code, tier, market_data.get(code, {})
                )
                if should_down:
                    results["downgrade"].append(code)
                    self._record_downgrade_risk(code, reason)

        # 评估挤出（当池满时）
        for tier in [PoolTier.CORE, PoolTier.ACTIVE, PoolTier.OBSERVE]:
            if self._pm.get_pool_size(tier) > config.POOL_SIZE_CONFIG.get(tier.value, {}).get("max_size", float("inf")):
                candidates = self._get_eviction_candidates(tier, market_data)
                if candidates:
                    results["evict"].extend(candidates[:1])  # 每次最多挤出一个

        return results

    def _evaluate_upgrades(self, tier: PoolTier, market_data: Dict) -> List[Tuple[str, str]]:
        """
        评估指定池的晋级候选

        Returns:
            [(code, reason), ...]
        """
        candidates = []
        tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]

        if tier not in tier_order or tier == PoolTier.CORE:
            return candidates

        current_idx = tier_order.index(tier)
        next_tier = tier_order[current_idx + 1]

        for code in self._pm.get_pool(tier):
            data = market_data.get(code, {})

            # 晋级条件检查
            upgrade_threshold = config.POOL_SIZE_CONFIG.get(next_tier.value, {}).get("upgrade_threshold", 100)

            # 检查成交额排名
            if data.get("volume_rank", 999) <= upgrade_threshold:
                candidates.append((code, f"成交额排名 {data.get('volume_rank')} 进入前 {upgrade_threshold}"))

            # 检查动量（连续N日上涨）
            momentum_days = config.REBALANCE_CONFIG["upgrade"]["momentum_streak_days"]
            if data.get("momentum_streak", 0) >= momentum_days:
                candidates.append((code, f"连续 {momentum_days} 日动量强势"))

            # 检查纳入指数成分
            if tier == PoolTier.ACTIVE and data.get("in_hs300") or data.get("in_zz500"):
                candidates.append((code, "纳入沪深300或中证500"))

        return candidates

    def should_upgrade(self, code: str, tier: PoolTier, data: Dict) -> Tuple[bool, str]:
        """
        判断股票是否应该晋级

        Returns:
            (should_upgrade, reason)
        """
        tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]
        if tier not in tier_order or tier == PoolTier.CORE:
            return False, ""

        current_idx = tier_order.index(tier)
        next_tier = tier_order[current_idx + 1]

        # 检查目标池容量
        next_tier_size = self._pm.get_pool_size(next_tier)
        next_tier_max = config.POOL_SIZE_CONFIG.get(next_tier.value, {}).get("max_size", float("inf"))
        if next_tier_size >= next_tier_max:
            return False, f"{next_tier.value} 池已满"

        # 获取股票信息
        info = self._pm.get_stock_info(code, tier)
        if info is None:
            return False, "股票信息不存在"

        # 晋级门槛
        min_volume = config.ADMISSION_CONFIG.get(next_tier.value, {}).get("min_daily_volume_20d", 0)
        if info.daily_volume_20d < min_volume:
            return False, f"成交额 {info.daily_volume_20d} 万 < {min_volume} 万门槛"

        # 指数成分加成
        if tier == PoolTier.ACTIVE and (info.in_hs300 or info.in_zz500):
            return True, "指数成分加成晋级"

        # 成交额排名加成
        volume_rank = data.get("volume_rank", 999)
        upgrade_threshold = config.POOL_SIZE_CONFIG.get(next_tier.value, {}).get("upgrade_threshold", 100)
        if volume_rank <= upgrade_threshold:
            return True, f"成交额排名 {volume_rank} 进入前 {upgrade_threshold}"

        return False, ""

    def should_downgrade(self, code: str, tier: PoolTier, data: Dict) -> Tuple[bool, str]:
        """
        判断股票是否应该降级

        Returns:
            (should_downgrade, reason)
        """
        tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]
        if tier not in tier_order or tier == PoolTier.OBSERVE:
            return False, ""

        # 获取股票信息
        info = self._pm.get_stock_info(code, tier)
        if info is None:
            return False, ""

        # 检查是否在白名单（白名单股票不降级）
        if info.is_whitelisted and not info.is_expired_whitelist():
            return False, "白名单保护"

        current_idx = tier_order.index(tier)
        lower_tier = tier_order[current_idx - 1]

        # 检查成交额是否持续低迷
        min_volume = config.ADMISSION_CONFIG.get(tier.value, {}).get("min_daily_volume_20d", 0)
        drop_threshold = min_volume * config.REBALANCE_CONFIG["downgrade"]["volume_drop_ratio"]
        drop_days = config.REBALANCE_CONFIG["downgrade"]["volume_drop_days"]

        if data.get("volume_below_threshold_days", 0) >= drop_days:
            return True, f"连续 {drop_days} 日成交额低于 {drop_threshold} 万"

        # 检查是否被ST
        if info.is_st:
            return True, "ST股票强制降级"

        return False, ""

    def _get_eviction_candidates(self, tier: PoolTier, market_data: Dict) -> List[str]:
        """
        获取挤出候选列表

        Returns:
            [code, ...] 按优先级排序
        """
        candidates = []
        pool_stocks = self._pm.get_pool(tier)

        for code in pool_stocks:
            data = market_data.get(code, {})
            info = self._pm.get_stock_info(code, tier)

            if info is None:
                continue

            # 优先级计算（战力越低越优先被挤出）
            priority = 0

            # 战力最低优先
            cp_score = getattr(info, "cp_score", 0)
            priority += (100 - cp_score) * 10 if cp_score else 50

            # 成交额低迷优先挤出
            if data.get("volume_below_threshold_days", 0) > 0:
                priority += data["volume_below_threshold_days"] * 5

            # 在池时间短优先挤出（新加入的容易被挤出）
            days_in_pool = (date.today() - info.tier_entry_date).days
            if days_in_pool < 10:
                priority += (10 - days_in_pool) * 2

            # 白名单股票不挤出
            if info.is_whitelisted and not info.is_expired_whitelist():
                continue

            candidates.append((code, priority))

        # 按优先级排序（高的先被挤出）
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [code for code, _ in candidates]

    def _record_downgrade_risk(self, code: str, reason: str) -> None:
        """记录降级风险"""
        if code not in self._downgrade_risks:
            self._downgrade_risks[code] = {
                "reasons": [],
                "first_detected": datetime.now(),
            }
        self._downgrade_risks[code]["reasons"].append(reason)

    def execute_rebalance(self, upgrade_codes: List[str], downgrade_codes: List[str],
                          evict_codes: List[str]) -> Dict[str, bool]:
        """
        执行再平衡

        Args:
            upgrade_codes: 晋级股票列表
            downgrade_codes: 降级股票列表
            evict_codes: 挤出股票列表

        Returns:
            执行结果 {code: success}
        """
        results = {}

        # 执行晋级
        for code in upgrade_codes:
            current_tier = self._pm.get_stock_tier(code)
            if current_tier is None:
                continue

            tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]
            current_idx = tier_order.index(current_tier) if current_tier in tier_order else -1

            if current_idx < len(tier_order) - 1:
                next_tier = tier_order[current_idx + 1]
                results[code] = self._pm.upgrade(code, next_tier, "再平衡晋级")

        # 执行降级
        for code in downgrade_codes:
            current_tier = self._pm.get_stock_tier(code)
            if current_tier is None:
                continue

            tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]
            current_idx = tier_order.index(current_tier) if current_tier in tier_order else -1

            if current_idx > 0:
                lower_tier = tier_order[current_idx - 1]
                results[code] = self._pm.downgrade(code, lower_tier, "再平衡降级")

        # 执行挤出
        for code in evict_codes:
            current_tier = self._pm.get_stock_tier(code)
            if current_tier is None:
                continue

            if current_tier != PoolTier.OBSERVE:
                tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]
                current_idx = tier_order.index(current_tier) if current_tier in tier_order else -1
                lower_tier = tier_order[current_idx - 1]
                results[code] = self._pm.downgrade(code, lower_tier, "池满挤出")
            else:
                results[code] = self._pm.remove_stock(code, PoolTier.OBSERVE, "池满挤出")

        return results
