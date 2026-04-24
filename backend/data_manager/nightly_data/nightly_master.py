#!/usr/bin/env python3
"""
夜间数据增强系统主调度脚本

通过 crontab 每天凌晨 00:30 触发:
0 30 * * * /home/ailearn/miniconda3/envs/tradesnake/bin/python backend/data_manager/nightly_data/nightly_master.py

各任务按顺序执行，支持断点续传
"""
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.data_manager.nightly_data.state_manager import StateManager
from backend.data_manager.nightly_data.logger import get_logger

# 导入各任务
from backend.data_manager.nightly_data.tasks.fill_history_klines import fill_history_klines
from backend.data_manager.nightly_data.tasks.fill_index_etf import fill_index_etf
from backend.data_manager.nightly_data.tasks.validate_data import validate_data
from backend.data_manager.nightly_data.tasks.update_predictions import update_predictions

TASKS = [
    ('fill_history_klines', fill_history_klines),
    ('fill_index_etf', fill_index_etf),
    ('validate_data', validate_data),
    ('update_predictions', update_predictions),
]

def check_time_window() -> bool:
    """检查是否在允许的时间窗口内 (00:30 - 06:00)"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    # 00:30 到 06:00
    if hour < 0 or hour >= 6:
        return False
    if hour == 0 and minute < 30:
        return False
    return True

def run():
    """主调度逻辑"""
    logger = get_logger('master')

    if not check_time_window():
        logger.info("Outside time window (00:30-06:00), exit gracefully")
        sys.exit(0)

    logger.info("=" * 50)
    logger.info("Nightly data enhancement started")
    logger.info("=" * 50)

    state_mgr = StateManager()

    for task_id, task_func in TASKS:
        logger.info(f"Starting task: {task_id}")

        try:
            task_func()
            logger.info(f"Task {task_id} completed")
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            # 继续执行下一个任务，不阻塞

    logger.info("=" * 50)
    logger.info("Nightly data enhancement finished")
    logger.info("=" * 50)

if __name__ == '__main__':
    run()
