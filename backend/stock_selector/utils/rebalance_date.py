"""
指数调整日计算工具

功能：
- 计算6月/12月指数调整日期
- 判断是否接近调整日
- 获取下次调整信息

中证指数调整规则：
- 调整日期：6月/12月最后一个交易日
- 生效日期：调整日后的第一个交易日
- 提前公告：通常提前2周公布
"""

from datetime import date, timedelta
from typing import List, Tuple, Optional


class RebalanceDateCalculator:
    """
    指数调整日期计算器
    """

    # 调样月份
    REBALANCE_MONTHS = [6, 12]

    # 调整生效延迟（通常是调整日后第一个交易日）
    EFFECTIVE_DELAY_DAYS = 1

    def __init__(self):
        pass

    def get_next_rebalance_dates(self, year: int) -> List[date]:
        """
        获取指定年度的所有调样日期

        Args:
            year: 年份

        Returns:
            调样日期列表（通常6月和12月各一次）
        """
        dates = []
        for month in self.REBALANCE_MONTHS:
            rebalance_date = self._get_last_trading_day(year, month)
            if rebalance_date:
                dates.append(rebalance_date)
        return dates

    def get_next_rebalance_date(self) -> Tuple[date, str]:
        """
        获取下次调样日期

        Returns:
            (date, description)
        """
        today = date.today()

        # 检查今年
        for month in self.REBALANCE_MONTHS:
            rebalance_date = self._get_last_trading_day(today.year, month)
            if rebalance_date and rebalance_date > today:
                return rebalance_date, f"{today.year}年{month}月"

        # 检查明年
        next_year = today.year + 1
        for month in self.REBALANCE_MONTHS:
            rebalance_date = self._get_last_trading_day(next_year, month)
            if rebalance_date:
                return rebalance_date, f"{next_year}年{month}月"

        # 默认返回30天后
        return today + timedelta(days=30), "未找到"

    def get_days_until_rebalance(self) -> Tuple[int, str]:
        """
        获取距离下次调样的天数

        Returns:
            (天数, 描述)
        """
        next_date, desc = self.get_next_rebalance_date()
        today = date.today()
        days = (next_date - today).days
        return max(0, days), desc

    def is_rebalance_month(self, month: int) -> bool:
        """检查是否是调样月份"""
        return month in self.REBALANCE_MONTHS

    def is_near_rebalance(self, threshold_days: int = 7) -> bool:
        """
        检查是否接近调样日

        Args:
            threshold_days: 阈值天数

        Returns:
            是否接近
        """
        days, _ = self.get_days_until_rebalance()
        return days <= threshold_days

    def get_effective_date(self, rebalance_date: date) -> date:
        """
        获取调整生效日期

        Args:
            rebalance_date: 调样日期

        Returns:
            生效日期
        """
        return rebalance_date + timedelta(days=self.EFFECTIVE_DELAY_DAYS)

    def _get_last_trading_day(self, year: int, month: int) -> Optional[date]:
        """
        获取指定月份最后一个交易日

        简化实现：取月末最后一天，如果是周末则前移到周五
        实际应查询交易日历

        Args:
            year: 年
            month: 月

        Returns:
            最后一个交易日
        """
        # 月末最后一天
        if month == 12:
            next_month_first = date(year + 1, 1, 1)
        else:
            next_month_first = date(year, month + 1, 1)

        last_day = next_month_first - timedelta(days=1)

        # 如果是周末，往前推到周五
        weekday = last_day.weekday()
        if weekday == 5:  # Saturday
            last_day -= timedelta(days=1)
        elif weekday == 6:  # Sunday
            last_day -= timedelta(days=2)

        return last_day

    def nth_weekday(self, year: int, month: int, n: int, weekday: int) -> date:
        """
        获取第n个指定星期几的日期

        Args:
            year: 年
            month: 月
            n: 第几个（从1开始）
            weekday: 星期几（0=周一，6=周日）

        Returns:
            日期
        """
        first_day = date(year, month, 1)

        # 找到第一个指定的星期几
        days_ahead = weekday - first_day.weekday()
        if days_ahead < 0:
            days_ahead += 7

        first_weekday = first_day + timedelta(days=days_ahead)
        return first_weekday + timedelta(weeks=n - 1)

    def get_announcement_estimate(self, rebalance_date: date) -> date:
        """
        估算公告日期（通常提前2周）

        Args:
            rebalance_date: 调样日期

        Returns:
            估算的公告日期
        """
        return rebalance_date - timedelta(days=14)


def get_next_rebalance_dates(year: int) -> List[date]:
    """
    获取指定年度的指数调样日期

    Args:
        year: 年份

    Returns:
        调样日期列表
    """
    calc = RebalanceDateCalculator()
    return calc.get_next_rebalance_dates(year)


def get_days_until_rebalance() -> Tuple[int, str]:
    """
    获取距离下次调样的天数

    Returns:
        (天数, 描述)
    """
    calc = RebalanceDateCalculator()
    return calc.get_days_until_rebalance()


def is_near_rebalance(threshold_days: int = 7) -> bool:
    """
    检查是否接近调样日

    Args:
        threshold_days: 阈值天数

    Returns:
        是否接近
    """
    calc = RebalanceDateCalculator()
    return calc.is_near_rebalance(threshold_days)
