"""
工具函数
"""

from datetime import date, timedelta
from typing import List, Tuple


def normalize_code(code: str) -> str:
    """
    标准化股票代码

    Args:
        code: 股票代码，可能是 '000001', '1', '000001.sz' 等

    Returns:
        6位数字字符串，如 '000001'
    """
    # 移除后缀
    code = code.split(".")[0]

    # 移除前导零后转整数再转回字符串
    code = str(int(code))

    # 补齐到6位
    return code.zfill(6)


def is_valid_code(code: str) -> bool:
    """
    检查是否是有效的股票代码

    Args:
        code: 股票代码

    Returns:
        是否有效
    """
    code = normalize_code(code)

    # 沪市：600-688 开头
    # 深市：000、001、002、003 开头
    # 创业板：300 开头
    # 科创板：688 开头

    valid_prefixes = ("000", "001", "002", "003", "300", "600", "601", "603", "688")
    return any(code.startswith(p) for p in valid_prefixes) and len(code) == 6


def get_next_rebalance_dates(year: int) -> List[date]:
    """
    获取指定年度的指数调样日期（6月和12月最后一个交易日）

    Args:
        year: 年份

    Returns:
        调样日期列表
    """
    # 中证指数一般在月末最后一个交易日调整
    dates = []

    # 6月调样
    june_date = _get_last_trading_day(year, 6)
    if june_date:
        dates.append(june_date)

    # 12月调样
    december_date = _get_last_trading_day(year, 12)
    if december_date:
        dates.append(december_date)

    return dates


def _get_last_trading_day(year: int, month: int) -> date:
    """
    获取指定月份最后一个交易日

    这里简化处理，实际应该查询交易日历
    """
    # 简单取月末最后一天
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    last_day = next_month - timedelta(days=1)

    # 如果是周末，往前推到周五
    weekday = last_day.weekday()
    if weekday == 5:  # Saturday
        last_day -= timedelta(days=1)
    elif weekday == 6:  # Sunday
        last_day -= timedelta(days=2)

    return last_day


def nth_weekday_after(year: int, month: int, n: int, weekday: int) -> date:
    """
    获取从指定月份1号开始第n个指定星期几的日期

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

    # 计算第n个
    first_weekday = first_day + timedelta(days=days_ahead)
    return first_weekday + timedelta(weeks=n - 1)


def get_days_until_rebalance() -> Tuple[int, str]:
    """
    获取距离下次指数调样的天数

    Returns:
        (天数, 说明)
    """
    today = date.today()

    # 检查今年6月和12月
    for month in [6, 12]:
        rebalance_date = _get_last_trading_day(today.year, month)
        if rebalance_date > today:
            days_left = (rebalance_date - today).days
            return days_left, f"{today.year}年{month}月调样"

    # 检查明年6月
    rebalance_date = _get_last_trading_day(today.year + 1, 6)
    days_left = (rebalance_date - today).days
    return days_left, f"{today.year + 1}年6月调样"


def format_volume(volume: float) -> str:
    """
    格式化成交额显示

    Args:
        volume: 成交额（万元）

    Returns:
        格式化字符串，如 '1.23亿'、'4567万'
    """
    if volume >= 10000:
        return f"{volume / 10000:.2f}亿"
    elif volume >= 1:
        return f"{volume:.0f}万"
    else:
        return f"{volume * 10000:.0f}元"


def format_market_cap(market_cap: float) -> str:
    """
    格式化市值显示

    Args:
        market_cap: 流通市值（万元）

    Returns:
        格式化字符串
    """
    if market_cap >= 10000:
        return f"{market_cap / 10000:.2f}万亿" if market_cap >= 100000000 else f"{market_cap / 10000:.2f}亿"
    elif market_cap >= 1:
        return f"{market_cap:.0f}万"
    else:
        return f"{market_cap * 10000:.0f}元"
