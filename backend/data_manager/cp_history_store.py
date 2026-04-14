"""
战力历史数据存储模块

由 data_manager 统一管理 cp_history 数据：
- 存储：SQLite WAL 模式
- 生命周期：2年保留
- 清理：由 data_manager/cleanup.py 统一管理

设计文档：docs/plans/DATA_LIFECYCLE_MANAGEMENT.md
"""

import sqlite3
import threading
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class CPHistoryStore:
    """战力历史数据存储"""

    _instance: Optional['CPHistoryStore'] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return

        if db_path is None:
            db_path = "/home/ailearn/projects/TradeSnake/data/tradesnake_cp_history.db"

        self.db_path = db_path
        self._write_lock = threading.Lock()
        self._ensure_db()
        self._initialized = True

    def _ensure_db(self):
        """确保数据库和表存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                price REAL DEFAULT 0,
                total_cp REAL DEFAULT 0,
                growth_score REAL DEFAULT 0,
                value_score REAL DEFAULT 0,
                quality_score REAL DEFAULT 0,
                momentum_score REAL DEFAULT 0,
                risk_score REAL DEFAULT 0,
                rank INTEGER DEFAULT 0,
                recorded_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 迁移：检查并添加缺失的列
        cursor.execute("PRAGMA table_info(cp_history)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # 需要添加的列（表结构升级）
        required_columns = {
            'price': 'REAL DEFAULT 0',
            'is_hot': 'INTEGER DEFAULT 1',
        }

        for col_name, col_type in required_columns.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE cp_history ADD COLUMN {col_name} {col_type}")
                    print(f"Migration: Added column {col_name} to cp_history")
                except Exception as e:
                    print(f"Migration warning: Could not add column {col_name}: {e}")

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_date ON cp_history(recorded_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_code ON cp_history(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_date_code ON cp_history(recorded_at, code)")

        # 启用 WAL 模式
        cursor.execute("PRAGMA journal_mode=WAL")

        conn.commit()
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_cp_history(self, stocks: List[Dict], date: str = None) -> int:
        """保存战力历史

        Args:
            stocks: 股票战力列表
            date: 日期，默认当天

        Returns:
            保存的股票数量
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM cp_history WHERE recorded_at = ?", (date,))

            sorted_stocks = sorted(stocks, key=lambda x: x.get('total_cp', 0), reverse=True)
            for rank, stock in enumerate(sorted_stocks, 1):
                cursor.execute("""
                    INSERT INTO cp_history (
                        code, name, price, total_cp, growth_score, value_score,
                        quality_score, momentum_score, risk_score, rank, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stock.get('code'),
                    stock.get('name'),
                    stock.get('price', 0),
                    stock.get('total_cp', 0),
                    stock.get('growth_score', 0),
                    stock.get('value_score', 0),
                    stock.get('quality_score', 0),
                    stock.get('momentum_score', 0),
                    stock.get('risk_score', 0),
                    rank,
                    date
                ))

            conn.commit()
            conn.close()
            return len(sorted_stocks)

    def get_cp_history(self, code: str, days: int = 30) -> List[Dict]:
        """获取指定股票的历史战力

        Args:
            code: 股票代码
            days: 获取天数

        Returns:
            历史战力列表
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM cp_history WHERE code = ?
            ORDER BY recorded_at DESC LIMIT ?
        """, (code, days))

        result = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return result

    def get_cp_history_by_date(self, date: str) -> List[Dict]:
        """获取指定日期的战力数据

        Args:
            date: 日期 (YYYY-MM-DD)

        Returns:
            该日期的战力列表
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM cp_history WHERE recorded_at = ?
            ORDER BY rank
        """, (date,))

        result = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return result

    def get_cp_changes(self, days: int = 7) -> List[Dict]:
        """获取战力变化

        Args:
            days: 对比天数

        Returns:
            战力变化列表
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT recorded_at FROM cp_history
            ORDER BY recorded_at DESC LIMIT ?
        """, (days,))

        date_rows = cursor.fetchall()
        if len(date_rows) < 2:
            conn.close()
            return []

        oldest_date = date_rows[-1]['recorded_at']
        latest_date = date_rows[0]['recorded_at']

        cursor.execute("""
            SELECT h1.code, h1.name,
                   h2.total_cp as old_cp, h1.total_cp as new_cp,
                   h1.total_cp - h2.total_cp as change
            FROM cp_history h1
            JOIN cp_history h2 ON h1.code = h2.code
            WHERE h1.recorded_at = ? AND h2.recorded_at = ?
            ORDER BY change DESC
        """, (latest_date, oldest_date))

        result = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return result

    def get_all_codes(self) -> List[str]:
        """获取所有有战力历史的股票代码"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT code FROM cp_history")
        result = [row['code'] for row in cursor.fetchall()]
        conn.close()
        return result

    def delete_old_records(self, before_date: str) -> int:
        """删除指定日期之前的记录

        Args:
            before_date: 日期 (YYYY-MM-DD)

        Returns:
            删除的记录数
        """
        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM cp_history WHERE recorded_at < ?", (before_date,))
            deleted = cursor.rowcount

            conn.commit()
            conn.close()
            return deleted


# 全局实例
_store: Optional[CPHistoryStore] = None


def get_cp_history_store() -> CPHistoryStore:
    """获取 CPHistoryStore 单例"""
    global _store
    if _store is None:
        _store = CPHistoryStore()
    return _store
