"""夜间数据任务状态管理器"""
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

DATA_DIR = Path("/home/ailearn/projects/TradeSnake/data")
STATE_DB = DATA_DIR / "nightly_state.db"

class StateManager:
    """管理夜间任务的执行状态，支持断点续传"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_path = str(STATE_DB)
        self._ensure_tables()
        self._initialized = True

    def _ensure_tables(self):
        """创建状态表"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_state (
                    task_id VARCHAR(20) PRIMARY KEY,
                    last_run DATE,
                    status VARCHAR(10),
                    last_date VARCHAR(10),
                    last_code VARCHAR(10),
                    error_msg TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS validation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_date DATE,
                    data_type VARCHAR(20),
                    code VARCHAR(10),
                    source1 VARCHAR(20),
                    source2 VARCHAR(20),
                    diff_percent FLOAT,
                    created_at TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM task_state WHERE task_id = ?", (task_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'task_id': row[0],
                    'last_run': row[1],
                    'status': row[2],
                    'last_date': row[3],
                    'last_code': row[4],
                    'error_msg': row[5],
                    'updated_at': row[6]
                }
            return None
        finally:
            conn.close()

    def update_task_state(self, task_id: str, last_date: str = None,
                          last_code: str = None, status: str = 'running',
                          error_msg: str = None):
        """更新任务状态"""
        conn = sqlite3.connect(self.db_path)
        try:
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO task_state
                (task_id, last_run, status, last_date, last_code, error_msg, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, datetime.now().date().isoformat(), status,
                  last_date, last_code, error_msg, now))
            conn.commit()
        finally:
            conn.close()

    def is_task_done_today(self, task_id: str) -> bool:
        """检查任务是否已在今天完成"""
        state = self.get_task_state(task_id)
        if not state:
            return False
        if state['status'] != 'completed':
            return False
        if state['last_run']:
            return state['last_run'] == datetime.now().date().isoformat()
        return False

    def mark_task_done(self, task_id: str):
        """标记任务完成"""
        self.update_task_state(task_id, status='completed')

    def mark_task_failed(self, task_id: str, error: str):
        """标记任务失败"""
        self.update_task_state(task_id, status='failed', error_msg=error)

    def log_validation(self, data_type: str, code: str, source1: str,
                       source2: str, diff_percent: float):
        """记录验证结果"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO validation_results
                (check_date, data_type, code, source1, source2, diff_percent, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datetime.now().date().isoformat(), data_type, code,
                  source1, source2, diff_percent, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()