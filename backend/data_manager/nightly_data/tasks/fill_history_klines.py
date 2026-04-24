"""历史K线回填任务

从2023-04-01开始，逐日回补全市场日K线数据
支持断点续传，中断后可从上次位置继续
"""
import sys
from pathlib import Path
from datetime import datetime, date, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.data_manager.filler import KlineFiller
from backend.data_manager.nightly_data.state_manager import StateManager
from backend.data_manager.nightly_data.logger import get_logger, log_task_start, log_task_progress, log_task_complete, log_task_error

TASK_ID = 'fill_history_klines'
START_DATE = '2023-04-01'
DAILY_BATCH = 50  # 每天处理50只股票

def get_date_range(start_date_str: str, end_date_str: str):
    """生成日期范围（排除周末）"""
    start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    dates = []
    current = start
    while current <= end:
        # 排除周末
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates

def fill_history_klines():
    """执行历史K线回填任务"""
    logger = get_logger(TASK_ID)
    state_mgr = StateManager()

    # 检查时间窗口
    now = datetime.now()
    if now.hour < 0 or now.hour >= 6:
        logger.info("Outside time window (00:30-06:00), skip")
        return

    # 检查是否已完成
    if state_mgr.is_task_done_today(TASK_ID):
        logger.info(f"Task {TASK_ID} already completed today, skip")
        return

    log_task_start(TASK_ID)

    try:
        # 获取上次断点
        state = state_mgr.get_task_state(TASK_ID)
        last_date = state['last_date'] if state and state['last_date'] else START_DATE
        last_code = state.get('last_code') if state else None

        logger.info(f"Resuming from last_date={last_date}, last_code={last_code}")

        # 计算需要回填的日期范围
        today = date.today()
        dates_to_fill = get_date_range(last_date, today.strftime('%Y-%m-%d'))

        logger.info(f"Need to fill {len(dates_to_fill)} trading days of data")

        # 初始化KlineFiller
        # 注意: KlineFiller.fill_all(codes=None, limit=200, days_back=730)
        # 不支持 target_date 参数，它填充所有股票最近 N 天的数据
        # 这里使用 fill_all(limit=200) 每次处理200只股票
        filler = KlineFiller()

        total_dates = len(dates_to_fill)
        for idx, d in enumerate(dates_to_fill):
            try:
                date_str = d.strftime('%Y-%m-%d')
                logger.debug(f"Filling {date_str}")

                # KlineFiller.fill_all 签名:
                # fill_all(codes: List[str] = None, limit: int = None,
                #          days_back: int = 730, rate_limit: float = None)
                # 它内部检测缺口并填充，不是按目标日期填充
                result = filler.fill_all(limit=200, days_back=730)

                # 每完成一天更新进度
                state_mgr.update_task_state(TASK_ID, last_date=date_str, status='running')

                if (idx + 1) % 10 == 0:
                    log_task_progress(TASK_ID, idx + 1, total_dates, f"date={date_str}")

            except Exception as e:
                logger.warning(f"Failed to fill {d}: {e}")
                continue

        # 标记完成
        state_mgr.mark_task_done(TASK_ID)
        log_task_complete(TASK_ID, f"Filled {total_dates} trading days")

    except Exception as e:
        log_task_error(TASK_ID, str(e))
        state_mgr.mark_task_failed(TASK_ID, str(e))

if __name__ == '__main__':
    fill_history_klines()
