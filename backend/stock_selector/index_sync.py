"""
指数成分同步

功能：
- 获取并同步指数成分股（沪深300、中证500、中证1000）
- 动态计算指数调整日期
- 跟踪成分股变化

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from .enums import PoolTier
from .pool_manager import PoolManager
from . import config

logger = logging.getLogger(__name__)


class IndexComponent:
    """指数成分股信息"""

    def __init__(self, code: str, name: str, index_name: str,
                 weight: float = 0, join_date: Optional[date] = None):
        self.code = code
        self.name = name
        self.index_name = index_name
        self.weight = weight
        self.join_date = join_date or date.today()

    def __repr__(self):
        return f"IndexComponent({self.code}, {self.name}, {self.index_name})"


class IndexSync:
    """
    指数成分同步器

    支持的指数：
    - 沪深300 (000300)
    - 中证500 (000905)
    - 中证1000 (000852)
    """

    INDEX_CODES = {
        "hs300": "000300",
        "zz500": "000905",
        "zz1000": "000852",
    }

    INDEX_NAMES = {
        "hs300": "沪深300",
        "zz500": "中证500",
        "zz1000": "中证1000",
    }

    def __init__(self, pool_manager: PoolManager):
        self._pm = pool_manager

        # 缓存的成分股数据
        self._components: Dict[str, Dict[str, IndexComponent]] = {
            "hs300": {},
            "zz500": {},
            "zz1000": {},
        }

        # 上次更新时间
        self._last_sync_time: Optional[datetime] = None

        # 变更记录
        self._change_records: List[Dict] = []

    def sync_components(self, index: str, components: List[Dict]) -> Dict[str, Set[str]]:
        """
        同步指数成分股

        Args:
            index: 指数标识 "hs300" | "zz500" | "zz1000"
            components: 成分股列表 [{
                code: str,
                name: str,
                weight: float,  # 可选
            }]

        Returns:
            {
                "added": {codes},   # 新加入的
                "removed": {codes}, # 删除的
            }
        """
        if index not in self._components:
            logger.error(f"未知指数: {index}")
            return {"added": set(), "removed": set()}

        old_components = set(self._components[index].keys())
        new_components = set()

        # 更新成分股
        for comp_data in components:
            code = comp_data["code"]
            name = comp_data.get("name", "")
            weight = comp_data.get("weight", 0)

            component = IndexComponent(
                code=code,
                name=name,
                index_name=self.INDEX_NAMES.get(index, index),
                weight=weight,
            )

            self._components[index][code] = component
            new_components.add(code)

        # 计算变更
        added = new_components - old_components
        removed = old_components - new_components

        # 记录变更
        if added or removed:
            self._record_change(index, added, removed)
            logger.info(f"指数 {self.INDEX_NAMES.get(index, index)} 同步完成：新增 {len(added)}，移除 {len(removed)}")

        self._last_sync_time = datetime.now()

        return {"added": added, "removed": removed}

    def get_components(self, index: str) -> List[str]:
        """
        获取指数成分股代码列表

        Args:
            index: 指数标识

        Returns:
            成分股代码列表
        """
        if index not in self._components:
            return []
        return list(self._components[index].keys())

    def get_all_index_components(self) -> Dict[str, List[str]]:
        """
        获取所有指数的成分股

        Returns:
            {"hs300": [codes], "zz500": [codes], "zz1000": [codes]}
        """
        return {index: self.get_components(index) for index in self._components}

    def is_component(self, code: str, index: str) -> bool:
        """检查股票是否是指定指数成分"""
        return code in self._components.get(index, {})

    def get_indices_for_code(self, code: str) -> List[str]:
        """获取股票所在的指数列表"""
        indices = []
        for index, components in self._components.items():
            if code in components:
                indices.append(index)
        return indices

    def _record_change(self, index: str, added: Set[str], removed: Set[str]) -> None:
        """记录成分变更"""
        self._change_records.append({
            "index": index,
            "added": list(added),
            "removed": list(removed),
            "timestamp": datetime.now(),
        })

    def get_change_records(self, limit: int = 50) -> List[Dict]:
        """获取变更记录"""
        return self._change_records[-limit:]

    def get_last_sync_time(self) -> Optional[datetime]:
        """获取上次同步时间"""
        return self._last_sync_time


class RebalanceDateCalculator:
    """
    指数调整日期计算器

    功能：
    - 动态计算6月/12月指数调整日期
    - 返回调整生效日
    """

    # 中证指数调整规则：月末最后一个交易日
    REBALANCE_MONTHS = [6, 12]

    def __init__(self):
        pass

    def get_next_rebalance_dates(self, year: int) -> List[date]:
        """
        获取指定年度的指数调样日期

        Args:
            year: 年份

        Returns:
            调样日期列表
        """
        dates = []
        for month in self.REBALANCE_MONTHS:
            rebalance_date = self._get_last_trading_day(year, month)
            if rebalance_date:
                dates.append(rebalance_date)
        return dates

    def get_next_rebalance_date(self) -> Tuple[date, str]:
        """
        获取距离下次指数调样的日期

        Returns:
            (date, description)
        """
        today = date.today()

        # 检查今年
        for month in self.REBALANCE_MONTHS:
            rebalance_date = self._get_last_trading_day(today.year, month)
            if rebalance_date > today:
                days_left = (rebalance_date - today).days
                return rebalance_date, f"{today.year}年{month}月 ({days_left}天后)"

        # 检查明年
        next_year = today.year + 1
        rebalance_date = self._get_last_trading_day(next_year, 6)
        if rebalance_date:
            days_left = (rebalance_date - today).days
            return rebalance_date, f"{next_year}年6月 ({days_left}天后)"

        # 默认
        return today + timedelta(days=30), "未找到下次调样日"

    def get_days_until_rebalance(self) -> Tuple[int, str]:
        """
        获取距离下次调样的天数

        Returns:
            (days, description)
        """
        next_date, desc = self.get_next_rebalance_date()
        today = date.today()
        days = (next_date - today).days
        return days, desc

    def _get_last_trading_day(self, year: int, month: int) -> Optional[date]:
        """
        获取指定月份最后一个交易日

        简化实现：取月末最后一天，如果是周末则前移到周五
        实际应查询交易日历
        """
        # 月末最后一天
        if month == 12:
            next_month_first = date(year + 1, 1, 1)
        else:
            next_month_first = date(year, month + 1, 1)

        last_day = next_month_first - timedelta(days=1)

        # 如果是周末，往前推
        weekday = last_day.weekday()
        if weekday == 5:  # Saturday
            last_day -= timedelta(days=1)
        elif weekday == 6:  # Sunday
            last_day -= timedelta(days=2)

        return last_day

    def is_rebalance_month(self, month: int) -> bool:
        """检查是否是调样月份"""
        return month in self.REBALANCE_MONTHS

    def is_near_rebalance(self, days_threshold: int = 7) -> bool:
        """
        检查是否接近调样日

        Args:
            days_threshold: 阈值天数

        Returns:
            是否接近
        """
        days_left, _ = self.get_days_until_rebalance()
        return days_left <= days_threshold


class IndexSyncManager:
    """
    指数同步管理器

    整合 IndexSync 和 RebalanceDateCalculator
    """

    def __init__(self, pool_manager: PoolManager):
        self._pm = pool_manager
        self._sync = IndexSync(pool_manager)
        self._date_calc = RebalanceDateCalculator()

    def check_and_sync(self, index_data: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """
        检查并同步所有指数

        Args:
            index_data: {
                "hs300": [{"code": "600000", "name": "浦发银行", "weight": 0.5}, ...],
                "zz500": [...],
                "zz1000": [...],
            }

        Returns:
            各指数同步结果
        """
        results = {}

        for index, components in index_data.items():
            result = self._sync.sync_components(index, components)
            results[index] = result

        return results

    def get_pool_for_index(self, index: str) -> PoolTier:
        """
        获取指数对应的目标池

        Returns:
            PoolTier
        """
        if index == "hs300" or index == "zz500":
            return PoolTier.CORE
        elif index == "zz1000":
            return PoolTier.ACTIVE
        else:
            return PoolTier.OBSERVE

    def sync_to_pools(self, index_data: Dict[str, List[Dict]]) -> Dict[str, int]:
        """
        同步指数成分到股票池

        Args:
            index_data: 指数成分数据

        Returns:
            各池同步数量
        """
        sync_results = self.check_and_sync(index_data)

        stats = {"core": 0, "active": 0, "observe": 0}

        for index, result in sync_results.items():
            target_tier = self.get_pool_for_index(index)

            # 处理新增
            for code in result.get("added", []):
                component = self._sync._components[index].get(code)
                if component:
                    from .types import StockInfo
                    info = StockInfo(
                        code=code,
                        name=component.name,
                        tier=PoolTier.OBSERVE,
                        tier_entry_date=date.today(),
                        tier_reason=f"指数纳入: {self._sync.INDEX_NAMES.get(index, index)}",
                    )
                    self._pm.add_stock(code, target_tier, info, f"指数纳入{self._sync.INDEX_NAMES.get(index, index)}")
                    stats[target_tier.value] += 1

        return stats

    def is_rebalance_due(self) -> bool:
        """检查是否应该触发再平衡"""
        return self._date_calc.is_near_rebalance(days_threshold=7)

    def get_rebalance_info(self) -> Dict:
        """获取再平衡信息"""
        days, desc = self._date_calc.get_days_until_rebalance()
        return {
            "days_until": days,
            "description": desc,
            "is_due": days <= 7,
        }
