"""
交易时间判断 - Trading Time
"""

from datetime import datetime, time


def is_trading_time() -> bool:
    """判断当前是否为交易时间"""
    now = datetime.now()
    current_time = now.time()

    morning_start = time(9, 30)
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)

    if now.weekday() >= 5:  # 周六周日
        return False

    if morning_start <= current_time <= morning_end:
        return True
    if afternoon_start <= current_time <= afternoon_end:
        return True

    return False


def get_trading_status() -> dict:
    """获取详细交易状态"""
    now = datetime.now()
    current_time = now.time()
    weekday = now.weekday()

    if weekday >= 5:
        return {"status": "closed", "reason": "周末"}

    morning_start = time(9, 30)
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)

    if current_time < morning_start:
        return {"status": "pre_open", "reason": "早盘未开盘", "next": "09:30"}
    elif morning_start <= current_time <= morning_end:
        return {"status": "trading", "session": "morning", "next": "11:30"}
    elif current_time < afternoon_start:
        return {"status": "lunch_break", "reason": "午间休市", "next": "13:00"}
    elif afternoon_start <= current_time <= afternoon_end:
        return {"status": "trading", "session": "afternoon", "next": "15:00"}
    else:
        return {"status": "closed", "reason": "已收盘", "next": "09:30"}
