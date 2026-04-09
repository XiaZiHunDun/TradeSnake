"""
刷新策略 - Refresh Strategy
"""

from datetime import datetime


def get_refresh_interval() -> int:
    """获取数据刷新间隔（秒）"""
    now = datetime.now()
    hour = now.hour

    # 交易时间：9:30-11:30, 13:00-15:00
    if 9 <= hour < 11 or (hour == 11 and now.minute < 30) or (hour == 13) or (14 <= hour < 15):
        return 60  # 交易时间每分钟刷新
    elif 8 <= hour < 20:
        return 300  # 盘前盘后5分钟刷新
    else:
        return 3600  # 收盘后1小时刷新


def get_market_phase() -> str:
    """获取当前市场阶段"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    if hour < 9 or (hour == 9 and minute < 30):
        return "pre_open"
    elif hour == 9 and minute >= 30:
        return "morning_open"
    elif 10 <= hour < 11:
        return "morning"
    elif hour == 11 and minute < 30:
        return "late_morning"
    elif hour == 11 and minute >= 30:
        return "noon_break"
    elif 13 <= hour < 15:
        return "afternoon"
    elif hour == 15:
        return "market_close"
    elif 16 <= hour < 20:
        return "after_hours"
    else:
        return "closed"
