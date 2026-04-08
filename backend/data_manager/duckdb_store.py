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
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import threading
import pandas as pd


# ==================== 路径配置 ====================

DATA_DIR = Path("/home/ailearn/projects/TradeSnake/data")
DUCKDB_PATH = DATA_DIR / "historical.duckdb"
SQLITE_PATH = DATA_DIR / "tradesnake.db"


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


@dataclass
class QueryResult:
    """查询结果"""
    success: bool
    data: Optional[pd.DataFrame] = None
    row_count: int = 0
    error: Optional[str] = None


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
        self._ensure_tables()

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        """获取DuckDB连接"""
        return duckdb.connect(self.db_path, read_only=False)

    def _ensure_tables(self):
        """确保表存在"""
        with self._get_conn() as conn:
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (code, trade_date)
                )
            """)

            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_code_date
                ON daily_kline(code, trade_date DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_date
                ON daily_kline(trade_date DESC)
            """)

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

    def insert_daily_kline(self, record: KlineRecord) -> bool:
        """插入单条日K线"""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO daily_kline
                    (code, trade_date, open, high, low, close, volume, amount, change_pct, adj_close)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ))
            return True
        except Exception as e:
            print(f"Insert daily kline error: {e}")
            return False

    def insert_daily_klines_batch(self, records: List[KlineRecord]) -> Tuple[int, int]:
        """
        批量插入日K线

        Returns:
            (success_count, error_count)
        """
        if not records:
            return 0, 0

        success = 0
        errors = 0

        try:
            with self._get_conn() as conn:
                for r in records:
                    try:
                        conn.execute("""
                            INSERT OR REPLACE INTO daily_kline
                            (code, trade_date, open, high, low, close, volume, amount, change_pct, adj_close)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            r.code, r.trade_date, r.open, r.high, r.low, r.close,
                            r.volume, r.amount, r.change_pct, r.adj_close,
                        ))
                        success += 1
                    except Exception:
                        errors += 1
        except Exception as e:
            return 0, len(records)

        return success, errors

    def insert_from_dataframe(self, df: pd.DataFrame, table: str = 'daily_kline') -> int:
        """
        从DataFrame批量插入

        Args:
            df: 必须包含 code, trade_date, open, high, low, close, volume 字段
            table: 表名

        Returns:
            插入行数
        """
        if df.empty:
            return 0

        required = ['code', 'trade_date', 'open', 'high', 'low', 'close', 'volume']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        try:
            with self._get_conn() as conn:
                # 先删除已存在的记录
                unique_codes = df['code'].unique().tolist()
                if unique_codes:
                    placeholders = ','.join([f"'{c}'" for c in unique_codes])
                    conn.execute(f"DELETE FROM {table} WHERE code IN ({placeholders})")

                # 批量插入
                conn.execute(f"INSERT INTO {table} BY NAME SELECT * FROM df")
                return len(df)
        except Exception as e:
            print(f"Insert from DataFrame error: {e}")
            return 0

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
            code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 返回条数限制

        Returns:
            QueryResult with DataFrame
        """
        try:
            with self._get_conn() as conn:
                sql = "SELECT * FROM daily_kline WHERE code = ?"
                params = [code]

                if start_date:
                    sql += " AND trade_date >= ?"
                    params.append(start_date)

                if end_date:
                    sql += " AND trade_date <= ?"
                    params.append(end_date)

                sql += " ORDER BY trade_date DESC LIMIT ?"
                params.append(limit)

                df = conn.execute(sql, params).df()

                return QueryResult(
                    success=True,
                    data=df,
                    row_count=len(df)
                )
        except Exception as e:
            return QueryResult(success=False, error=str(e))

    def get_latest_kline(self, code: str) -> Optional[Dict]:
        """获取最新一条K线"""
        try:
            with self._get_conn() as conn:
                df = conn.execute("""
                    SELECT * FROM daily_kline
                    WHERE code = ?
                    ORDER BY trade_date DESC
                    LIMIT 1
                """, [code]).df()

                if df.empty:
                    return None

                return df.iloc[0].to_dict()
        except Exception:
            return None

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
            field: 计算字段

        Returns:
            均线值
        """
        try:
            with self._get_conn() as conn:
                if end_date:
                    df = conn.execute("""
                        WITH ranked AS (
                            SELECT code, trade_date, %s,
                                   ROW_NUMBER() OVER (PARTITION BY code ORDER BY trade_date DESC) as rn
                            FROM daily_kline
                            WHERE code = ? AND trade_date <= ?
                        )
                        SELECT AVG(%s) as ma FROM ranked WHERE rn <= ?
                    """ % (field, field), [code, end_date, days]).df()
                else:
                    df = conn.execute("""
                        WITH ranked AS (
                            SELECT code, trade_date, %s,
                                   ROW_NUMBER() OVER (PARTITION BY code ORDER BY trade_date DESC) as rn
                            FROM daily_kline
                            WHERE code = ?
                        )
                        SELECT AVG(%s) as ma FROM ranked WHERE rn <= ?
                    """ % (field, field), [code, days]).df()

                if df.empty or df.iloc[0]['ma'] is None:
                    return QueryResult(success=True, data=pd.DataFrame({'ma': [None]}), row_count=1)

                return QueryResult(success=True, data=df, row_count=1)
        except Exception as e:
            return QueryResult(success=False, error=str(e))

    def get_klines_with_ma(
        self,
        code: str,
        ma_days: List[int] = [5, 10, 20, 60],
        start_date: str = None,
        end_date: str = None,
        limit: int = 100
    ) -> QueryResult:
        """获取K线及均线"""
        try:
            with self._get_conn() as conn:
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
                        ORDER BY trade_date DESC
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

    def get_volume_history(
        self,
        code: str,
        days: int = 20
    ) -> List[float]:
        """获取成交量历史"""
        try:
            with self._get_conn() as conn:
                df = conn.execute("""
                    SELECT volume FROM daily_kline
                    WHERE code = ?
                    ORDER BY trade_date DESC
                    LIMIT ?
                """, [code, days]).df()

                return df['volume'].tolist() if not df.empty else []
        except Exception:
            return []

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
        try:
            from datetime import datetime, timedelta
            start_datetime = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            with self._get_conn() as conn:
                df = conn.execute("""
                    SELECT code, trade_date, trade_time, open, high, low, close, volume, amount
                    FROM minute_kline
                    WHERE code = ? AND trade_time >= ?
                    ORDER BY trade_time DESC
                    LIMIT ?
                """, [code, start_datetime, limit]).df()

                return QueryResult(success=True, data=df, row_count=len(df))
        except Exception as e:
            return QueryResult(success=False, error=str(e))

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
        try:
            from datetime import datetime, timedelta
            start_datetime = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            with self._get_conn() as conn:
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
        except Exception:
            return None

    def get_trade_dates(
        self,
        start_date: str,
        end_date: str
    ) -> List[str]:
        """获取交易日列表"""
        try:
            with self._get_conn() as conn:
                df = conn.execute("""
                    SELECT DISTINCT trade_date FROM daily_kline
                    WHERE trade_date BETWEEN ? AND ?
                    ORDER BY trade_date
                """, [start_date, end_date]).df()

                return [str(d) for d in df['trade_date'].tolist()]
        except Exception:
            return []

    def get_stats(self) -> Dict:
        """获取统计信息"""
        try:
            with self._get_conn() as conn:
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

    def query(self, sql: str, params: List = None) -> QueryResult:
        """执行自定义SQL查询"""
        try:
            with self._get_conn() as conn:
                if params:
                    df = conn.execute(sql, params).df()
                else:
                    df = conn.execute(sql).df()

                return QueryResult(success=True, data=df, row_count=len(df))
        except Exception as e:
            return QueryResult(success=False, error=str(e))

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
        try:
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=keep_days)).strftime('%Y-%m-%d')

            with self._get_conn() as conn:
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
        try:
            from datetime import datetime, timedelta
            cutoff_datetime = (datetime.now() - timedelta(days=keep_days)).strftime('%Y-%m-%d %H:%M:%S')

            with self._get_conn() as conn:
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

    def get_retention_info(self) -> Dict:
        """
        获取数据保留信息（用于诊断）

        Returns:
            各表的数据保留情况
        """
        try:
            with self._get_conn() as conn:
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


def get_duckdb_store() -> DuckDBStore:
    """获取DuckDB存储管理器单例"""
    global _duckdb_store
    if _duckdb_store is None:
        _duckdb_store = DuckDBStore()
    return _duckdb_store


# ==================== 便捷函数 ====================

def get_klines(code: str, start_date: str = None, end_date: str = None, limit: int = 1000) -> QueryResult:
    """获取K线数据"""
    return get_duckdb_store().get_klines(code, start_date, end_date, limit)


def get_latest_kline(code: str) -> Optional[Dict]:
    """获取最新K线"""
    return get_duckdb_store().get_latest_kline(code)


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
