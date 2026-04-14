"""
股票池管理器 - 核心组件

负责：
1. 维护四层股票池（Core/Active/Observe/Temp）
2. 处理股票的晋级、降级、挤出
3. 管理白名单/黑名单
4. 记录池变更历史

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

from .enums import PoolTier, EventType, FinancialWarningLevel
from .types import StockInfo, TempStockInfo, PoolChange
from . import config

logger = logging.getLogger(__name__)


class PoolManager:
    """股票池管理器"""

    def __init__(self):
        # 各池股票集合
        self._pools: Dict[PoolTier, Dict[str, StockInfo]] = {
            PoolTier.CORE: {},
            PoolTier.ACTIVE: {},
            PoolTier.OBSERVE: {},
            PoolTier.TEMP: {},
        }

        # 临时池信息
        self._temp_stocks: Dict[str, TempStockInfo] = {}

        # 白名单
        self._whitelist: Set[str] = set()

        # 黑名单
        self._blacklist: Set[str] = set()

        # 变更历史
        self._change_history: List[PoolChange] = []

        # 代码到池的映射
        self._code_to_tier: Dict[str, PoolTier] = {}

        # 降级观察期记录
        self._probation_records: Dict[str, date] = {}

    # -------------------- 基础查询 --------------------

    def get_pool(self, tier: PoolTier) -> List[str]:
        """获取指定池的所有股票代码"""
        return list(self._pools[tier].keys())

    def get_all_pools(self) -> Dict[PoolTier, List[str]]:
        """获取所有池"""
        return {tier: list(stocks.keys()) for tier, stocks in self._pools.items()}

    def get_stock_tier(self, code: str) -> Optional[PoolTier]:
        """获取股票所在池"""
        return self._code_to_tier.get(code)

    def get_stock_info(self, code: str, tier: PoolTier) -> Optional[StockInfo]:
        """获取股票详细信息"""
        return self._pools[tier].get(code)

    def get_pool_size(self, tier: PoolTier) -> int:
        """获取指定池的大小"""
        return len(self._pools[tier])

    def is_blacklisted(self, code: str) -> bool:
        """检查是否在黑名单"""
        return code in self._blacklist

    def is_whitelisted(self, code: str) -> bool:
        """检查是否在白名单"""
        return code in self._whitelist

    # -------------------- 变更操作 --------------------

    def add_stock(self, code: str, tier: PoolTier, info: StockInfo, reason: str = "") -> bool:
        """
        添加股票到指定池

        Args:
            code: 股票代码
            tier: 目标池
            info: 股票信息
            reason: 添加原因

        Returns:
            是否添加成功
        """
        # 检查黑名单
        if self.is_blacklisted(code):
            logger.debug(f"股票 {code} 在黑名单中，拒绝添加")
            return False

        # 检查是否已在池中
        if code in self._code_to_tier:
            current_tier = self._code_to_tier[code]
            if current_tier == tier:
                logger.debug(f"股票 {code} 已在 {tier.value} 池中")
                return False
            # 已在其他池，先移除
            self._remove_from_pool(code, current_tier)

        # 检查池容量（容量满时执行挤出机制）
        if tier != PoolTier.TEMP:
            max_size = config.POOL_SIZE_CONFIG.get(tier.value, {}).get("max_size", float("inf"))
            if len(self._pools[tier]) >= max_size:
                # 尝试挤出最差股票
                evicted = self.evict_worst(tier, f"容量满，为 {code} 腾出位置")
                if evicted is None:
                    logger.warning(f"{tier.value} 池已满 ({max_size})，无法挤出更多股票")
                    return False

        # 添加到池
        info.tier = tier
        info.tier_entry_date = date.today()
        info.tier_reason = reason
        info.updated_at = datetime.now()

        self._pools[tier][code] = info
        self._code_to_tier[code] = tier

        # 记录变更
        self._record_change(code, "add", None, tier, reason)

        logger.info(f"股票 {code} ({info.name}) 加入 {tier.value} 池: {reason}")
        return True

    def remove_stock(self, code: str, tier: Optional[PoolTier] = None, reason: str = "") -> bool:
        """
        从池中移除股票

        Args:
            code: 股票代码
            tier: 指定池，如果为None则在所有池中查找
            reason: 移除原因

        Returns:
            是否移除成功
        """
        if tier is None:
            tier = self._code_to_tier.get(code)

        if tier is None:
            logger.debug(f"股票 {code} 不在任何池中")
            return False

        return self._remove_from_pool(code, tier, reason)

    def _remove_from_pool(self, code: str, tier: PoolTier, reason: str = "") -> bool:
        """内部方法：从指定池移除"""
        if code not in self._pools[tier]:
            return False

        del self._pools[tier][code]
        del self._code_to_tier[code]

        # 清理观察期记录
        self._probation_records.pop(code, None)

        # 记录变更
        self._record_change(code, "remove", tier, None, reason)

        logger.info(f"股票 {code} 从 {tier.value} 池移除: {reason}")
        return True

    def upgrade(self, code: str, target_tier: PoolTier, reason: str = "") -> bool:
        """
        晋级股票到更高层池

        Args:
            code: 股票代码
            target_tier: 目标池
            reason: 晋级原因

        Returns:
            是否晋级成功
        """
        current_tier = self._code_to_tier.get(code)
        if current_tier is None:
            logger.warning(f"股票 {code} 不在任何池中，无法晋级")
            return False

        # 检查晋级顺序
        tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]
        if target_tier not in tier_order:
            logger.warning(f"{target_tier.value} 不是有效的晋级目标")
            return False

        current_idx = tier_order.index(current_tier) if current_tier in tier_order else -1
        target_idx = tier_order.index(target_tier)

        if current_idx >= target_idx:
            logger.warning(f"股票 {code} 无法从 {current_tier.value} 晋级到 {target_tier.value}")
            return False

        # 获取股票信息
        info = self._pools[current_tier].get(code)
        if info is None:
            return False

        # 从当前池移除
        self._remove_from_pool(code, current_tier, f"晋级到 {target_tier.value}")

        # 添加到目标池
        self.add_stock(code, target_tier, info, reason or f"晋级: {current_tier.value} -> {target_tier.value}")

        # 记录变更
        self._record_change(code, "upgrade", current_tier, target_tier, reason)

        return True

    def downgrade(self, code: str, target_tier: PoolTier, reason: str = "") -> bool:
        """
        降级股票到更低层池

        Args:
            code: 股票代码
            target_tier: 目标池
            reason: 降级原因

        Returns:
            是否降级成功
        """
        current_tier = self._code_to_tier.get(code)
        if current_tier is None:
            logger.warning(f"股票 {code} 不在任何池中，无法降级")
            return False

        # 检查降级顺序
        tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]
        if target_tier not in tier_order:
            logger.warning(f"{target_tier.value} 不是有效的降级目标")
            return False

        current_idx = tier_order.index(current_tier) if current_tier in tier_order else -1
        target_idx = tier_order.index(target_tier)

        if current_idx <= target_idx:
            logger.warning(f"股票 {code} 无法从 {current_tier.value} 降级到 {target_tier.value}")
            return False

        # 获取股票信息
        info = self._pools[current_tier].get(code)
        if info is None:
            return False

        # 从当前池移除
        self._remove_from_pool(code, current_tier, f"降级到 {target_tier.value}")

        # 添加到目标池
        self.add_stock(code, target_tier, info, reason or f"降级: {current_tier.value} -> {target_tier.value}")

        # 记录变更
        self._record_change(code, "downgrade", current_tier, target_tier, reason)

        return True

    def evict_worst(self, tier: PoolTier, reason: str = "") -> Optional[str]:
        """
        挤出指定池中战力最差的股票

        Args:
            tier: 目标池
            reason: 挤出原因

        Returns:
            被挤出的股票代码，如果没有可挤出的股票返回None
        """
        if tier == PoolTier.TEMP:
            logger.warning("临时池不支持挤出机制")
            return None

        pool_stocks = self._pools[tier]
        if not pool_stocks:
            return None

        # 找到战力最低的股票
        worst_code = min(
            pool_stocks.keys(),
            key=lambda c: pool_stocks[c].cp_score if hasattr(pool_stocks[c], "cp_score") else 0
        )

        # 降级到下一层池
        tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]
        current_idx = tier_order.index(tier) if tier in tier_order else -1

        if current_idx > 0:
            lower_tier = tier_order[current_idx - 1]
            self.downgrade(worst_code, lower_tier, reason or f"池满挤出: {tier.value}")
        else:
            # 已是最底层，直接移除
            self.remove_stock(worst_code, tier, reason or "最底层池满挤出")

        return worst_code

    # -------------------- 临时池操作 --------------------

    def to_temp(self, code: str, event_type: EventType, name: str, reason: str = "") -> bool:
        """
        将股票移入临时池（事件驱动）

        Args:
            code: 股票代码
            event_type: 事件类型
            name: 股票名称
            reason: 触发原因

        Returns:
            是否成功
        """
        # 检查是否已在临时池
        if code in self._temp_stocks:
            # 更新事件
            self._temp_stocks[code].trigger_time = datetime.now()
            self._temp_stocks[code].trigger_reason = reason
            logger.debug(f"股票 {code} 临时池事件更新")
            return True

        # 检查容量
        max_size = config.POOL_SIZE_CONFIG["temp"]["max_size"]
        if len(self._temp_stocks) >= max_size:
            # 移除最旧的
            oldest = min(self._temp_stocks.values(), key=lambda x: x.trigger_time)
            self.remove_from_temp(oldest.code, "容量满，移除旧事件")

        # 添加到临时池
        temp_info = TempStockInfo(
            code=code,
            name=name,
            event_type=event_type,
            trigger_reason=reason,
            trigger_time=datetime.now(),
            expire_time=datetime.now() + timedelta(days=config.POOL_SIZE_CONFIG["temp"]["ttl_days"]),
            original_tier=current_tier if current_tier and current_tier != PoolTier.TEMP else PoolTier.OBSERVE,
        )

        self._temp_stocks[code] = temp_info

        # 从原池移除（如果在的话）
        current_tier = self._code_to_tier.get(code)
        if current_tier and current_tier != PoolTier.TEMP:
            self._remove_from_pool(code, current_tier, f"事件驱动进入临时池: {event_type.value}")

        # 添加到临时池记录
        self._pools[PoolTier.TEMP][code] = StockInfo(
            code=code,
            name=name,
            tier=PoolTier.TEMP,
            tier_entry_date=date.today(),
            tier_reason=f"事件: {reason}",
        )
        self._code_to_tier[code] = PoolTier.TEMP

        logger.info(f"股票 {code} 进入临时池: {event_type.value} - {reason}")
        return True

    def remove_from_temp(self, code: str, result: str = "") -> bool:
        """
        从临时池移除股票

        Args:
            code: 股票代码
            result: 处理结果

        Returns:
            是否成功
        """
        if code not in self._temp_stocks:
            return False

        temp_info = self._temp_stocks[code]
        temp_info.result = result

        # 记录临时池变更
        self._record_change(code, "remove", PoolTier.TEMP, None, f"临时池处理: {result}")

        del self._temp_stocks[code]
        self._remove_from_pool(code, PoolTier.TEMP, result)

        logger.info(f"股票 {code} 从临时池移除: {result}")
        return True

    def process_temp(self, code: str, result: str = "hold") -> bool:
        """
        处理临时池股票并回归原池或降级

        Args:
            code: 股票代码
            result: 处理结果
                - "hold": 回原池
                - "not_hold": 降一级
                - "timeout": 回观察池

        Returns:
            是否处理成功
        """
        if code not in self._temp_stocks:
            logger.warning(f"股票 {code} 不在临时池中")
            return False

        temp_info = self._temp_stocks[code]
        original_tier = temp_info.original_tier

        # 确定目标池
        tier_order = [PoolTier.OBSERVE, PoolTier.ACTIVE, PoolTier.CORE]
        result_handling = config.POOL_SIZE_CONFIG["temp"].get("result_handling", {})

        if result == "hold":
            # 回原池
            target_tier = original_tier
        elif result == "not_hold":
            # 降一级
            if original_tier in tier_order:
                current_idx = tier_order.index(original_tier)
                if current_idx > 0:
                    target_tier = tier_order[current_idx - 1]
                else:
                    target_tier = PoolTier.OBSERVE
            else:
                target_tier = PoolTier.OBSERVE
        elif result == "timeout":
            # 回观察池
            target_tier = PoolTier.OBSERVE
        else:
            logger.warning(f"未知处理结果: {result}，默认回观察池")
            target_tier = PoolTier.OBSERVE

        # 从临时池移除
        temp_info.result = result
        del self._temp_stocks[code]
        self._remove_from_pool(code, PoolTier.TEMP, f"临时池处理结果: {result}")

        # 获取股票信息（从历史或重建）
        stock_info = StockInfo(
            code=code,
            name=temp_info.name,
            tier=target_tier,
            tier_entry_date=date.today(),
            tier_reason=f"临时池{result}处理: {temp_info.event_type.value}",
        )

        # 添加到目标池
        success = self._pools[target_tier].get(code) is not None or self.add_stock(
            code, target_tier, stock_info, f"临时池回归: {result}"
        )

        logger.info(f"股票 {code} 临时池处理完成: {result} -> {target_tier.value}池")
        return success

    def cleanup_expired_temp(self) -> List[str]:
        """清理过期的临时池股票（回归观察池）"""
        expired = []
        for code, info in list(self._temp_stocks.items()):
            if info.is_expired():
                # TTL过期 -> 回观察池（而非简单移除）
                self.process_temp(code, "timeout")
                expired.append(code)

        if expired:
            logger.info(f"临时池清理完成，{len(expired)} 只过期股票回归观察池")
        return expired

    # -------------------- 白名单/黑名单 --------------------

    def add_whitelist(self, code: str, expire_days: Optional[int] = None) -> None:
        """添加到白名单"""
        expire_days = expire_days or config.WHITELIST_CONFIG["default_expire_days"]

        self._whitelist.add(code)

        # 更新股票信息中的白名单状态
        for tier, stocks in self._pools.items():
            if code in stocks:
                stocks[code].is_whitelisted = True
                stocks[code].whitelist_expire_date = date.today() + timedelta(days=expire_days)
                break

        logger.info(f"股票 {code} 添加到白名单，有效期 {expire_days} 天")

    def remove_from_whitelist(self, code: str) -> None:
        """从白名单移除"""
        self._whitelist.discard(code)

        # 更新股票信息
        for tier, stocks in self._pools.items():
            if code in stocks:
                stocks[code].is_whitelisted = False
                stocks[code].whitelist_expire_date = None
                break

        logger.info(f"股票 {code} 从白名单移除")

    def add_blacklist(self, code: str) -> None:
        """添加到黑名单"""
        self._blacklist.add(code)

        # 如果在池中，移除
        current_tier = self._code_to_tier.get(code)
        if current_tier:
            self._remove_from_pool(code, current_tier, "加入黑名单")

        logger.info(f"股票 {code} 添加到黑名单")

    def remove_from_blacklist(self, code: str) -> None:
        """从黑名单移除"""
        self._blacklist.discard(code)
        logger.info(f"股票 {code} 从黑名单移除")

    # -------------------- 观察期管理 --------------------

    def start_probation(self, code: str) -> None:
        """开始降级观察期"""
        self._probation_records[code] = date.today()
        logger.debug(f"股票 {code} 开始 {config.REBALANCE_CONFIG['probation_days']} 天观察期")

    def is_in_probation(self, code: str) -> bool:
        """检查是否在观察期"""
        if code not in self._probation_records:
            return False

        start_date = self._probation_records[code]
        probation_days = config.REBALANCE_CONFIG["probation_days"]
        return (date.today() - start_date).days < probation_days

    def check_probation_expired(self, code: str) -> bool:
        """检查观察期是否已过"""
        if code not in self._probation_records:
            return False

        start_date = self._probation_records[code]
        probation_days = config.REBALANCE_CONFIG["probation_days"]
        return (date.today() - start_date).days >= probation_days

    # -------------------- 历史记录 --------------------

    def _record_change(self, code: str, action: str, from_tier: Optional[PoolTier],
                      to_tier: Optional[PoolTier], reason: str) -> None:
        """记录池变更"""
        change = PoolChange(
            code=code,
            action=action,
            from_tier=from_tier,
            to_tier=to_tier,
            reason=reason,
            timestamp=datetime.now(),
        )
        self._change_history.append(change)

    def get_change_history(self, limit: int = 100) -> List[PoolChange]:
        """获取变更历史"""
        return self._change_history[-limit:]

    def get_pool_stats(self) -> Dict[str, int]:
        """获取各池统计"""
        return {tier.value: len(stocks) for tier, stocks in self._pools.items()}
