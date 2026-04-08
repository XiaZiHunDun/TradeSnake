"""
手动白名单/黑名单管理

功能：
- 白名单：用户手动添加的股票，即使不满足准入条件也优先进入分析范围
- 黑名单：用户手动排除的股票，即使其他条件满足也排除

特性：
- 白名单有过期机制
- 黑名单永不过期
- 支持批量操作

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Set, Optional, Tuple

from ..types import StockInfo
from .. import config

logger = logging.getLogger(__name__)


class ManualListFilter:
    """手动白名单/黑名单过滤器"""

    def __init__(self):
        # 白名单 {code: expire_date}
        self._whitelist: Dict[str, date] = {}

        # 黑名单（永不过期）
        self._blacklist: Set[str] = set()

        # 黑名单记录（用于审计）
        self._blacklist_history: List[Dict] = []

        # 白名单记录
        self._whitelist_history: List[Dict] = []

    # -------------------- 基础操作 --------------------

    def add_whitelist(self, code: str, expire_days: Optional[int] = None) -> bool:
        """
        添加到白名单

        Args:
            code: 股票代码
            expire_days: 过期天数，None表示使用默认值

        Returns:
            是否添加成功
        """
        if expire_days is None:
            expire_days = config.WHITELIST_CONFIG.get("default_expire_days", 30)

        expire_date = date.today() + timedelta(days=expire_days)
        self._whitelist[code] = expire_date

        self._record_whitelist_action(code, "add", expire_days)
        logger.info(f"股票 {code} 加入白名单，有效期 {expire_days} 天，至 {expire_date}")

        return True

    def remove_whitelist(self, code: str) -> bool:
        """
        从白名单移除

        Returns:
            是否成功移除
        """
        if code not in self._whitelist:
            return False

        expire_date = self._whitelist.pop(code)
        self._record_whitelist_action(code, "remove", None)
        logger.info(f"股票 {code} 从白名单移除（原来到期日：{expire_date}）")

        return True

    def add_blacklist(self, code: str, reason: str = "") -> bool:
        """
        添加到黑名单

        Args:
            code: 股票代码
            reason: 加入原因

        Returns:
            是否添加成功
        """
        if code in self._blacklist:
            return False

        self._blacklist.add(code)
        self._record_blacklist_action(code, "add", reason)
        logger.info(f"股票 {code} 加入黑名单: {reason}")

        return True

    def remove_blacklist(self, code: str) -> bool:
        """
        从黑名单移除

        Returns:
            是否成功移除
        """
        if code not in self._blacklist:
            return False

        self._blacklist.discard(code)
        self._record_blacklist_action(code, "remove", "")
        logger.info(f"股票 {code} 从黑名单移除")

        return True

    # -------------------- 查询操作 --------------------

    def is_whitelisted(self, code: str) -> bool:
        """检查是否在白名单且未过期"""
        if code not in self._whitelist:
            return False

        expire_date = self._whitelist[code]
        if date.today() > expire_date:
            # 已过期，清理
            del self._whitelist[code]
            return False

        return True

    def is_blacklisted(self, code: str) -> bool:
        """检查是否在黑名单"""
        return code in self._blacklist

    def get_whitelist(self) -> List[str]:
        """获取当前白名单（未过期的）"""
        result = []
        expired = []

        for code, expire_date in list(self._whitelist.items()):
            if date.today() > expire_date:
                expired.append(code)
            else:
                result.append(code)

        # 清理过期条目
        for code in expired:
            del self._whitelist[code]

        return result

    def get_blacklist(self) -> List[str]:
        """获取当前黑名单"""
        return list(self._blacklist)

    def get_expired_whitelist(self) -> List[str]:
        """获取已过期的白名单"""
        expired = []
        for code, expire_date in self._whitelist.items():
            if date.today() > expire_date:
                expired.append(code)
        return expired

    # -------------------- 过滤操作 --------------------

    def filter(self, stocks: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        过滤白名单/黑名单股票

        Args:
            stocks: 股票列表

        Returns:
            (passed_stocks, excluded_stocks)
        """
        passed = []
        excluded = []

        for stock in stocks:
            code = stock.get("code", "")

            # 黑名单直接排除
            if self.is_blacklisted(code):
                excluded.append({
                    **stock,
                    "exclude_reason": "黑名单",
                })
                continue

            # 检查白名单
            if self.is_whitelisted(code):
                # 白名单股票添加标记但不排除
                passed.append({
                    **stock,
                    "is_whitelisted": True,
                })
            else:
                passed.append(stock)

        return passed, excluded

    def is_allowed(self, code: str) -> Tuple[bool, str]:
        """
        检查股票是否允许通过

        Returns:
            (is_allowed, reason)
            - is_allowed: 是否允许
            - reason: 原因（拒绝时说明原因，允许时为空）
        """
        if self.is_blacklisted(code):
            return False, "黑名单"

        if self.is_whitelisted(code):
            return True, "白名单"

        return True, ""

    # -------------------- 历史记录 --------------------

    def _record_whitelist_action(self, code: str, action: str, expire_days: Optional[int]) -> None:
        """记录白名单操作"""
        self._whitelist_history.append({
            "code": code,
            "action": action,
            "expire_days": expire_days,
            "timestamp": datetime.now(),
        })

    def _record_blacklist_action(self, code: str, action: str, reason: str) -> None:
        """记录黑名单操作"""
        self._blacklist_history.append({
            "code": code,
            "action": action,
            "reason": reason,
            "timestamp": datetime.now(),
        })

    def get_whitelist_history(self, limit: int = 50) -> List[Dict]:
        """获取白名单操作历史"""
        return self._whitelist_history[-limit:]

    def get_blacklist_history(self, limit: int = 50) -> List[Dict]:
        """获取黑名单操作历史"""
        return self._blacklist_history[-limit:]

    # -------------------- 批量操作 --------------------

    def batch_add_whitelist(self, codes: List[str], expire_days: Optional[int] = None) -> Dict:
        """
        批量添加白名单

        Returns:
            {"success": [codes], "failed": [codes]}
        """
        success = []
        failed = []

        for code in codes:
            if self.add_whitelist(code, expire_days):
                success.append(code)
            else:
                failed.append(code)

        logger.info(f"批量添加白名单：成功 {len(success)}，失败 {len(failed)}")
        return {"success": success, "failed": failed}

    def batch_add_blacklist(self, codes: List[str], reason: str = "") -> Dict:
        """
        批量添加黑名单

        Returns:
            {"success": [codes], "failed": [codes]}
        """
        success = []
        failed = []

        for code in codes:
            if self.add_blacklist(code, reason):
                success.append(code)
            else:
                failed.append(code)

        logger.info(f"批量添加黑名单：成功 {len(success)}，失败 {len(failed)}")
        return {"success": success, "failed": failed}

    def clear_expired_whitelist(self) -> int:
        """
        清理过期白名单

        Returns:
            清理数量
        """
        expired = self.get_expired_whitelist()
        for code in expired:
            self.remove_whitelist(code)

        if expired:
            logger.info(f"清理 {len(expired)} 个过期白名单")

        return len(expired)
