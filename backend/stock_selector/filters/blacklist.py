"""
黑名单过滤器

基于硬性排除规则过滤股票：
- ST/*ST/SST 股票
- 退市整理期股票
- 次新股（上市不足60个交易日）
- 僵尸股（连续20日成交额<500万）
- 长期停牌（停牌超过30个交易日）

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from typing import List, Tuple, Dict, Any

from ..enums import PoolTier
from ..types import StockInfo
from .. import config

logger = logging.getLogger(__name__)


class BlacklistFilter:
    """黑名单过滤器"""

    def __init__(self):
        self._exclude_st = config.EXCLUDE_CONFIG.get("exclude_st", True)
        self._new_stock_days = config.EXCLUDE_CONFIG.get("new_stock_days", 60)
        self._zombie_volume_threshold = config.EXCLUDE_CONFIG.get("zombie_volume_threshold", 500)
        self._zombie_days = config.EXCLUDE_CONFIG.get("zombie_days", 20)
        self._suspended_days = config.EXCLUDE_CONFIG.get("suspended_days", 30)

    def filter(self, stocks: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        过滤黑名单股票

        Args:
            stocks: 股票列表 [{
                code: str,
                name: str,
                is_st: bool,
                listing_days: int,
                volume_below_threshold_days: int,  # 连续低于门槛的天数
                suspended_days: int,  # 停牌天数
                ...
            }]

        Returns:
            (passed_stocks, excluded_stocks)
            - passed_stocks: 通过过滤的股票
            - excluded_stocks: 被排除的股票（含排除原因）
        """
        passed = []
        excluded = []

        for stock in stocks:
            code = stock.get("code", "")
            name = stock.get("name", "")
            reason = self._check_exclusion(stock)

            if reason:
                excluded.append({
                    **stock,
                    "exclude_reason": reason,
                })
                logger.debug(f"股票 {code} ({name}) 被排除: {reason}")
            else:
                passed.append(stock)

        if excluded:
            logger.info(f"黑名单过滤：排除 {len(excluded)} 只股票，剩余 {len(passed)} 只")

        return passed, excluded

    def _check_exclusion(self, stock: Dict) -> str:
        """检查排除原因，返回空字符串表示通过"""
        code = stock.get("code", "")
        name = stock.get("name", "")

        # 1. ST股票
        if self._exclude_st and stock.get("is_st", False):
            return f"ST/*ST/SST股票"

        # 2. 次新股（上市不足60个交易日）
        listing_days = stock.get("listing_days", 0)
        if listing_days < self._new_stock_days:
            return f"次新股（上市{listing_days}日<{self._new_stock_days}日门槛）"

        # 3. 僵尸股（连续成交额低迷）
        volume_below_days = stock.get("volume_below_threshold_days", 0)
        if volume_below_days >= self._zombie_days:
            return f"僵尸股（连续{volume_below_days}日成交额<{self._zombie_volume_threshold}万）"

        # 4. 长期停牌
        suspended_days = stock.get("suspended_days", 0)
        if suspended_days >= self._suspended_days:
            return f"长期停牌（停牌{suspended_days}日>{self._suspended_days}日）"

        return ""  # 通过

    def check_single(self, stock: Dict) -> Tuple[bool, str]:
        """
        检查单只股票

        Returns:
            (is_excluded, reason)
        """
        reason = self._check_exclusion(stock)
        return (len(reason) > 0, reason)

    def get_exclude_stats(self, stocks: List[Dict]) -> Dict[str, int]:
        """
        获取排除统计

        Returns:
            {
                "st_count": ST股票数量,
                "new_stock_count": 次新股数量,
                "zombie_count": 僵尸股数量,
                "suspended_count": 停牌股数量,
                "total_excluded": 总排除数量,
            }
        """
        stats = {
            "st_count": 0,
            "new_stock_count": 0,
            "zombie_count": 0,
            "suspended_count": 0,
            "total_excluded": 0,
        }

        for stock in stocks:
            reason = self._check_exclusion(stock)
            if not reason:
                continue

            stats["total_excluded"] += 1
            if "ST" in reason:
                stats["st_count"] += 1
            elif "次新股" in reason:
                stats["new_stock_count"] += 1
            elif "僵尸股" in reason:
                stats["zombie_count"] += 1
            elif "停牌" in reason:
                stats["suspended_count"] += 1

        return stats
