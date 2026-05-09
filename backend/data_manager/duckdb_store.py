"""
DuckDB历史行情存储 - DuckDB Historical Price Store
===================================================
职责：存储和查询海量历史行情数据（日K线、分钟K线）

为什么用DuckDB：
- SQLite单表超百万行后性能衰减
- DuckDB是嵌入式列存，分析查询极快
- 容量无上限，可处理千万行级别数据

存储分层：
- SQLite: 用户业务数据（持仓、交易、战力历史）
- DuckDB: 海量行情历史数据（日K线、分钟K线）

支持的数据量：
- daily_kline: 2500万行（5年×5000股）
- minute_kline: 7.5亿行（3年×）
"""

import sqlite3
import duckdb
import json
import logging
import fcntl
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import threading
import pandas as pd

logger = logging.getLogger(__name__)


# ==================== 路径
from backend.config import DATA_DIR, DUCKDB_PATH, SQLITE_PATH

# ==================== 数据类 ====================

@dataclass
class KlineRecord:
    """K线记录"""
    code: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0
    change_pct: float = 0.0
    adj_close: float = 0.0
    adj_factor: float = 1.0  # 复权因子


@dataclass
class QueryResult:
    """查询结果"""
    success: bool
    data: Optional[pd.DataFrame] = None
    row_count: int = 0
    error: Optional[str] = None

    def __len__(self) -> int:
        if self.data is not None:
            return len(self.data)
        return self.row_count

    def __getitem__(self, key):
        if self.data is not None:
            return self.data[key]
        raise IndexError("QueryResult has no data")


# ==================== 代码规范化 ====================

def normalize_code(code: str) -> str:
    """将带前缀的股票代码标准化为纯数字格式

    Args:
        code: 股票代码，支持 sh600000、sz000001、600000 等格式

    Returns:
        纯数字代码，如 600000、000001
    """
    if code is None:
        return code
    code = str(code).strip().upper()
    if code.startswith('SH'):
        return code[2:]
    elif code.startswith('SZ'):
        return code[2:]
    return code


# ==================== DuckDB管理器 ====================

class DuckDBStore:
    """
    DuckDB历史行情存储管理器

    功能：
    1. 创建/管理K线表
    2. 插入/批量插入K线数据
    3. 按代码和日期范围查询
    4. 聚合查询（均线等）
    5. 数据统计
    """

    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or DUCKDB_PATH)
        self._lock = threading.Lock()
        self._lock_path = self.db_path + ".lock"

        # 单连接复用（跨进程文件锁保护）
        self._write_conn = None
        self._read_conn = None
        self._conn_lock = threading.Lock()  # 保护连接创建

        self._ensure_tables()

    def _acquire_lock(self, exclusive: bool = True):
        """获取文件锁（跨进程互斥）"""
        lock_fd = open(self._lock_path, 'w')
        lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(lock_fd.fileno(), lock_type)
        return lock_fd

    def _release_lock(self, lock_fd):
        """释放文件锁"""
        if lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        """获取写连接（单例，复用）"""
        if self._write_conn is None:
            with self._conn_lock:
                if self._write_conn is None:
                    self._write_conn = duckdb.connect(self.db_path, read_only=False)
        return self._write_conn

    def _get_read_conn(self) -> duckdb.DuckDBPyConnection:
        """获取读连接（单例，复用）

        尝试 read_only=False，失败时自动降级为 read_only=True（当另一个进程持有写锁时）
        """
        if self._read_conn is None:
            with self._conn_lock:
                if self._read_conn is None:
                    try:
                        self._read_conn = duckdb.connect(self.db_path, read_only=False)
                        self._read_conn.execute("SET threads=1")
                    except duckdb.IOException:
                        # 另一个进程持有写锁，降级为只读
                        self._read_conn = duckdb.connect(self.db_path, read_only=True)
                        self._read_conn.execute("SET threads=1")
        return self._read_conn

    def _migrate_columns(self, conn):
        """
        迁移：检查并添加缺失的列

        用于已有表结构升级，添加新版本新增的列
        """
        # 需要添加到 daily_kline 表的列
        required_columns = {
            'adj_factor': 'DECIMAL(10, 6) DEFAULT 1.0',
        }

        try:
            # 获取当前表的所有列
            result = conn.execute("DESCRIBE daily_kline").fetchall()
            existing_columns = {row[0] for row in result}

            # 添加缺失的列
            for col_name, col_type in required_columns.items():
                if col_name not in existing_columns:
                    try:
                        conn.execute(f"ALTER TABLE daily_kline ADD COLUMN {col_name} {col_type}")
                        print(f"Migration: Added column {col_name} to daily_kline")
                    except Exception as e:
                        print(f"Migration warning: Could not add column {col_name}: {e}")
        except Exception as e:
            print(f"Migration warning: Could not check columns: {e}")

    def checkpoint(self):
        """强制checkpoint，确保所有写操作刷新到磁盘"""
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=True)
            conn = self._get_conn()
            conn.execute("CHECKPOINT")
        except Exception as e:
            print(f"Checkpoint warning: {e}")
        finally:
            self._release_lock(lock_fd)

    def _ensure_tables(self):
        """确保表存在"""
        # 如果数据库已被锁定（另一个进程持有写锁），跳过表创建
        # 因为只读连接无法执行DDL，这只在首次初始化时需要
        try:
            # 注意：这里不使用 with self._get_conn() 因为 _ensure_tables 在 __init__ 中调用，
            # 此时 singleton 连接还未创建，我们需要在初始化后保持连接可用
            conn = self._get_conn()

            # 日K线表
            conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS kline_id START 1
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_kline (
                    id BIGINT DEFAULT nextval('kline_id'),
                    code VARCHAR(6) NOT NULL,
                    trade_date DATE NOT NULL,
                    open DECIMAL(10, 2) NOT NULL,
                    high DECIMAL(10, 2) NOT NULL,
                    low DECIMAL(10, 2) NOT NULL,
                    close DECIMAL(10, 2) NOT NULL,
                    volume BIGINT NOT NULL,
                    amount DECIMAL(20, 2) DEFAULT 0,
                    change_pct DECIMAL(10, 2) DEFAULT 0,
                    adj_close DECIMAL(10, 2) DEFAULT 0,
                    adj_factor DECIMAL(10, 6) DEFAULT 1.0,  -- 复权因子
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, trade_date)
                )
            """)

            # 迁移：检查并添加缺失的列（针对已存在的表）
            self._migrate_columns(conn)

            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_code_date
                ON daily_kline(code, trade_date DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_date
                ON daily_kline(trade_date DESC)
            """)

            # 迁移：检查并添加缺失的列
            self._migrate_columns(conn)

            # 分钟K线表（预留）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS minute_kline (
                    id BIGINT DEFAULT nextval('kline_id'),
                    code VARCHAR(6) NOT NULL,
                    trade_date DATE NOT NULL,
                    trade_time TIMESTAMP NOT NULL,
                    open DECIMAL(10, 2) NOT NULL,
                    high DECIMAL(10, 2) NOT NULL,
                    low DECIMAL(10, 2) NOT NULL,
                    close DECIMAL(10, 2) NOT NULL,
                    volume BIGINT NOT NULL,
                    amount DECIMAL(20, 2) DEFAULT 0,
                    interval_type VARCHAR(10) DEFAULT '1min',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, trade_time, interval_type)
                )
            """)
        except (duckdb.IOException, OSError) as e:
            if "Could not set lock" in str(e) or "locked" in str(e).lower():
                print(f"[DuckDB] 数据库被锁定 ({e})，跳过表创建（表可能已存在）")
            else:
                raise
        except Exception as e:
            # 其他异常打印但不阻止初始化
            print(f"[DuckDB] 表创建警告: {e}")

    def insert_daily_kline(self, record: KlineRecord) -> bool:
        """插入单条日K线"""
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=True)
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO daily_kline
                (code, trade_date, open, high, low, close, volume, amount, change_pct, adj_close, adj_factor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.code,
                record.trade_date,
                record.open,
                record.high,
                record.low,
                record.close,
                record.volume,
                record.amount,
                record.change_pct,
                record.adj_close,
                getattr(record, 'adj_factor', 1.0),
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Insert daily kline error: {e}")
            return False
        finally:
            self._release_lock(lock_fd)

    def insert_daily_klines_batch(self, records: List[KlineRecord], batch_size: int = 1000) -> Tuple[int, int]:
        """
        批量插入日K线（优化版）

        优化点：
        1. 每1000条提交一次（减少事务大小）
        2. 使用 executemany 批量处理提高性能
        3. 单次提交减少IO次数

        Args:
            records: K线记录列表
            batch_size: 每批提交数量

        Returns:
            (success_count, error_count)
        """
        if not records:
            return 0, 0

        total_success = 0
        total_errors = 0
        lock_fd = None

        try:
            lock_fd = self._acquire_lock(exclusive=True)
            conn = self._get_conn()

            # SQL语句
            sql = """
                INSERT OR REPLACE INTO daily_kline
                (code, trade_date, open, high, low, close, volume, amount, change_pct, adj_close, adj_factor)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            # 分批处理
            for batch_start in range(0, len(records), batch_size):
                batch_end = min(batch_start + batch_size, len(records))
                batch = records[batch_start:batch_end]

                # 准备批量数据
                batch_data = [
                    (
                        r.code, r.trade_date, r.open, r.high, r.low, r.close,
                        r.volume, r.amount, r.change_pct, r.adj_close,
                        getattr(r, 'adj_factor', 1.0),
                    )
                    for r in batch
                ]

                try:
                    # 使用 executemany 批量插入
                    conn.executemany(sql, batch_data)
                    total_success += len(batch)
                except Exception as e:
                    # 如果批量失败，尝试逐条插入
                    for r in batch:
                        try:
                            conn.execute(sql, (
                                r.code, r.trade_date, r.open, r.high, r.low, r.close,
                                r.volume, r.amount, r.change_pct, r.adj_close,
                                getattr(r, 'adj_factor', 1.0),
                            ))
                            total_success += 1
                        except Exception as e:
                            print(f"insert_klines error for {r.code} on {r.trade_date}: {e}")
                            total_errors += 1

            # 提交事务
            conn.commit()

        except Exception as e:
            return 0, len(records)
        finally:
            self._release_lock(lock_fd)

        return total_success, total_errors

    def insert_from_dataframe(self, df: pd.DataFrame, table: str = 'daily_kline') -> int:
        """
        从DataFrame批量插入

        Args:
            df: 必须包含 code, trade_date, open, high, low, close, volume 字段
            table: 表名（白名单验证）

        Returns:
            插入行数
        """
        # 白名单验证，防止 SQL 注入
        ALLOWED_TABLES = {'daily_kline', 'minute_kline', 'trade_cal', 'ex_right_factor'}
        if table not in ALLOWED_TABLES:
            print(f"Insert from DataFrame error: Invalid table name: {table}")
            return 0

        if df.empty:
            return 0

        required = ['code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=True)
            conn = self._get_conn()
            # 先删除已存在的记录
            unique_codes = df['code'].unique().tolist()
            if unique_codes:
                placeholders = ','.join(['?' for _ in unique_codes])
                conn.execute(f"DELETE FROM {table} WHERE code IN ({placeholders})", unique_codes)

            # 批量插入
            conn.execute(f"INSERT INTO {table} BY NAME SELECT * FROM df")
            return len(df)
        except Exception as e:
            print(f"Insert from DataFrame error: {e}")
            return 0
        finally:
            self._release_lock(lock_fd)

    def get_klines(
        self,
        code: str,
        start_date: str = None,
        end_date: str = None,
        limit: int = 1000
    ) -> QueryResult:
        """
        查询K线数据

        Args:
            code: 股票代码（支持 sh600000、sz000001、600000 等格式，内部自动标准化）
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 返回条数限制

        Returns:
            QueryResult with DataFrame
        """
        code = normalize_code(code)  # 标准化代码格式
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)  # 共享锁
            # 使用读连接（写连接也可读，但读连接有 threads=1 优化且语义更清晰）
            conn = self._get_read_conn()
            sql = "SELECT * FROM daily_kline WHERE code = ?"
            params = [code]

            if start_date:
                sql += " AND trade_date >= ?"
                params.append(start_date)

            if end_date:
                sql += " AND trade_date <= ?"
                params.append(end_date)

            # 返回 ASC 顺序（方便consumer直接使用）
            sql += " ORDER BY trade_date ASC, id ASC LIMIT ?"
            params.append(limit)

            df = conn.execute(sql, params).df()

            return QueryResult(
                success=True,
                data=df,
                row_count=len(df)
            )
        except Exception as e:
            logger.warning(f"get_klines 查询失败 code={code}: {e}")
            return QueryResult(success=False, error=str(e))
        finally:
            self._release_lock(lock_fd)

    def get_date_range(self, code: str) -> Tuple[Optional[str], Optional[str]]:
        """
        获取某股票已有数据的日期范围（最小/最大日期）。

        Args:
            code: 股票代码（支持 sh600000、sz000001、600000 等格式，内部自动标准化）

        Returns:
            (min_date, max_date) 格式为 YYYY-MM-DD 字符串，或 (None, None)
        """
        code = normalize_code(code)  # 标准化代码格式
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            row = conn.execute(
                "SELECT MIN(trade_date), MAX(trade_date) FROM daily_kline WHERE code = ?",
                [code]
            ).fetchone()
            if row and row[0] and row[1]:
                return str(row[0]), str(row[1])
            return None, None
        except Exception as e:
            print(f"get_kline_date_range error for {code}: {e}")
            return None, None
        finally:
            self._release_lock(lock_fd)

    def get_klines_bulk(self, codes: List[str], days: int = 60) -> Dict[str, pd.DataFrame]:
        """批量获取多只股票的K线数据（单次连接）

        相比逐只调用 get_klines()，避免了大量连接创建开销，
        适合预测引擎等需要全市场数据的场景。

        Args:
            codes: 股票代码列表
            days: 最近N天

        Returns:
            Dict[code -> DataFrame]
        """
        if not codes:
            return {}
        codes = [normalize_code(c) for c in codes]  # 标准化代码格式
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            placeholders = ','.join(['?' for _ in codes])
            sql = f"""
                SELECT * FROM daily_kline
                WHERE code IN ({placeholders})
                  AND trade_date >= ?
                  AND trade_date <= ?
                ORDER BY code, trade_date ASC
            """
            params = list(codes) + [start_date, end_date]
            df = conn.execute(sql, params).df()

            result: Dict[str, pd.DataFrame] = {}
            if not df.empty:
                for code, group in df.groupby('code'):
                    result[code] = group.reset_index(drop=True)
            return result
        except Exception as e:
            print(f"get_klines_bulk error: {e}")
            return {}
        finally:
            self._release_lock(lock_fd)

    def get_klines_bulk_for_date(
        self, codes: List[str], end_date: str, days: int = 70
    ) -> Dict[str, pd.DataFrame]:
        """批量获取多只股票在指定日期范围内的K线数据 v19.9

        用于历史战力计算，避免逐只查询造成的N+1问题。

        Args:
            codes: 股票代码列表
            end_date: 结束日期 (YYYY-MM-DD)
            days: 获取多少天的数据

        Returns:
            Dict[code -> DataFrame]
        """
        if not codes:
            return {}
        # 处理 DuckDB Timestamp 类型
        if hasattr(end_date, 'strftime'):
            end_date = end_date.strftime('%Y-%m-%d')
        codes = [normalize_code(c) for c in codes]  # 标准化代码格式
        from datetime import datetime, timedelta
        start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            placeholders = ','.join(['?' for _ in codes])
            sql = f"""
                SELECT * FROM daily_kline
                WHERE code IN ({placeholders})
                  AND trade_date >= ?
                  AND trade_date <= ?
                ORDER BY code, trade_date ASC
            """
            params = list(codes) + [start_date, end_date]
            df = conn.execute(sql, params).df()

            result: Dict[str, pd.DataFrame] = {}
            if not df.empty:
                for code, group in df.groupby('code'):
                    result[code] = group.reset_index(drop=True)
            return result
        except Exception as e:
            print(f"get_klines_bulk_for_date error: {e}")
            return {}
        finally:
            self._release_lock(lock_fd)

    def get_avg_daily_amount_20d_bulk(
        self, codes: List[str], chunk_size: int = 400
    ) -> Dict[str, float]:
        """
        批量计算近 20 个交易日日均成交额（元，与 daily_kline.amount 一致）。

        用于股票池初始化/再平衡时填充 daily_volume_20d（万元 = 本返回值 / 10000）。
        """
        result: Dict[str, float] = {}
        if not codes:
            return result
        codes = [normalize_code(c) for c in codes]  # 标准化代码格式
        unique = list({str(c).strip() for c in codes if c})
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            for i in range(0, len(unique), chunk_size):
                chunk = unique[i : i + chunk_size]
                placeholders = ",".join(["?" for _ in chunk])
                sql = f"""
                    SELECT code, AVG(amount) AS avg_amt
                    FROM (
                        SELECT code, amount,
                            ROW_NUMBER() OVER (
                                PARTITION BY code ORDER BY trade_date DESC, id DESC
                            ) AS rn
                        FROM daily_kline
                        WHERE code IN ({placeholders})
                    ) t
                    WHERE rn <= 20
                    GROUP BY code
                """
                rows = conn.execute(sql, chunk).fetchall()
                for row in rows:
                    if row[0] is not None:
                        result[str(row[0])] = float(row[1] or 0)
            return result
        except Exception as e:
            logger.debug("get_avg_daily_amount_20d_bulk failed: %s", e)
            return result
        finally:
            self._release_lock(lock_fd)

    def get_latest_kline(self, code: str) -> Optional[Dict]:
        """获取最新一条K线"""
        code = normalize_code(code)  # 标准化代码格式
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            df = conn.execute("""
                SELECT * FROM daily_kline
                WHERE code = ?
                ORDER BY trade_date DESC, id DESC
                LIMIT 1
            """, [code]).df()

            if df.empty:
                return None

            return df.iloc[0].to_dict()
        except Exception as e:
            print(f"get_latest_kline error for {code}: {e}")
            return None
        finally:
            self._release_lock(lock_fd)

    def get_ma(
        self,
        code: str,
        days: int = 5,
        end_date: str = None,
        field: str = 'close'
    ) -> QueryResult:
        """
        计算均线

        Args:
            code: 股票代码
            days: 均线天数
            end_date: 计算截止日期
            field: 计算字段（白名单验证）

        Returns:
            QueryResult: 包含均线DataFrame（列：ma）/ 空数据时success=False
        """
        # 白名单验证，防止 SQL 注入
        ALLOWED_FIELDS = {'close', 'open', 'high', 'low', 'volume', 'amount',
                          'change_pct', 'turnover_rate', 'pe', 'pb'}
        if field not in ALLOWED_FIELDS:
            return QueryResult(success=False, error=f"Invalid field: {field}")

        code = normalize_code(code)  # 标准化代码格式
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            sql_field = field  # 已通过白名单验证
            if end_date:
                df = conn.execute(f"""
                    WITH ranked AS (
                        SELECT code, trade_date, {sql_field},
                               ROW_NUMBER() OVER (PARTITION BY code ORDER BY trade_date DESC, id DESC) as rn
                        FROM daily_kline
                        WHERE code = ? AND trade_date <= ?
                    )
                    SELECT AVG({sql_field}) as ma FROM ranked WHERE rn <= ?
                """, [code, end_date, days]).df()
            else:
                df = conn.execute(f"""
                    WITH ranked AS (
                        SELECT code, trade_date, {sql_field},
                               ROW_NUMBER() OVER (PARTITION BY code ORDER BY trade_date DESC, id DESC) as rn
                        FROM daily_kline
                        WHERE code = ?
                    )
                    SELECT AVG({sql_field}) as ma FROM ranked WHERE rn <= ?
                """, [code, days]).df()

            if df.empty or df.iloc[0]['ma'] is None:
                return QueryResult(success=True, data=pd.DataFrame({'ma': [None]}), row_count=1)

            return QueryResult(success=True, data=df, row_count=1)
        except Exception as e:
            return QueryResult(success=False, error=str(e))
        finally:
            self._release_lock(lock_fd)

    def get_klines_with_ma(
        self,
        code: str,
        ma_days: List[int] = [5, 10, 20, 60],
        start_date: str = None,
        end_date: str = None,
        limit: int = 100
    ) -> QueryResult:
        """获取K线及均线"""
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            ma_sql_parts = []
            for d in ma_days:
                ma_sql_parts.append(f"""
                    AVG(t.close) OVER (ORDER BY t.trade_date ROWS BETWEEN {d-1} PRECEDING AND CURRENT ROW) as ma_{d}
                """)

            sql = f"""
                SELECT t.*, {', '.join(ma_sql_parts)}
                FROM (
                    SELECT * FROM daily_kline
                    WHERE code = ?
                    {'AND trade_date >= ?' if start_date else ''}
                    {'AND trade_date <= ?' if end_date else ''}
                    ORDER BY trade_date ASC, id ASC
                    LIMIT ?
                ) t
                ORDER BY t.trade_date ASC
            """

            params = [code]
            if start_date:
                params.append(start_date)
            if end_date:
                params.append(end_date)
            params.append(limit)

            df = conn.execute(sql, params).df()

            return QueryResult(success=True, data=df, row_count=len(df))
        except Exception as e:
            return QueryResult(success=False, error=str(e))
        finally:
            self._release_lock(lock_fd)

    def get_volume_history(
        self,
        code: str,
        days: int = 20
    ) -> List[float]:
        """获取成交量历史"""
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            df = conn.execute("""
                SELECT volume FROM daily_kline
                WHERE code = ?
                ORDER BY trade_date ASC, id ASC
                LIMIT ?
            """, [code, days]).df()

            return df['volume'].tolist() if not df.empty else []
        except Exception as e:
            print(f"get_volume_list error for {code}: {e}")
            return []
        finally:
            self._release_lock(lock_fd)

    def get_minute_klines(
        self,
        code: str,
        days: int = 1,
        limit: int = 500
    ) -> QueryResult:
        """获取某股票最近N天的分钟K线

        Args:
            code: 股票代码
            days: 获取天数，默认1天
            limit: 返回条数限制，默认500条

        Returns:
            QueryResult，包含minute_kline表的数据
        """
        code = normalize_code(code)  # 标准化代码格式
        lock_fd = None
        try:
            from datetime import datetime, timedelta
            start_datetime = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            df = conn.execute("""
                SELECT code, trade_date, trade_time, open, high, low, close, volume, amount
                FROM minute_kline
                WHERE code = ? AND trade_time >= ?
                ORDER BY trade_time ASC
                LIMIT ?
            """, [code, start_datetime, limit]).df()

            return QueryResult(success=True, data=df, row_count=len(df))
        except Exception as e:
            return QueryResult(success=False, error=str(e))
        finally:
            self._release_lock(lock_fd)

    def get_minute_ma(
        self,
        code: str,
        minutes: int = 5,
        days: int = 1
    ) -> Optional[float]:
        """计算分钟级均线

        Args:
            code: 股票代码
            minutes: 均线分钟数，默认5分钟
            days: 获取天数，默认1天

        Returns:
            均线值
        """
        code = normalize_code(code)  # 标准化代码格式
        lock_fd = None
        try:
            from datetime import datetime, timedelta
            start_datetime = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            df = conn.execute("""
                WITH ranked AS (
                    SELECT trade_time, close,
                           ROW_NUMBER() OVER (ORDER BY trade_time DESC) as rn
                    FROM minute_kline
                    WHERE code = ? AND trade_time >= ?
                )
                SELECT AVG(close) as ma FROM ranked WHERE rn <= ?
            """, [code, start_datetime, minutes]).df()

            if df.empty or df.iloc[0]['ma'] is None:
                return None

            return float(df.iloc[0]['ma'])
        except Exception as e:
            print(f"get_ma error for {code}: {e}")
            return None
        finally:
            self._release_lock(lock_fd)

    def get_bulk_minute_data(
        self,
        codes: List[str],
        minutes: int = 5,
        days: int = 1
    ) -> Dict[str, Dict[str, float]]:
        """批量获取多个股票的分钟MA数据 v19.9

        一次查询所有股票，内存中计算MA，避免N+1查询问题

        Args:
            codes: 股票代码列表
            minutes: 均线分钟数
            days: 获取天数

        Returns:
            {code: {'ma5': float, 'ma15': float, 'latest_price': float, 'avg_volume': float}}
        """
        lock_fd = None
        try:
            from datetime import datetime, timedelta
            start_datetime = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            if not codes:
                return {}
            codes = [normalize_code(c) for c in codes]  # 标准化代码格式

            # 构造IN子句的占位符
            placeholders = ','.join(['?' for _ in codes])

            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            # 一次性获取所有股票的最新分钟数据
            df = conn.execute(f"""
                WITH latest AS (
                    SELECT code, trade_time, close, volume,
                           ROW_NUMBER() OVER (PARTITION BY code ORDER BY trade_time DESC) as rn
                    FROM minute_kline
                    WHERE code IN ({placeholders}) AND trade_time >= ?
                ),
                ma5 AS (
                    SELECT code, AVG(close) as ma5
                    FROM (SELECT code, trade_time, close, ROW_NUMBER() OVER (PARTITION BY code ORDER BY trade_time DESC) as rn
                          FROM minute_kline WHERE code IN ({placeholders}) AND trade_time >= ?)
                    WHERE rn <= {minutes}
                    GROUP BY code
                ),
                ma15 AS (
                    SELECT code, AVG(close) as ma15
                    FROM (SELECT code, trade_time, close, ROW_NUMBER() OVER (PARTITION BY code ORDER BY trade_time DESC) as rn
                          FROM minute_kline WHERE code IN ({placeholders}) AND trade_time >= ?)
                    WHERE rn <= {minutes * 3}
                    GROUP BY code
                ),
                volume_stats AS (
                    SELECT code, AVG(volume) as avg_volume
                    FROM (SELECT code, trade_time, volume, ROW_NUMBER() OVER (PARTITION BY code ORDER BY trade_time DESC) as rn
                          FROM minute_kline WHERE code IN ({placeholders}) AND trade_time >= ?)
                    WHERE rn <= 10
                    GROUP BY code
                ),
                latest_price AS (
                    SELECT code, close as price
                    FROM latest WHERE rn = 1
                )
                SELECT l.code, l.price, m5.ma5, m15.ma15, vs.avg_volume
                FROM latest_price l
                LEFT JOIN ma5 m5 ON l.code = m5.code
                LEFT JOIN ma15 m15 ON l.code = m15.code
                LEFT JOIN volume_stats vs ON l.code = vs.code
            """, codes * 5 + [start_datetime] * 5).df()

            result = {}
            for _, row in df.iterrows():
                code = row['code']
                result[code] = {
                    'ma5': float(row['ma5']) if row['ma5'] is not None else None,
                    'ma15': float(row['ma15']) if row['ma15'] is not None else None,
                    'latest_price': float(row['price']) if row['price'] is not None else 0.0,
                    'avg_volume': float(row['avg_volume']) if row['avg_volume'] is not None else 0.0,
                    'current_volume': 0.0  # 将在调用处填充
                }
            return result
        except Exception as e:
            print(f"get_bulk_minute_data error: {e}")
            return {}
        finally:
            self._release_lock(lock_fd)

    def get_trade_dates(
        self,
        start_date: str,
        end_date: str
    ) -> List[str]:
        """获取交易日列表"""
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            df = conn.execute("""
                SELECT DISTINCT trade_date FROM daily_kline
                WHERE trade_date BETWEEN ? AND ?
                ORDER BY trade_date
            """, [start_date, end_date]).df()

            return [str(d) for d in df['trade_date'].tolist()]
        except Exception as e:
            logger.warning(f"get_trade_dates 查询失败: {e}")
            return []
        finally:
            self._release_lock(lock_fd)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            total = conn.execute("SELECT COUNT(*) as cnt FROM daily_kline").fetchone()[0]
            codes = conn.execute("SELECT COUNT(DISTINCT code) as cnt FROM daily_kline").fetchone()[0]
            date_range = conn.execute("""
                SELECT MIN(trade_date), MAX(trade_date) FROM daily_kline
            """).fetchone()

            # 表大小
            size_bytes = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0

            return {
                'total_rows': total,
                'total_codes': codes,
                'date_from': str(date_range[0]) if date_range[0] else None,
                'date_to': str(date_range[1]) if date_range[1] else None,
                'size_bytes': size_bytes,
                'size_mb': round(size_bytes / 1024 / 1024, 2),
            }
        except Exception as e:
            return {'error': str(e)}
        finally:
            self._release_lock(lock_fd)

    def query(self, sql: str, params: List = None) -> QueryResult:
        """执行自定义SQL查询"""
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)  # 共享锁
            conn = self._get_read_conn()  # 使用读连接
            if params:
                df = conn.execute(sql, params).df()
            else:
                df = conn.execute(sql).df()

            return QueryResult(success=True, data=df, row_count=len(df))
        except Exception as e:
            return QueryResult(success=False, error=str(e))
        finally:
            self._release_lock(lock_fd)

    def close(self):
        """关闭连接（ DuckDB是嵌入式，不需要显式关闭）"""
        pass

    # ==================== 数据时效清理 ====================

    def cleanup_old_klines(
        self,
        keep_days: int = 730,
        table: str = 'daily_kline'
    ) -> Dict:
        """
        删除超过保留期的K线数据

        Args:
            keep_days: 保留天数，默认730天（2年）
            table: 表名，默认 daily_kline

        Returns:
            {
                'success': bool,
                'deleted_rows': int,
                'remaining_rows': int,
                'cutoff_date': str,
            }
        """
        lock_fd = None
        try:
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=keep_days)).strftime('%Y-%m-%d')

            lock_fd = self._acquire_lock(exclusive=True)
            conn = self._get_conn()
            # 删除前统计
            before_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

            # 删除超过保留期的数据
            conn.execute(
                f"DELETE FROM {table} WHERE trade_date < ?",
                [cutoff_date]
            )

            # 删除后统计
            after_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            deleted = before_count - after_count

            return {
                'success': True,
                'deleted_rows': deleted,
                'remaining_rows': after_count,
                'cutoff_date': cutoff_date,
                'keep_days': keep_days,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            self._release_lock(lock_fd)

    def cleanup_old_minute_klines(
        self,
        keep_days: int = 14
    ) -> Dict:
        """
        删除超过保留期的分钟K线数据

        Args:
            keep_days: 保留天数，默认14天（核心池+活跃池均为14天）

        Returns:
            清理结果
        """
        lock_fd = None
        try:
            from datetime import datetime, timedelta
            cutoff_datetime = (datetime.now() - timedelta(days=keep_days)).strftime('%Y-%m-%d %H:%M:%S')

            lock_fd = self._acquire_lock(exclusive=True)
            conn = self._get_conn()
            before_count = conn.execute("SELECT COUNT(*) FROM minute_kline").fetchone()[0]

            conn.execute(
                "DELETE FROM minute_kline WHERE trade_time < ?",
                [cutoff_datetime]
            )

            after_count = conn.execute("SELECT COUNT(*) FROM minute_kline").fetchone()[0]
            deleted = before_count - after_count

            return {
                'success': True,
                'deleted_rows': deleted,
                'remaining_rows': after_count,
                'cutoff_datetime': cutoff_datetime,
                'keep_days': keep_days,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            self._release_lock(lock_fd)

    def get_retention_info(self) -> Dict:
        """
        获取数据保留信息（用于诊断）

        Returns:
            各表的数据保留情况
        """
        lock_fd = None
        try:
            lock_fd = self._acquire_lock(exclusive=False)
            conn = self._get_read_conn()
            info = {}

            # daily_kline
            daily_stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    MIN(trade_date) as oldest,
                    MAX(trade_date) as newest,
                    COUNT(DISTINCT code) as codes
                FROM daily_kline
            """).fetchone()
            info['daily_kline'] = {
                'total_rows': daily_stats[0],
                'oldest_date': str(daily_stats[1]) if daily_stats[1] else None,
                'newest_date': str(daily_stats[2]) if daily_stats[2] else None,
                'stock_count': daily_stats[3],
            }

            # minute_kline
            minute_stats = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    MIN(trade_time) as oldest,
                    MAX(trade_time) as newest
                FROM minute_kline
            """).fetchone()
            info['minute_kline'] = {
                'total_rows': minute_stats[0],
                'oldest_time': str(minute_stats[1]) if minute_stats[1] else None,
                'newest_time': str(minute_stats[2]) if minute_stats[2] else None,
            }

            return info
        except Exception as e:
            return {'error': str(e)}
        finally:
            self._release_lock(lock_fd)

    def backfill_adj_factor(self, batch_size: int = 1000, offset: int = 0) -> Dict:
        """
        v19.9.4: 从 ex_right_factor 表回填 adj_factor 和 adj_close

        由于历史原因，DuckDB daily_kline 表的 adj_factor 全部为1.0，
        adj_close 也未正确计算。本方法从 SQLite ex_right_factor 表
        获取复权因子并回填。

        Returns:
            回填结果统计
        """
        # 注意：这需要 SQLite ex_right_factor 表有数据
        # 如果表为空，先调用 ExRightFactorFiller.fetch_from_tushare()
        lock_fd = None
        try:
            import sqlite3
            sqlite_path = str(SQLITE_PATH)

            # 获取需要回填的股票
            sqlite_conn = sqlite3.connect(sqlite_path)
            cursor = sqlite_conn.execute("""
                SELECT DISTINCT symbol FROM ex_right_factor
                WHERE adj_type = 'qfq'
            """)
            symbols = [row[0] for row in cursor.fetchall()]
            sqlite_conn.close()

            if not symbols:
                return {'success': True, 'symbols_processed': 0, 'rows_updated': 0}

            # 获取文件锁（跨进程保护）
            lock_fd = self._acquire_lock(exclusive=True)

            # 关闭已有连接（需要同时持有 _conn_lock 防止并发访问）
            with self._conn_lock:
                # 如果已有读连接，关闭它（避免 DuckDB 连接配置冲突）
                if self._read_conn is not None:
                    try:
                        self._read_conn.close()
                    except Exception as e:
                        logger.debug(f"关闭读连接时出错: {e}")
                    self._read_conn = None

                # 如果已有写连接，先关闭它（确保干净的连接状态）
                if self._write_conn is not None:
                    try:
                        self._write_conn.close()
                    except Exception as e:
                        logger.debug(f"关闭写连接时出错: {e}")
                    self._write_conn = None

            # 创建新连接（避免配置冲突）
            import duckdb
            conn = duckdb.connect(self.db_path, read_only=False)

            total_updated = 0

            # 限制处理数量，每批50只股票，每只股票只处理最近500条因子
            # 使用 offset 参数支持分批处理
            limit_symbols = 50
            max_factors_per_symbol = 500

            # 应用 offset 来支持分批处理
            symbols_subset = symbols[offset:offset + limit_symbols]

            for i, symbol in enumerate(symbols_subset):
                if i % 10 == 0:
                    print(f"backfill_adj_factor: processing {offset + i}/{len(symbols)}, total_updated={total_updated}")
                    try:
                        # 获取该股票的因子（限制数量避免超时）
                        sqlite_conn = sqlite3.connect(sqlite_path)
                        cursor = sqlite_conn.execute("""
                            SELECT trade_date, factor FROM ex_right_factor
                            WHERE symbol = ? AND adj_type = 'qfq' AND factor < 10000
                            ORDER BY trade_date DESC
                            LIMIT ?
                        """, (symbol, max_factors_per_symbol))
                        factors = {row[0]: row[1] for row in cursor.fetchall()}
                        sqlite_conn.close()

                        if not factors:
                            continue

                        # 批量更新该股票的 adj_factor
                        for trade_date, factor in factors.items():
                            try:
                                # 转换日期格式：20260417 -> 2026-04-17
                                formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                                conn.execute("""
                                    UPDATE daily_kline
                                    SET adj_factor = ?, adj_close = close * ?
                                    WHERE code = ? AND trade_date = ?
                                """, [factor, factor, symbol, formatted_date])
                            except Exception as e:
                                print(f"backfill_adj_factor UPDATE failed for {symbol} {formatted_date}: {e}")
                        total_updated += len(factors)
                    except Exception as e:
                        print(f"backfill_adj_factor symbol processing failed for {symbol}: {e}")

            # 提交事务
            conn.commit()
            print(f"backfill_adj_factor: done, total_updated={total_updated}")

            return {
                'success': True,
                'symbols_processed': len(symbols_subset),
                'rows_updated': total_updated
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
        finally:
            if lock_fd:
                self._release_lock(lock_fd)


# ==================== SQLite历史数据迁移 ====================

class HistoryMigrator:
    """历史数据迁移器（从SQLite迁移到DuckDB）"""

    def __init__(self, sqlite_path: str = None, duckdb_store: DuckDBStore = None):
        self.sqlite_path = str(sqlite_path or SQLITE_PATH)
        self.duckdb = duckdb_store or DuckDBStore()

    def migrate_price_history(self, batch_size: int = 1000) -> Dict:
        """
        从SQLite的price_history表迁移到DuckDB

        Returns:
            迁移统计
        """
        try:
            sqlite_conn = sqlite3.connect(self.sqlite_path)

            # 检查源表是否存在
            cursor = sqlite_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='price_history'"
            )
            if not cursor.fetchone():
                return {'success': False, 'error': 'price_history table not found in SQLite'}

            # 获取总数
            cursor = sqlite_conn.execute("SELECT COUNT(*) FROM price_history")
            total = cursor.fetchone()[0]

            # 分批读取和插入
            offset = 0
            success = 0
            errors = 0

            while offset < total:
                df = pd.read_sql_query(
                    f"SELECT * FROM price_history LIMIT {batch_size} OFFSET {offset}",
                    sqlite_conn
                )

                if df.empty:
                    break

                # 转换日期格式: date -> trade_date
                if 'date' in df.columns:
                    df['trade_date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    df.drop('date', axis=1, inplace=True)

                # 转换股票代码格式: sz002772 -> 002772
                if 'code' in df.columns:
                    df['code'] = df['code'].str.replace(r'^(sz|sh)', '', regex=True)

                # 确保adj_close字段存在（使用close作为默认值）
                if 'adj_close' not in df.columns:
                    df['adj_close'] = df['close']

                # 插入DuckDB
                inserted = self.duckdb.insert_from_dataframe(df)
                success += inserted
                errors += (len(df) - inserted)
                offset += batch_size

            sqlite_conn.close()

            return {
                'success': True,
                'total': total,
                'inserted': success,
                'errors': errors,
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def migrate_from_cache_files(self, data_dir: Path, batch_size: int = 500) -> Dict:
        """
        从JSON缓存文件迁移历史K线数据

        Args:
            data_dir: 数据目录（包含 *_history_cache.json 文件）
            batch_size: 批量大小

        Returns:
            迁移统计
        """
        import glob

        history_files = list(data_dir.glob("*_history_cache.json"))
        if not history_files:
            return {'success': True, 'message': 'No history cache files found', 'processed': 0}

        total_success = 0
        total_errors = 0

        for cache_file in history_files:
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if not isinstance(data, list):
                    data = [data]

                records = []
                for item in data:
                    if 'code' in item and 'trade_date' in item:
                        records.append(KlineRecord(
                            code=item['code'],
                            trade_date=item['trade_date'],
                            open=float(item.get('open', 0)),
                            high=float(item.get('high', 0)),
                            low=float(item.get('low', 0)),
                            close=float(item.get('close', 0)),
                            volume=float(item.get('volume', 0)),
                            amount=float(item.get('amount', 0)),
                            change_pct=float(item.get('change_pct', 0)),
                            adj_close=float(item.get('adj_close', 0)),
                        ))

                if records:
                    s, e = self.duckdb.insert_daily_klines_batch(records)
                    total_success += s
                    total_errors += e

            except Exception as ex:
                print(f"Error processing {cache_file}: {ex}")
                continue

        return {
            'success': True,
            'files_processed': len(history_files),
            'inserted': total_success,
            'errors': total_errors,
        }


# ==================== 全局单例 ====================

_duckdb_store = None
_duckdb_store_lock = threading.Lock()


def get_duckdb_store() -> DuckDBStore:
    """获取DuckDB存储管理器单例（线程安全）"""
    global _duckdb_store
    if _duckdb_store is None:
        with _duckdb_store_lock:
            if _duckdb_store is None:  # 二次检查
                _duckdb_store = DuckDBStore()
    return _duckdb_store


# ==================== 便捷函数 ====================

def get_klines(code: str, days: int = None, start_date: str = None, end_date: str = None, limit: int = 1000) -> QueryResult:
    """获取K线数据

    支持两种调用方式：
    1. get_klines(code, days=N) - 获取最近N天
    2. get_klines(code, start_date='2024-01-01', end_date='2024-12-31') - 指定日期范围

    Args:
        code: 股票代码
        days: 最近N天（与start_date/end_date互斥）
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        limit: 返回条数限制
    """
    if days is not None and start_date is None and end_date is None:
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    return get_duckdb_store().get_klines(code, start_date, end_date, limit)


def get_klines_bulk(codes: List[str], days: int = 60) -> Dict[str, pd.DataFrame]:
    """批量获取多只股票K线（单次连接，适合预测引擎全市场扫描）"""
    return get_duckdb_store().get_klines_bulk(codes, days)


def get_latest_kline(code: str) -> Optional[Dict]:
    """获取最新K线"""
    return get_duckdb_store().get_latest_kline(code)


def get_date_range(code: str) -> Tuple[Optional[str], Optional[str]]:
    """获取某股票已有数据的日期范围 (min_date, max_date)"""
    return get_duckdb_store().get_date_range(code)


def insert_kline(record: KlineRecord) -> bool:
    """插入单条K线"""
    return get_duckdb_store().insert_daily_kline(record)


def get_ma(code: str, days: int = 5, end_date: str = None) -> Optional[float]:
    """计算均线"""
    result = get_duckdb_store().get_ma(code, days, end_date)
    if result.success and result.data is not None and not result.data.empty:
        return result.data.iloc[0]['ma']
    return None


def get_minute_klines(code: str, days: int = 1, limit: int = 500) -> QueryResult:
    """获取分钟K线数据"""
    return get_duckdb_store().get_minute_klines(code, days, limit)


def get_minute_ma(code: str, minutes: int = 5, days: int = 1) -> Optional[float]:
    """计算分钟级均线"""
    return get_duckdb_store().get_minute_ma(code, minutes, days)


def get_bulk_minute_data(codes: List[str], minutes: int = 5, days: int = 1) -> Dict[str, Dict[str, float]]:
    """批量获取多个股票的分钟MA数据 v19.9

    一次查询所有股票，内存中计算MA，避免N+1查询问题

    Args:
        codes: 股票代码列表
        minutes: 均线分钟数
        days: 获取天数

    Returns:
        {code: {'ma5': float, 'ma15': float, 'latest_price': float, 'avg_volume': float, 'current_volume': float}}
    """
    return get_duckdb_store().get_bulk_minute_data(codes, minutes, days)


# ==================== 数据清理便捷函数 ====================

def cleanup_old_klines(keep_days: int = 730) -> Dict:
    """
    删除超过保留期的日K线数据

    Args:
        keep_days: 保留天数，默认730天（2年）

    Returns:
        清理结果
    """
    return get_duckdb_store().cleanup_old_klines(keep_days=keep_days)


def cleanup_old_minute_klines(keep_days: int = 30) -> Dict:
    """
    删除超过保留期的分钟K线数据

    Args:
        keep_days: 保留天数，默认30天

    Returns:
        清理结果
    """
    return get_duckdb_store().cleanup_old_minute_klines(keep_days=keep_days)


def get_retention_info() -> Dict:
    """获取数据保留信息"""
    return get_duckdb_store().get_retention_info()


def cleanup_all_old_data(
    daily_keep_days: int = 730,
    minute_keep_days: int = 30
) -> Dict:
    """
    清理所有超过保留期的数据

    Args:
        daily_keep_days: 日K线保留天数
        minute_keep_days: 分钟K线保留天数

    Returns:
        各表的清理结果
    """
    store = get_duckdb_store()
    return {
        'daily_kline': store.cleanup_old_klines(keep_days=daily_keep_days),
        'minute_kline': store.cleanup_old_minute_klines(keep_days=minute_keep_days),
    }


def get_readonly_connection(db_path: str = None):
    """获取只读 DuckDB 连接，用于分析脚本（不与主进程的写锁冲突）

    Args:
        db_path: 可选，默认使用 DUCKDB_PATH

    Returns:
        DuckDBPyConnection (read_only=True)
    """
    from backend.config import DUCKDB_PATH
    path = db_path or str(DUCKDB_PATH)
    return duckdb.connect(path, read_only=True)


# 静态方法版本（供 DuckDBStore 内部使用）
DuckDBStore.get_readonly_connection = staticmethod(get_readonly_connection)
