"""
股票池监控指标

功能：
- 计算各池的统计指标
- 监控池的健康状态
- 生成池报告

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from ..enums import PoolTier
from ..pool_manager import PoolManager

logger = logging.getLogger(__name__)


@dataclass
class PoolMetrics:
    """股票池指标"""
    tier: PoolTier
    size: int
    target_size: int
    utilization_rate: float  # 容量利用率
    avg_volume: float  # 平均成交额（万元）
    upgrade_rate: float  # 晋级率
    downgrade_rate: float  # 降级率
    event_rate: float  # 事件触发率
    whitelist_count: int  # 白名单数量
    blacklist_count: int  # 黑名单数量


@dataclass
class PoolHealthReport:
    """股票池健康报告"""
    date: date
    metrics: Dict[str, PoolMetrics]
    issues: List[str]  # 发现的问题
    recommendations: List[str]  # 建议


class PoolMetricsCollector:
    """
    股票池指标收集器
    """

    def __init__(self, pool_manager: PoolManager):
        self._pm = pool_manager

    def calculate_metrics(self, tier: PoolTier,
                         market_data: Optional[Dict] = None) -> PoolMetrics:
        """
        计算指定池的指标

        Args:
            tier: 池层级
            market_data: 市场数据 {code: {daily_volume_20d, ...}}

        Returns:
            PoolMetrics
        """
        pool_codes = self._pm.get_pool(tier)
        size = len(pool_codes)

        # 目标大小
        target_sizes = {PoolTier.CORE: 300, PoolTier.ACTIVE: 500, PoolTier.OBSERVE: 1000}
        target_size = target_sizes.get(tier, 1000)

        # 容量利用率
        utilization_rate = size / target_size if target_size > 0 else 0

        # 平均成交额
        avg_volume = 0
        if market_data:
            volumes = []
            for code in pool_codes:
                data = market_data.get(code, {})
                vol = data.get("daily_volume_20d", 0)
                if vol > 0:
                    volumes.append(vol)
            if volumes:
                avg_volume = sum(volumes) / len(volumes)

        # 晋级/降级率（从历史记录计算）
        upgrade_rate, downgrade_rate = self._calculate_rates(tier)

        # 白名单/黑名单数量
        whitelist_count = len([c for c in self._pm.get_pool(tier) if self._pm.is_whitelisted(c)])
        blacklist_count = len([c for c in self._pm.get_pool(tier) if self._pm.is_blacklisted(c)])

        return PoolMetrics(
            tier=tier,
            size=size,
            target_size=target_size,
            utilization_rate=utilization_rate,
            avg_volume=avg_volume,
            upgrade_rate=upgrade_rate,
            downgrade_rate=downgrade_rate,
            event_rate=0,  # 临时池专用
            whitelist_count=whitelist_count,
            blacklist_count=blacklist_count,
        )

    def _calculate_rates(self, tier: PoolTier) -> tuple:
        """
        计算晋级/降级率

        Returns:
            (upgrade_rate, downgrade_rate)
        """
        history = self._pm.get_change_history(limit=1000)

        tier_name = tier.value
        relevant_changes = [c for c in history if c.code in self._pm.get_pool(tier)]

        upgrades = len([c for c in relevant_changes if c.action == "upgrade"])
        downgrades = len([c for c in relevant_changes if c.action == "downgrade"])

        total = len(relevant_changes) if relevant_changes else 1

        return upgrades / total, downgrades / total

    def collect_all(self, market_data: Optional[Dict] = None) -> Dict[str, PoolMetrics]:
        """
        收集所有池的指标

        Returns:
            {tier_name: metrics}
        """
        return {
            tier.value: self.calculate_metrics(tier, market_data)
            for tier in PoolTier
        }

    def generate_report(self, market_data: Optional[Dict] = None) -> PoolHealthReport:
        """
        生成池健康报告

        Returns:
            PoolHealthReport
        """
        metrics = self.collect_all(market_data)
        issues = []
        recommendations = []

        for tier_name, m in metrics.items():
            # 检查容量问题
            if m.utilization_rate > 0.95:
                issues.append(f"{tier_name}池容量超过95%，建议触发再平衡")
                recommendations.append(f"{tier_name}池：考虑挤出低优先级股票或调整目标容量")
            elif m.utilization_rate < 0.5:
                issues.append(f"{tier_name}池容量低于50%，可能需要降低准入门槛")
                recommendations.append(f"{tier_name}池：考虑放宽准入条件或调整目标容量")

            # 检查黑名单过多
            if m.blacklist_count > m.size * 0.1:
                issues.append(f"{tier_name}池黑名单比例超过10%")

        return PoolHealthReport(
            date=date.today(),
            metrics=metrics,
            issues=issues,
            recommendations=recommendations,
        )


def calculate_pool_metrics(pool_manager: PoolManager,
                           tier: PoolTier,
                           market_data: Optional[Dict] = None) -> PoolMetrics:
    """
    计算股票池指标

    Args:
        pool_manager: 池管理器
        tier: 池层级
        market_data: 市场数据

    Returns:
        PoolMetrics
    """
    collector = PoolMetricsCollector(pool_manager)
    return collector.calculate_metrics(tier, market_data)
