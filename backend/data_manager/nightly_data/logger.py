"""夜间数据任务日志工具"""
import logging
from datetime import datetime, date
from pathlib import Path
import os

from backend.config import LOG_DIR
LOG_DIR.mkdir(parents=True, exist_ok=True)

def get_logger(task_name: str) -> logging.Logger:
    """获取指定任务的logger"""
    logger = logging.getLogger(f"nightly.{task_name}")

    # 避免重复添加handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 按日期创建日志文件
    log_file = LOG_DIR / f"nightly_{date.today().isoformat()}.log"

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def log_task_start(task_name: str, total: int = None):
    """记录任务开始"""
    logger = get_logger(task_name)
    msg = f"Task {task_name} started"
    if total:
        msg += f" (total: {total})"
    logger.info(msg)

def log_task_progress(task_name: str, current: int, total: int,
                      extra: str = ""):
    """记录任务进度"""
    logger = get_logger(task_name)
    pct = current / total * 100 if total else 0
    msg = f"Progress: {current}/{total} ({pct:.1f}%)"
    if extra:
        msg += f" - {extra}"
    logger.info(msg)

def log_task_complete(task_name: str, summary: str = ""):
    """记录任务完成"""
    logger = get_logger(task_name)
    msg = f"Task {task_name} completed"
    if summary:
        msg += f" - {summary}"
    logger.info(msg)

def log_task_error(task_name: str, error: str, extra: str = ""):
    """记录任务错误"""
    logger = get_logger(task_name)
    msg = f"Task {task_name} error: {error}"
    if extra:
        msg += f" - {extra}"
    logger.error(msg)