"""
SQLite数据库模块 - Simulator Database
"""

import sqlite3
import json
import os
import threading
from datetime import datetime
from typing import List, Dict, Optional
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
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.row_factory = sqlite3.Row
            self._write_lock = threading.Lock()
            self._initialized = True
            self._create_tables()

    def _ensure_db_dir(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def _create_tables(self):
        with self._write_lock:
            cursor = self.conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    code TEXT PRIMARY KEY, name TEXT NOT NULL, price REAL DEFAULT 0,
                    pe REAL DEFAULT 0, roe REAL DEFAULT 0, net_profit_growth REAL DEFAULT 0,
                    revenue_growth REAL DEFAULT 0, change_pct REAL DEFAULT 0,
                    pb REAL DEFAULT 0, gross_margin REAL DEFAULT 0, revenue REAL DEFAULT 0,
                    cashflow REAL DEFAULT 0, debt_ratio REAL DEFAULT 0,
                    volume REAL DEFAULT 0, amount REAL DEFAULT 0, dividend_yield REAL DEFAULT 0,
                    market_cap REAL DEFAULT 0, high REAL DEFAULT 0, low REAL DEFAULT 0,
                    growth_score REAL DEFAULT 0, value_score REAL DEFAULT 0,
                    momentum_score REAL DEFAULT 0, quality_score REAL DEFAULT 0,
                    total_cp REAL DEFAULT 0, risk_score REAL DEFAULT 0,
                    risk_level TEXT DEFAULT '', peg REAL DEFAULT 0,
                    data_quality TEXT DEFAULT 'low', sector TEXT DEFAULT '',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cp_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL,
                    name TEXT NOT NULL, total_cp REAL DEFAULT 0,
                    growth_score REAL DEFAULT 0, value_score REAL DEFAULT 0,
                    quality_score REAL DEFAULT 0, momentum_score REAL DEFAULT 0,
                    risk_score REAL DEFAULT 0, rank INTEGER DEFAULT 0,
                    recorded_at TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_type TEXT NOT NULL UNIQUE, threshold REAL DEFAULT 10,
                    is_enabled INTEGER DEFAULT 1, cooldown_hours INTEGER DEFAULT 24,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, name TEXT,
                    alert_type TEXT NOT NULL, level TEXT DEFAULT 'warning',
                    title TEXT, message TEXT, cp_before REAL DEFAULT 0,
                    cp_after REAL DEFAULT 0, is_read INTEGER DEFAULT 0,
                    is_muted INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY, value TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    capital REAL DEFAULT 20000,
                    allowed_boards TEXT DEFAULT 'main',
                    risk_preference TEXT DEFAULT 'aggressive',
                    consider_dividend INTEGER DEFAULT 1,
                    keep_cash_reserve INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cash REAL DEFAULT 20000,
                    initial_cash REAL DEFAULT 20000,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS holding_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL, name TEXT NOT NULL,
                    quantity INTEGER NOT NULL, cost_price REAL NOT NULL,
                    bought_at TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL, name TEXT NOT NULL,
                    action TEXT NOT NULL, quantity INTEGER NOT NULL,
                    price REAL NOT NULL, commission REAL NOT NULL,
                    stamp_tax REAL DEFAULT 0, transfer_fee REAL NOT NULL,
                    total_amount REAL NOT NULL, recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_cooldown (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    last_traded_at TEXT NOT NULL, cooldown_days INTEGER DEFAULT 5
                )
            """)

            # 委托单表 v19.1
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL, name TEXT NOT NULL,
                    action TEXT NOT NULL, order_type TEXT NOT NULL,
                    price REAL NOT NULL, quantity INTEGER NOT NULL,
                    filled_quantity INTEGER DEFAULT 0, filled_price REAL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    frozen_amount REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    filled_at TEXT,
                    cancel_reason TEXT
                )
            """)

            # 资金流水表 v19.1
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_flow (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    change_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    balance_after REAL NOT NULL,
                    order_id INTEGER,
                    remark TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 持仓快照表 v19.7（每日收盘后记录，用于回测验证）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS holding_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT,
                    quantity INTEGER,
                    cost_price REAL,
                    close_price REAL,
                    market_value REAL,
                    profit REAL,
                    profit_pct REAL,
                    cp REAL,
                    batch_id INTEGER,
                    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, code, batch_id)
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_date ON cp_history(recorded_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_code ON cp_history(code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_date_code ON cp_history(recorded_at, code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_unread ON alerts(is_read, created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_code ON alerts(code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_holdings_code ON holding_batches(code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_recorded_at ON trades(recorded_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_flow_type ON account_flow(change_type, created_at)")

            # 持仓快照索引 v19.7
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_date ON holding_snapshots(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_code ON holding_snapshots(code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_date_code ON holding_snapshots(date, code)")

            self.conn.commit()

    @contextmanager
    def get_cursor(self):
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
                stock.get('data_quality', 'low'), datetime.now().isoformat()
            ))
            self.conn.commit()

    def batch_upsert_stocks(self, stocks: List[Dict]):
        with self._write_lock:
            cursor = self.conn.cursor()
            data = [
                (s.get('code'), s.get('name'), s.get('price', 0),
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
                 s.get('data_quality', 'low'), s.get('sector', ''),
                 datetime.now().isoformat()
                ) for s in stocks
            ]
            cursor.executemany("""
                INSERT OR REPLACE INTO stocks (
                    code, name, price, pe, roe, net_profit_growth, revenue_growth,
                    change_pct, pb, gross_margin, revenue, cashflow, debt_ratio,
                    volume, amount, dividend_yield, market_cap, high, low,
                    growth_score, value_score, momentum_score, quality_score,
                    total_cp, risk_score, risk_level, peg, data_quality, sector,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            self.conn.commit()
            return cursor.rowcount

    def get_stock(self, code: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM stocks WHERE code = ?", (code,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_stocks(self) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM stocks ORDER BY total_cp DESC")
        return [dict(row) for row in cursor.fetchall()]

    def get_top_stocks(self, limit: int = 50) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM stocks ORDER BY total_cp DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # ==================== 战力历史操作 ====================

    def record_cp_history(self, stocks: List[Dict], date: str = None):
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM cp_history WHERE recorded_at = ?", (date,))
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
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM cp_history WHERE code = ?
            ORDER BY recorded_at DESC LIMIT ?
        """, (code, days))
        return [dict(row) for row in cursor.fetchall()]

    def get_cp_history_by_date(self, date: str) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM cp_history WHERE recorded_at = ?
            ORDER BY rank
        """, (date,))
        return [dict(row) for row in cursor.fetchall()]

    def get_cp_changes(self, days: int = 7) -> List[Dict]:
        cursor = self.conn.cursor()
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

    # ==================== 预警操作 ====================

    def get_alert_config(self, rule_type: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM alert_config WHERE rule_type = ?", (rule_type,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def set_alert_config(self, rule_type: str, threshold: float, cooldown_hours: int = 24):
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO alert_config (rule_type, threshold, cooldown_hours, updated_at)
                VALUES (?, ?, ?, ?)
            """, (rule_type, threshold, cooldown_hours, datetime.now().isoformat()))
            self.conn.commit()

    def create_alert(self, alert: Dict) -> int:
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
        cursor = self.conn.cursor()
        since = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
        cursor.execute("""
            SELECT * FROM alerts
            WHERE code = ? AND alert_type = ?
            AND created_at >= ?
            ORDER BY created_at DESC LIMIT 1
        """, (code, alert_type, since))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_alerts(self, unread_only: bool = False, limit: int = 50) -> List[Dict]:
        cursor = self.conn.cursor()
        query = "SELECT * FROM alerts"
        if unread_only:
            query += " WHERE is_read = 0"
        query += " ORDER BY created_at DESC LIMIT ?"
        cursor.execute(query, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def mark_alert_read(self, alert_id: int):
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,))
            self.conn.commit()

    def get_alert_summary(self) -> Dict:
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
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else None

    def set_config(self, key: str, value: str):
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)
            """, (key, value, datetime.now().isoformat()))
            self.conn.commit()

    def get_schema_version(self) -> str:
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
        row = cursor.fetchone()
        return row['version'] if row else '0'

    def set_schema_version(self, version: str):
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            self.conn.commit()

    # ==================== 用户配置操作 ====================

    def get_user_profile(self) -> Dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM user_profile WHERE id = 1")
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if 'allowed_boards' in result and result['allowed_boards']:
                result['allowed_boards'] = result['allowed_boards'].split(',')
            else:
                result['allowed_boards'] = ['main']
            result['consider_dividend'] = bool(result.get('consider_dividend', 1))
            result['keep_cash_reserve'] = bool(result.get('keep_cash_reserve', 0))
            return result
        else:
            return {
                'id': 1, 'capital': 20000, 'allowed_boards': ['main'],
                'risk_preference': 'aggressive', 'consider_dividend': True,
                'keep_cash_reserve': False
            }

    def save_user_profile(self, profile: Dict) -> bool:
        with self._write_lock:
            cursor = self.conn.cursor()
            boards = profile.get('allowed_boards', ['main'])
            if isinstance(boards, list):
                boards = ','.join(boards)
            cursor.execute("""
                INSERT OR REPLACE INTO user_profile (
                    id, capital, allowed_boards, risk_preference,
                    consider_dividend, keep_cash_reserve, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?)
            """, (
                profile.get('capital', 20000), boards,
                profile.get('risk_preference', 'aggressive'),
                int(profile.get('consider_dividend', True)),
                int(profile.get('keep_cash_reserve', False)),
                datetime.now().isoformat()
            ))
            self.conn.commit()
            return True

    def get_affordable_stocks_count(self, capital: float, boards: List[str]) -> int:
        cursor = self.conn.cursor()
        boards_str = ','.join([f"'{b}'" for b in boards])
        cursor.execute(f"""
            SELECT COUNT(*) as cnt FROM stocks
            WHERE price > 0 AND price * 100 <= ?
            AND board_type IN ({boards_str})
        """, (capital,))
        row = cursor.fetchone()
        return row['cnt'] if row else 0

    # ==================== 模拟账户操作 ====================

    def get_account(self) -> Dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM account WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return dict(row)
        else:
            self.init_account()
            return {
                'id': 1, 'cash': 20000, 'initial_cash': 20000,
                'updated_at': datetime.now().isoformat()
            }

    def init_account(self):
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO account (id, cash, initial_cash, updated_at)
                VALUES (1, 20000, 20000, ?)
            """, (datetime.now().isoformat(),))
            self.conn.commit()

    def update_account(self, cash: float) -> bool:
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE account SET cash = ?, updated_at = ? WHERE id = 1
            """, (cash, datetime.now().isoformat()))
            self.conn.commit()
            return cursor.rowcount > 0

    # ==================== 模拟持仓操作 ====================

    def get_holdings(self) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT code, name, SUM(quantity) as total_quantity,
                   SUM(quantity * cost_price) / SUM(quantity) as avg_cost_price,
                   MIN(bought_at) as earliest_bought_at,
                   MAX(bought_at) as latest_bought_at
            FROM holding_batches
            GROUP BY code
            HAVING SUM(quantity) > 0
            ORDER BY latest_bought_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_holding(self, code: str) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT code, name, SUM(quantity) as total_quantity,
                   SUM(quantity * cost_price) / SUM(quantity) as avg_cost_price,
                   MIN(bought_at) as earliest_bought_at,
                   MAX(bought_at) as latest_bought_at
            FROM holding_batches
            WHERE code = ?
            GROUP BY code
        """, (code,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def add_holding_batch(self, code: str, name: str, quantity: int, cost_price: float, bought_at: str = None) -> int:
        with self._write_lock:
            cursor = self.conn.cursor()
            if bought_at is None:
                bought_at = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO holding_batches (code, name, quantity, cost_price, bought_at)
                VALUES (?, ?, ?, ?, ?)
            """, (code, name, quantity, cost_price, bought_at))
            self.conn.commit()
            return cursor.lastrowid

    def get_holding_batches(self, code: str) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM holding_batches
            WHERE code = ? AND quantity > 0
            ORDER BY bought_at ASC
        """, (code,))
        return [dict(row) for row in cursor.fetchall()]

    def get_holding_batches_for_sell(self, code: str) -> List[Dict]:
        cursor = self.conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT * FROM holding_batches
            WHERE code = ? AND quantity > 0 AND date(bought_at) < ?
            ORDER BY bought_at ASC
        """, (code, today))
        return [dict(row) for row in cursor.fetchall()]

    def get_today_bought_quantity(self, code: str) -> int:
        cursor = self.conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT COALESCE(SUM(quantity), 0) as qty FROM holding_batches
            WHERE code = ? AND date(bought_at) = ?
        """, (code, today))
        row = cursor.fetchone()
        return row['qty'] if row else 0

    def get_today_date(self) -> str:
        """获取今日日期字符串"""
        return datetime.now().strftime("%Y-%m-%d")

    def reduce_holding_batch(self, batch_id: int, reduce_qty: int) -> bool:
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE holding_batches SET quantity = quantity - ? WHERE id = ?
            """, (reduce_qty, batch_id))
            self.conn.commit()
            cursor.execute("DELETE FROM holding_batches WHERE quantity <= 0")
            self.conn.commit()
            return cursor.rowcount > 0

    def delete_holding_batch(self, batch_id: int) -> bool:
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM holding_batches WHERE id = ?", (batch_id,))
            self.conn.commit()
            return cursor.rowcount > 0

    def delete_all_holdings(self) -> bool:
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM holding_batches")
            self.conn.commit()
            return True

    # ==================== 交易记录操作 ====================

    def record_trade(self, trade: Dict) -> int:
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trades (
                    code, name, action, quantity, price,
                    commission, stamp_tax, transfer_fee, total_amount, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.get('code'), trade.get('name'), trade.get('action'),
                trade.get('quantity'), trade.get('price'),
                trade.get('commission', 0), trade.get('stamp_tax', 0),
                trade.get('transfer_fee', 0), trade.get('total_amount'),
                datetime.now().isoformat()
            ))
            self.conn.commit()
            return cursor.lastrowid

    def get_trades(self, limit: int = 50) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM trades ORDER BY recorded_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # ==================== 交易冷却追踪 ====================

    def update_trade_cooldown(self, code: str, cooldown_days: int = 5) -> None:
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO trade_cooldown (code, last_traded_at, cooldown_days)
                VALUES (?, ?, ?)
            """, (code, datetime.now().isoformat(), cooldown_days))
            self.conn.commit()

    def get_trade_cooldown(self, code: str) -> Dict:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM trade_cooldown WHERE code = ?", (code,))
        row = cursor.fetchone()
        if not row:
            return {'code': code, 'on_cooldown': False, 'days_remaining': 0}
        row = dict(row)
        last_traded = datetime.fromisoformat(row['last_traded_at'])
        days_since = (datetime.now() - last_traded).days
        days_remaining = max(0, row['cooldown_days'] - days_since)
        row['on_cooldown'] = days_remaining > 0
        row['days_remaining'] = days_remaining
        row['days_since_traded'] = days_since
        return row

    def is_on_cooldown(self, code: str) -> bool:
        cooldown = self.get_trade_cooldown(code)
        return cooldown.get('on_cooldown', False)

    # ==================== 委托单操作 v19.1 ====================

    def create_order(self, order: Dict) -> int:
        """创建委托单"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO orders (
                    code, name, action, order_type, price, quantity,
                    filled_quantity, filled_price, status, frozen_amount,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'pending', ?, ?, ?)
            """, (
                order.get('code'), order.get('name'),
                order.get('action'), order.get('order_type'),
                order.get('price'), order.get('quantity'),
                order.get('frozen_amount', 0),
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            self.conn.commit()
            return cursor.lastrowid

    def update_order_status(self, order_id: int, status: str,
                            filled_quantity: int = None, filled_price: float = None,
                            cancel_reason: str = None) -> bool:
        """更新委托单状态"""
        with self._write_lock:
            cursor = self.conn.cursor()
            now = datetime.now().isoformat()

            if filled_quantity is not None and filled_price is not None:
                cursor.execute("""
                    UPDATE orders SET
                        status = ?, filled_quantity = ?, filled_price = ?,
                        updated_at = ?, filled_at = ?
                    WHERE id = ?
                """, (status, filled_quantity, filled_price, now, now, order_id))
            elif cancel_reason:
                cursor.execute("""
                    UPDATE orders SET
                        status = ?, cancel_reason = ?, updated_at = ?
                    WHERE id = ?
                """, (status, cancel_reason, now, order_id))
            else:
                cursor.execute("""
                    UPDATE orders SET status = ?, updated_at = ? WHERE id = ?
                """, (status, now, order_id))
            self.conn.commit()
            return cursor.rowcount > 0

    def get_order(self, order_id: int) -> Optional[Dict]:
        """获取委托单"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_pending_orders(self, code: str = None) -> List[Dict]:
        """获取待成交委托"""
        cursor = self.conn.cursor()
        if code:
            cursor.execute("""
                SELECT * FROM orders
                WHERE status = 'pending' AND code = ?
                ORDER BY created_at ASC
            """, (code,))
        else:
            cursor.execute("""
                SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at ASC
            """)
        return [dict(row) for row in cursor.fetchall()]

    def get_order_history(self, limit: int = 50) -> List[Dict]:
        """获取委托历史"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM orders ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def cancel_order(self, order_id: int, reason: str = "用户撤单") -> bool:
        """撤销委托单"""
        order = self.get_order(order_id)
        if not order or order['status'] != 'pending':
            return False
        return self.update_order_status(order_id, 'cancelled', cancel_reason=reason)

    # ==================== 资金流水操作 v19.1 ====================

    def record_flow(self, flow: Dict) -> int:
        """记录资金流水"""
        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO account_flow (
                    change_type, amount, balance_after, order_id, remark, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                flow.get('change_type'),
                flow.get('amount', 0),
                flow.get('balance_after', 0),
                flow.get('order_id'),
                flow.get('remark', ''),
                datetime.now().isoformat()
            ))
            self.conn.commit()
            return cursor.lastrowid

    def get_account_flows(self, limit: int = 100) -> List[Dict]:
        """获取资金流水"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM account_flow ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # ==================== 持仓快照操作 v19.7 ====================

    def record_holding_snapshot(
        self,
        date: str,
        code: str,
        name: str,
        quantity: int,
        cost_price: float,
        close_price: float,
        cp: float = 0,
        batch_id: int = None
    ) -> int:
        """记录单只股票的持仓快照 v19.7

        Args:
            date: 快照日期
            code: 股票代码
            name: 股票名称
            quantity: 持股数量
            cost_price: 成本价
            close_price: 收盘价
            cp: 当日战力（可选）
            batch_id: 持仓批次ID（可选）

        Returns:
            快照记录ID
        """
        market_value = quantity * close_price
        cost_total = quantity * cost_price
        profit = market_value - cost_total
        profit_pct = (profit / cost_total * 100) if cost_total > 0 else 0

        with self._write_lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO holding_snapshots (
                    date, code, name, quantity, cost_price, close_price,
                    market_value, profit, profit_pct, cp, batch_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date, code, name, quantity, cost_price, close_price,
                market_value, profit, profit_pct, cp, batch_id
            ))
            self.conn.commit()
            return cursor.lastrowid

    def record_daily_holding_snapshots(self, date: str = None, stocks_data: Dict = None) -> int:
        """每日收盘后记录所有持仓快照 v19.7

        Args:
            date: 快照日期，默认今日
            stocks_data: 股票数据缓存 {code: {price, cp}}，用于获取最新价和战力

        Returns:
            记录的快照数量
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # 获取当前持仓（含批次）
        holdings = self.get_holdings()
        if not holdings:
            return 0

        count = 0
        for holding in holdings:
            code = holding['code']
            name = holding['name']
            quantity = holding['total_quantity']
            cost_price = holding['avg_cost_price']

            # 获取收盘价
            close_price = 0
            cp = 0
            if stocks_data and code in stocks_data:
                close_price = stocks_data[code].get('price', 0)
                cp = stocks_data[code].get('total_cp', 0)
            else:
                # 从stocks表获取最新价
                stock = self.get_stock(code)
                if stock:
                    close_price = stock.get('price', 0)
                    cp = stock.get('total_cp', 0)

            if close_price > 0:
                self.record_holding_snapshot(
                    date=date,
                    code=code,
                    name=name,
                    quantity=quantity,
                    cost_price=cost_price,
                    close_price=close_price,
                    cp=cp
                )
                count += 1

        return count

    def get_holding_snapshots(
        self,
        code: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """获取持仓快照历史 v19.7

        Args:
            code: 股票代码（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            limit: 返回条数限制

        Returns:
            快照列表
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM holding_snapshots WHERE 1=1"
        params = []

        if code:
            query += " AND code = ?"
            params.append(code)
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC, code LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_snapshot_by_date(self, date: str) -> List[Dict]:
        """获取指定日期的持仓快照 v19.7

        Args:
            date: 日期

        Returns:
            快照列表
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM holding_snapshots
            WHERE date = ?
            ORDER BY profit DESC
        """, (date,))
        return [dict(row) for row in cursor.fetchall()]

    def get_portfolio_value_history(
        self,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """获取每日持仓市值历史 v19.7

        Returns:
            [{date, total_value, total_cost, total_profit, profit_pct}, ...]
        """
        cursor = self.conn.cursor()
        query = """
            SELECT
                date,
                SUM(market_value) as total_value,
                SUM(quantity * cost_price) as total_cost,
                SUM(profit) as total_profit
            FROM holding_snapshots
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " GROUP BY date ORDER BY date"

        cursor.execute(query, params)
        results = []
        for row in cursor.fetchall():
            r = dict(row)
            cost = r.get('total_cost', 0) or 0
            profit = r.get('total_profit', 0) or 0
            r['profit_pct'] = (profit / cost * 100) if cost > 0 else 0
            results.append(r)
        return results

    def close(self):
        if hasattr(self, 'conn'):
            self.conn.close()


_db_instance = None


def get_db() -> Database:
    """获取数据库单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
