"""
SQLite数据库模块 - TradeSnake v17

使用WAL模式提高并发读写性能，支持:
- 股票数据存储
- 战力历史记录
- 预警配置（未来扩展）
"""

import sqlite3
import json
import os
import threading
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

DB_PATH = "/home/ailearn/projects/TradeSnake/data/tradesnake.db"


class Database:
    """SQLite数据库封装类，支持WAL模式"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.db_path = DB_PATH
            self._ensure_db_dir()
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
            self.conn.execute("PRAGMA journal_mode=WAL")  # WAL模式提高并发
            self.conn.execute("PRAGMA synchronous=NORMAL")  # 平衡安全与性能
            self.conn.row_factory = sqlite3.Row
            self._write_lock = threading.Lock()
            self._initialized = True
            self._create_tables()

    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def _create_tables(self):
        """创建数据库表"""
        with self._write_lock:
            cursor = self.conn.cursor()

            # 1. 股票实时数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    price REAL DEFAULT 0,
                    pe REAL DEFAULT 0,
                    roe REAL DEFAULT 0,
                    net_profit_growth REAL DEFAULT 0,
                    revenue_growth REAL DEFAULT 0,
                    change_pct REAL DEFAULT 0,
                    pb REAL DEFAULT 0,
                    gross_margin REAL DEFAULT 0,
                    revenue REAL DEFAULT 0,
                    cashflow REAL DEFAULT 0,
                    debt_ratio REAL DEFAULT 0,
                    volume REAL DEFAULT 0,
                    amount REAL DEFAULT 0,
                    dividend_yield REAL DEFAULT 0,
                    market_cap REAL DEFAULT 0,
                    high REAL DEFAULT 0,
                    low REAL DEFAULT 0,
                    growth_score REAL DEFAULT 0,
                    value_score REAL DEFAULT 0,
                    momentum_score REAL DEFAULT 0,
                    quality_score REAL DEFAULT 0,
                    total_cp REAL DEFAULT 0,
                    risk_score REAL DEFAULT 0,
                    risk_level TEXT DEFAULT '',
                    peg REAL DEFAULT 0,
                    data_quality TEXT DEFAULT 'low',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. 战力历史记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cp_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
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

            # 3. 预警配置表（v17.2使用）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_type TEXT NOT NULL UNIQUE,
                    threshold REAL DEFAULT 10,
                    is_enabled INTEGER DEFAULT 1,
                    cooldown_hours INTEGER DEFAULT 24,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 4. 预警记录表（v17.2使用）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT,
                    name TEXT,
                    alert_type TEXT NOT NULL,
                    level TEXT DEFAULT 'warning',
                    title TEXT,
                    message TEXT,
                    cp_before REAL DEFAULT 0,
                    cp_after REAL DEFAULT 0,
                    is_read INTEGER DEFAULT 0,
                    is_muted INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT
                )
            """)

            # 5. 系统配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 6. 迁移版本记录
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 7. 用户配置表（存储用户约束）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),  -- 单行配置
                    capital REAL DEFAULT 20000,
                    allowed_boards TEXT DEFAULT 'main',  -- 逗号分隔: main,gem,star
                    risk_preference TEXT DEFAULT 'aggressive',
                    consider_dividend INTEGER DEFAULT 1,
                    keep_cash_reserve INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_date ON cp_history(recorded_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_code ON cp_history(code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_date_code ON cp_history(recorded_at, code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_unread ON alerts(is_read, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_code ON alerts(code)")

            self.conn.commit()

    @contextmanager
    def get_cursor(self):
        """获取数据库游标的上下文管理器"""
        cursor = self.conn.cursor()
        try:
            yield cursor
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()

    # ==================== 股票数据操作 ====================

    def upsert_stock(self, stock: Dict):
        """插入或更新股票数据"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO stocks (
                    code, name, price, pe, roe, net_profit_growth, revenue_growth,
                    change_pct, pb, gross_margin, revenue, cashflow, debt_ratio,
                    volume, amount, dividend_yield, market_cap, high, low,
                    growth_score, value_score, momentum_score, quality_score,
                    total_cp, risk_score, risk_level, peg, data_quality, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stock.get('code'), stock.get('name'), stock.get('price', 0),
                stock.get('pe', 0), stock.get('roe', 0), stock.get('net_profit_growth', 0),
                stock.get('revenue_growth', 0), stock.get('change_pct', 0),
                stock.get('pb', 0), stock.get('gross_margin', 0), stock.get('revenue', 0),
                stock.get('cashflow', 0), stock.get('debt_ratio', 0),
                stock.get('volume', 0), stock.get('amount', 0), stock.get('dividend_yield', 0),
                stock.get('market_cap', 0), stock.get('high', 0), stock.get('low', 0),
                stock.get('growth_score', 0), stock.get('value_score', 0),
                stock.get('momentum_score', 0), stock.get('quality_score', 0),
                stock.get('total_cp', 0), stock.get('risk_score', 0),
                stock.get('risk_level', ''), stock.get('peg', 0),
                stock.get('data_quality', 'low'),
                datetime.now().isoformat()
            ))
            self.conn.commit()

    def batch_upsert_stocks(self, stocks: List[Dict]):
        """批量插入或更新股票数据"""
        with self._write_lock:
            cursor = self.conn.cursor()
            data = [
                (
                    s.get('code'), s.get('name'), s.get('price', 0),
                    s.get('pe', 0), s.get('roe', 0), s.get('net_profit_growth', 0),
                    s.get('revenue_growth', 0), s.get('change_pct', 0),
                    s.get('pb', 0), s.get('gross_margin', 0), s.get('revenue', 0),
                    s.get('cashflow', 0), s.get('debt_ratio', 0),
                    s.get('volume', 0), s.get('amount', 0), s.get('dividend_yield', 0),
                    s.get('market_cap', 0), s.get('high', 0), s.get('low', 0),
                    s.get('growth_score', 0), s.get('value_score', 0),
                    s.get('momentum_score', 0), s.get('quality_score', 0),
                    s.get('total_cp', 0), s.get('risk_score', 0),
                    s.get('risk_level', ''), s.get('peg', 0),
                    s.get('data_quality', 'low'),
                    datetime.now().isoformat()
                ) for s in stocks
            ]
            cursor.executemany("""
                INSERT OR REPLACE INTO stocks (
                    code, name, price, pe, roe, net_profit_growth, revenue_growth,
                    change_pct, pb, gross_margin, revenue, cashflow, debt_ratio,
                    volume, amount, dividend_yield, market_cap, high, low,
                    growth_score, value_score, momentum_score, quality_score,
                    total_cp, risk_score, risk_level, peg, data_quality, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            self.conn.commit()
            return cursor.rowcount

    def get_stock(self, code: str) -> Optional[Dict]:
        """获取单只股票数据"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM stocks WHERE code = ?", (code,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_stocks(self) -> List[Dict]:
        """获取所有股票数据"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM stocks ORDER BY total_cp DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_top_stocks(self, limit: int = 50) -> List[Dict]:
        """获取战力榜TOP N"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM stocks ORDER BY total_cp DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # ==================== 战力历史操作 ====================

    def record_cp_history(self, stocks: List[Dict], date: str = None):
        """记录每日战力快照"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        with self._write_lock:
            cursor = self.conn.cursor()

            # 先删除该日期的旧记录
            cursor.execute("DELETE FROM cp_history WHERE recorded_at = ?", (date,))

            # 按战力排序插入
            sorted_stocks = sorted(stocks, key=lambda x: x.get('total_cp', 0), reverse=True)
            for rank, stock in enumerate(sorted_stocks, 1):
                cursor.execute("""
                    INSERT INTO cp_history (
                        code, name, total_cp, growth_score, value_score,
                        quality_score, momentum_score, risk_score, rank, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stock.get('code'), stock.get('name'), stock.get('total_cp', 0),
                    stock.get('growth_score', 0), stock.get('value_score', 0),
                    stock.get('quality_score', 0), stock.get('momentum_score', 0),
                    stock.get('risk_score', 0), rank, date
                ))
            self.conn.commit()
            return len(sorted_stocks)

    def get_cp_history(self, code: str, days: int = 30) -> List[Dict]:
        """获取股票历史战力"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM cp_history
            WHERE code = ?
            ORDER BY recorded_at DESC
            LIMIT ?
        """, (code, days))
        return [dict(row) for row in cursor.fetchall()]

    def get_cp_history_by_date(self, date: str) -> List[Dict]:
        """获取指定日期的战力榜"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM cp_history
            WHERE recorded_at = ?
            ORDER BY rank
        """, (date,))
        return [dict(row) for row in cursor.fetchall()]

    def get_cp_changes(self, days: int = 7) -> List[Dict]:
        """获取战力变化显著的股票"""
        cursor = self.conn.cursor()

        # 获取最早和最晚的记录
        cursor.execute("""
            SELECT DISTINCT recorded_at FROM cp_history
            ORDER BY recorded_at DESC LIMIT ?
        """, (days,))

        dates = [row['recorded_at'] for row in cursor.fetchall()]
        if len(dates) < 2:
            return []

        oldest_date, latest_date = dates[-1], dates[0]

        cursor.execute("""
            SELECT h1.code, h1.name,
                   h2.total_cp as old_cp, h1.total_cp as new_cp,
                   h1.total_cp - h2.total_cp as change
            FROM cp_history h1
            JOIN cp_history h2 ON h1.code = h2.code
            WHERE h1.recorded_at = ? AND h2.recorded_at = ?
            ORDER BY change DESC
        """, (latest_date, oldest_date))

        return [dict(row) for row in cursor.fetchall()]

    # ==================== 预警操作（v17.2使用） ====================

    def get_alert_config(self, rule_type: str) -> Optional[Dict]:
        """获取预警配置"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM alert_config WHERE rule_type = ?", (rule_type,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def set_alert_config(self, rule_type: str, threshold: float, cooldown_hours: int = 24):
        """设置预警配置"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO alert_config (rule_type, threshold, cooldown_hours, updated_at)
                VALUES (?, ?, ?, ?)
            """, (rule_type, threshold, cooldown_hours, datetime.now().isoformat()))
            self.conn.commit()

    def create_alert(self, alert: Dict) -> int:
        """创建预警"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO alerts (
                    code, name, alert_type, level, title, message,
                    cp_before, cp_after, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.get('code'), alert.get('name'), alert.get('alert_type'),
                alert.get('level', 'warning'), alert.get('title'),
                alert.get('message'), alert.get('cp_before', 0),
                alert.get('cp_after', 0), alert.get('expires_at')
            ))
            self.conn.commit()
            return cursor.lastrowid

    def get_recent_alert(self, code: str, alert_type: str, hours: int = 24) -> Optional[Dict]:
        """检查最近是否有同类预警（用于去重）"""
        cursor = self.conn.cursor()
        since = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
        cursor.execute("""
            SELECT * FROM alerts
            WHERE code = ? AND alert_type = ?
            AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (code, alert_type, since))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_alerts(self, unread_only: bool = False, limit: int = 50) -> List[Dict]:
        """获取预警列表"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM alerts"
        if unread_only:
            query += " WHERE is_read = 0"
        query += " ORDER BY created_at DESC LIMIT ?"
        cursor.execute(query, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def mark_alert_read(self, alert_id: int):
        """标记预警已读"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,))
            self.conn.commit()

    def get_alert_summary(self) -> Dict:
        """获取预警汇总"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread,
                SUM(CASE WHEN level = 'danger' AND is_read = 0 THEN 1 ELSE 0 END) as danger_unread,
                SUM(CASE WHEN level = 'warning' AND is_read = 0 THEN 1 ELSE 0 END) as warning_unread
            FROM alerts
            WHERE created_at >= date('now')
        """)
        row = cursor.fetchone()
        return dict(row) if row else {'total': 0, 'unread': 0, 'danger_unread': 0, 'warning_unread': 0}

    # ==================== 配置操作 ====================

    def get_config(self, key: str) -> Optional[str]:
        """获取配置值"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else None

    def set_config(self, key: str, value: str):
        """设置配置值"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO config (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, datetime.now().isoformat()))
            self.conn.commit()

    # ==================== 迁移相关 ====================

    def get_schema_version(self) -> str:
        """获取当前数据库版本"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
        row = cursor.fetchone()
        return row['version'] if row else '0'

    def set_schema_version(self, version: str):
        """设置数据库版本"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            self.conn.commit()

    # ==================== 用户配置操作 ====================

    def get_user_profile(self) -> Dict:
        """获取用户配置"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM user_profile WHERE id = 1")
        row = cursor.fetchone()
        if row:
            result = dict(row)
            # 转换 allowed_boards 从字符串到列表
            if 'allowed_boards' in result and result['allowed_boards']:
                result['allowed_boards'] = result['allowed_boards'].split(',')
            else:
                result['allowed_boards'] = ['main']
            # 转换整数字段
            result['consider_dividend'] = bool(result.get('consider_dividend', 1))
            result['keep_cash_reserve'] = bool(result.get('keep_cash_reserve', 0))
            return result
        else:
            # 返回默认值
            return {
                'id': 1,
                'capital': 20000,
                'allowed_boards': ['main'],
                'risk_preference': 'aggressive',
                'consider_dividend': True,
                'keep_cash_reserve': False
            }

    def save_user_profile(self, profile: Dict) -> bool:
        """保存用户配置"""
        with self._write_lock:
            cursor = self.conn.cursor()
            # 转换 allowed_boards 为字符串
            boards = profile.get('allowed_boards', ['main'])
            if isinstance(boards, list):
                boards = ','.join(boards)

            cursor.execute("""
                INSERT OR REPLACE INTO user_profile (
                    id, capital, allowed_boards, risk_preference,
                    consider_dividend, keep_cash_reserve, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?)
            """, (
                profile.get('capital', 20000),
                boards,
                profile.get('risk_preference', 'aggressive'),
                int(profile.get('consider_dividend', True)),
                int(profile.get('keep_cash_reserve', False)),
                datetime.now().isoformat()
            ))
            self.conn.commit()
            return True

    def get_affordable_stocks_count(self, capital: float, boards: List[str]) -> int:
        """获取可买的股票数量（价格在资金可容纳一手以内的）"""
        cursor = self.conn.cursor()
        boards_str = ','.join([f"'{b}'" for b in boards])
        # 股票最小购买单位是1手=100股，所以价格<=capital/100的都可以买
        cursor.execute(f"""
            SELECT COUNT(*) as cnt FROM stocks
            WHERE price > 0 AND price * 100 <= ?
            AND board_type IN ({boards_str})
        """, (capital,))
        row = cursor.fetchone()
        return row['cnt'] if row else 0

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'conn'):
            self.conn.close()


# 全局数据库实例
_db_instance = None


def get_db() -> Database:
    """获取数据库单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
