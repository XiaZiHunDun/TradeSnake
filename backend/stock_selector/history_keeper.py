"""
历史保留机制

功能：
- 对曾经进入核心池的股票永久保留摘要信息
- 记录股票的池变更历史
- 提供历史战力快照查询

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .enums import PoolTier
from .pool_manager import PoolManager

logger = logging.getLogger(__name__)


@dataclass
class StockHistorySummary:
    """股票历史摘要"""
    code: str
    name: str

    # 入池历史
    first_core_entry: Optional[date] = None  # 首次进入核心池日期
    total_core_days: int = 0  # 核心池总天数
    core_upgrades: int = 0  # 晋级次数
    core_downgrades: int = 0  # 降级次数

    # 最后状态
    last_seen_date: Optional[date] = None
    last_tier: Optional[PoolTier] = None
    last_reason: str = ""

    # 战力数据（如果可用）
    last_cp_score: float = 0
    last_cp_rank: int = 0

    # 更新时间
    updated_at: datetime = field(default_factory=datetime.now)


class HistoryKeeper:
    """
    历史保留器

    设计原则：
    - 核心池股票永久保留历史记录
    - 观察池股票在离开后保留一段时间（如30天）后清理
    - 所有记录永久保存到磁盘
    """

    def __init__(self, pool_manager: PoolManager):
        self._pm = pool_manager

        # 历史摘要缓存 {code: StockHistorySummary}
        self._history_cache: Dict[str, StockHistorySummary] = {}

        # 池变更历史记录（内存）
        self._pool_changes: List[Dict] = []

        # 持久化路径（可选）
        self._persist_path: Optional[str] = None

    def set_persist_path(self, path: str) -> None:
        """设置持久化路径"""
        self._persist_path = path

    def record_pool_change(self, code: str, name: str, from_tier: Optional[PoolTier],
                          to_tier: Optional[PoolTier], reason: str) -> None:
        """
        记录池变更

        Args:
            code: 股票代码
            name: 股票名称
            from_tier: 原池
            to_tier: 新池
            reason: 变更原因
        """
        change_record = {
            "code": code,
            "name": name,
            "from_tier": from_tier.value if from_tier else None,
            "to_tier": to_tier.value if to_tier else None,
            "reason": reason,
            "timestamp": datetime.now(),
        }

        self._pool_changes.append(change_record)

        # 更新历史摘要
        self._update_history_summary(code, name, from_tier, to_tier, reason)

        logger.debug(f"记录池变更: {code} {from_tier} -> {to_tier}")

    def _update_history_summary(self, code: str, name: str,
                               from_tier: Optional[PoolTier],
                               to_tier: Optional[PoolTier],
                               reason: str) -> None:
        """更新历史摘要"""
        if code not in self._history_cache:
            self._history_cache[code] = StockHistorySummary(code=code, name=name)

        summary = self._history_cache[code]
        summary.last_seen_date = date.today()
        summary.last_tier = to_tier
        summary.last_reason = reason
        summary.updated_at = datetime.now()

        # 首次进入核心池
        if to_tier == PoolTier.CORE and summary.first_core_entry is None:
            summary.first_core_entry = date.today()

        # 计数
        if from_tier and to_tier:
            if self._get_tier_rank(to_tier) > self._get_tier_rank(from_tier):
                summary.core_upgrades += 1
            elif self._get_tier_rank(to_tier) < self._get_tier_rank(from_tier):
                summary.core_downgrades += 1

        # 更新核心池天数
        if to_tier == PoolTier.CORE:
            summary.total_core_days += 1

    def _get_tier_rank(self, tier: PoolTier) -> int:
        """获取池层级排名（数值越大越高）"""
        ranks = {
            PoolTier.CORE: 4,
            PoolTier.ACTIVE: 3,
            PoolTier.OBSERVE: 2,
            PoolTier.TEMP: 1,
        }
        return ranks.get(tier, 0)

    def get_history_summary(self, code: str) -> Optional[StockHistorySummary]:
        """
        获取股票历史摘要

        Args:
            code: 股票代码

        Returns:
            历史摘要，如果没有则返回 None
        """
        return self._history_cache.get(code)

    def has_ever_been_core(self, code: str) -> bool:
        """
        检查股票是否曾进入过核心池

        Returns:
            是否曾进入核心池
        """
        summary = self._history_cache.get(code)
        return summary is not None and summary.first_core_entry is not None

    def get_pool_change_history(self, code: Optional[str] = None,
                               limit: int = 100) -> List[Dict]:
        """
        获取池变更历史

        Args:
            code: 股票代码，如果为None则返回所有
            limit: 限制数量

        Returns:
            变更历史列表
        """
        if code:
            filtered = [c for c in self._pool_changes if c["code"] == code]
            return filtered[-limit:]
        else:
            return self._pool_changes[-limit:]

    def get_ever_core_codes(self) -> List[str]:
        """
        获取曾进入核心池的所有股票代码

        Returns:
            代码列表
        """
        return [
            code for code, summary in self._history_cache.items()
            if summary.first_core_entry is not None
        ]

    def update_cp_score(self, code: str, cp_score: float, cp_rank: int) -> None:
        """
        更新股票的战力分数

        Args:
            code: 股票代码
            cp_score: 战力分数
            cp_rank: 战力排名
        """
        if code in self._history_cache:
            self._history_cache[code].last_cp_score = cp_score
            self._history_cache[code].last_cp_rank = cp_rank
            self._history_cache[code].updated_at = datetime.now()

    def get_top_core_stocks(self, limit: int = 100) -> List[StockHistorySummary]:
        """
        获取在核心池时间最长的股票

        Args:
            limit: 返回数量

        Returns:
            按核心池天数排序的股票列表
        """
        summaries = list(self._history_cache.values())
        summaries = [s for s in summaries if s.first_core_entry is not None]
        summaries.sort(key=lambda x: (x.total_core_days, x.first_core_entry), reverse=True)
        return summaries[:limit]

    def persist(self) -> bool:
        """
        持久化历史数据到磁盘

        Returns:
            是否成功
        """
        if not self._persist_path:
            logger.warning("未设置持久化路径，跳过保存")
            return False

        try:
            import json
            data = {
                "history_cache": {
                    code: {
                        "code": s.code,
                        "name": s.name,
                        "first_core_entry": s.first_core_entry.isoformat() if s.first_core_entry else None,
                        "total_core_days": s.total_core_days,
                        "core_upgrades": s.core_upgrades,
                        "core_downgrades": s.core_downgrades,
                        "last_seen_date": s.last_seen_date.isoformat() if s.last_seen_date else None,
                        "last_tier": s.last_tier.value if s.last_tier else None,
                        "last_reason": s.last_reason,
                        "last_cp_score": s.last_cp_score,
                        "last_cp_rank": s.last_cp_rank,
                        "updated_at": s.updated_at.isoformat(),
                    }
                    for code, s in self._history_cache.items()
                },
                "pool_changes": self._pool_changes[-1000:],  # 只保留最近1000条
            }

            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"历史数据已保存到 {self._persist_path}")
            return True

        except Exception as e:
            logger.error(f"保存历史数据失败: {e}")
            return False

    def load(self) -> bool:
        """
        从磁盘加载历史数据

        Returns:
            是否成功
        """
        if not self._persist_path:
            return False

        import os
        if not os.path.exists(self._persist_path):
            logger.info(f"历史数据文件不存在: {self._persist_path}")
            return False

        try:
            import json
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 加载历史缓存
            self._history_cache.clear()
            for code, s_data in data.get("history_cache", {}).items():
                summary = StockHistorySummary(
                    code=s_data["code"],
                    name=s_data["name"],
                    first_core_entry=date.fromisoformat(s_data["first_core_entry"]) if s_data["first_core_entry"] else None,
                    total_core_days=s_data.get("total_core_days", 0),
                    core_upgrades=s_data.get("core_upgrades", 0),
                    core_downgrades=s_data.get("core_downgrades", 0),
                    last_seen_date=date.fromisoformat(s_data["last_seen_date"]) if s_data["last_seen_date"] else None,
                    last_tier=PoolTier(s_data["last_tier"]) if s_data.get("last_tier") else None,
                    last_reason=s_data.get("last_reason", ""),
                    last_cp_score=s_data.get("last_cp_score", 0),
                    last_cp_rank=s_data.get("last_cp_rank", 0),
                    updated_at=datetime.fromisoformat(s_data["updated_at"]),
                )
                self._history_cache[code] = summary

            # 加载变更记录
            self._pool_changes = data.get("pool_changes", [])

            logger.info(f"历史数据已加载，共 {len(self._history_cache)} 条记录")
            return True

        except Exception as e:
            logger.error(f"加载历史数据失败: {e}")
            return False
