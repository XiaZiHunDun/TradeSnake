"""
数据生命周期清理模块 - Data Lifecycle Cleanup
=============================================
职责：统一管理所有数据的清理任务

清理策略：
- SQLite：cp_history保留2年，price_history保留2年，alerts保留90天
- DuckDB：日K线保留2年（超限降采样为周K），分钟K线保留14天
- JSON缓存：基于TTL自动清理

核心原则：
1. 先备份后清理 - 确保数据安全
2. 分批删除 - 避免IO阻塞
3. 幂等性 - 防止重复清理
4. 审计日志 - 记录清理详情
"""

import os
import json
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ==================== 路径配置 ====================

DATA_DIR = Path("/home/ailearn/projects/TradeSnake/data")
BACKUP_DIR = DATA_DIR / "backup"
SQLITE_PATH = DATA_DIR / "tradesnake.db"
DUCKDB_PATH = DATA_DIR / "historical.duckdb"


# ==================== 清理配置 ====================

# SQLite保留策略（天）
SQLITE_RETENTION = {
    'cp_history': 365 * 2,       # 战力历史：2年
    'price_history': 365 * 2,    # 价格历史：2年
    'alerts': 90,                # 告警记录：90天
}

# DuckDB保留策略（天）
DUCKDB_RETENTION = {
    'daily_kline': 365 * 2,      # 日K线：2年
    'minute_kline_core': 14,     # 核心池分钟K：14天
    'minute_kline_active': 14,   # 活跃池分钟K：14天
}

# JSON缓存TTL（天）
CACHE_RETENTION = {
    'market_': 1,               # 市场行情缓存：1天
    'fin_': 7,                   # 财务数据缓存：7天
    'stock_list': 7,             # 股票列表缓存：7天
    'stock_pool': 7,             # 股票池配置：7天
    'market_trends': 7,          # 市场趋势：7天
    'enhancer_status': 30,       # 增强器状态：30天
    'cp_history': 30,            # 战力历史JSON：30天
    'tushare_ts_': 7,           # Tushare原始数据：7天
}

# 分批删除配置
BATCH_DELETE_CONFIG = {
    'duckdb_daily_kline_batch': 5000,    # DuckDB日K每批5000条
    'duckdb_minute_kline_batch': 10000,  # DuckDB分钟K每批10000条
    'sqlite_cp_history_batch': 5000,     # SQLite cp_history每批5000条
}


# ==================== 清理结果 ====================

@dataclass
class CleanupResult:
    """清理结果"""
    success: bool
    operation: str
    deleted_count: int = 0
    freed_bytes: int = 0
    errors: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)


@dataclass
class CleanupAudit:
    """清理审计记录"""
    timestamp: str
    operation: str
    details: Dict
    records_deleted: int
    space_freed_bytes: int
    status: str  # 'success', 'failed', 'partial'
    error_message: Optional[str] = None


# ==================== 清理状态管理 ====================

class CleanupState:
    """清理状态管理（用于幂等性）"""

    STATE_FILE = DATA_DIR / ".cleanup_state"
    LOCK_FILE = DATA_DIR / ".cleanup_lock"

    @classmethod
    def is_running(cls) -> bool:
        """检查是否有清理任务正在运行"""
        if cls.LOCK_FILE.exists():
            # 检查是否超时（超过1小时视为僵尸锁）
            try:
                lock_time = datetime.fromisoformat(cls.LOCK_FILE.read_text())
                if datetime.now() - lock_time > timedelta(hours=1):
                    cls.LOCK_FILE.unlink()
                    return False
                return True
            except:
                cls.LOCK_FILE.unlink()
                return False
        return False

    @classmethod
    def acquire_lock(cls) -> bool:
        """获取清理锁"""
        if cls.is_running():
            return False
        cls.LOCK_FILE.write_text(datetime.now().isoformat())
        return True

    @classmethod
    def release_lock(cls):
        """释放清理锁"""
        cls.LOCK_FILE.unlink(missing_ok=True)

    @classmethod
    def is_already_cleaned_today(cls, operation: str = None) -> bool:
        """检查今日是否已执行过清理"""
        if not cls.STATE_FILE.exists():
            return False
        try:
            state = json.loads(cls.STATE_FILE.read_text())
            today = datetime.now().strftime("%Y-%m-%d")
            if state.get("date") == today:
                if operation is None:
                    return True
                return operation in state.get("completed_operations", [])
            return False
        except:
            return False

    @classmethod
    def mark_completed(cls, operation: str, details: Dict):
        """标记清理完成"""
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            if cls.STATE_FILE.exists():
                state = json.loads(cls.STATE_FILE.read_text())
                if state.get("date") != today:
                    state = {"date": today, "completed_operations": []}
            else:
                state = {"date": today, "completed_operations": []}
        except:
            state = {"date": today, "completed_operations": []}

        state["completed_operations"].append(operation)
        state[f"{operation}_details"] = details
        cls.STATE_FILE.write_text(json.dumps(state, indent=2))


# ==================== 审计日志 ====================

class CleanupAuditor:
    """清理审计日志"""

    @staticmethod
    def init_audit_table(conn: sqlite3.Connection):
        """初始化审计日志表"""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cleanup_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT,
                operation TEXT NOT,
                details TEXT NOT,
                records_deleted INTEGER DEFAULT 0,
                space_freed_bytes INTEGER DEFAULT 0,
                status TEXT NOT,
                error_message TEXT,
                operator TEXT DEFAULT 'system'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cleanup_audit_timestamp
            ON cleanup_audit(timestamp DESC)
        """)

    @classmethod
    def log(cls, conn: sqlite3.Connection, audit: CleanupAudit):
        """记录审计日志"""
        cls.init_audit_table(conn)
        conn.execute("""
            INSERT INTO cleanup_audit
            (timestamp, operation, details, records_deleted, space_freed_bytes, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            audit.timestamp,
            audit.operation,
            json.dumps(audit.details),
            audit.records_deleted,
            audit.space_freed_bytes,
            audit.status,
            audit.error_message
        ))


# ==================== 清理前核心数据校验 ====================

class CleanupValidator:
    """
    清理前核心数据校验

    确保核心业务数据（P0级别）在清理前完好无损
    """

    # P0核心数据：绝不能删除的数据
    PROTECTED_TABLES = ['holdings', 'trades', 'orders', 'account', 'account_flow']
    PROTECTED_KLINE_TABLES = ['weekly_kline_archive']  # 归档表不清理

    @classmethod
    def pre_cleanup_check(cls) -> Tuple[bool, str]:
        """
        清理前核心数据校验

        检查项：
        1. SQLite核心表是否存在且可读
        2. DuckDB是否存在且可读
        3. 备份目录是否可写
        4. 存储空间是否充足

        Returns:
            (is_valid, error_message)
        """
        # 检查1：SQLite核心表
        conn = sqlite3.connect(str(SQLITE_PATH))
        try:
            cursor = conn.cursor()
            for table in cls.PROTECTED_TABLES:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                except sqlite3.OperationalError as e:
                    if "no such table" in str(e).lower():
                        # 核心表不存在，记录警告但不阻止清理（可能是新建数据库）
                        pass
                    else:
                        return False, f"核心表{table}读取失败: {e}"
        finally:
            conn.close()

        # 检查2：DuckDB是否存在且可读
        if DUCKDB_PATH.exists():
            try:
                import duckdb
                duckdb_conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
                duckdb_conn.execute("SELECT 1")
                duckdb_conn.close()
            except Exception as e:
                return False, f"DuckDB读取失败: {e}"

        # 检查3：备份目录是否可写
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            test_file = BACKUP_DIR / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            return False, f"备份目录不可写: {e}"

        # 检查4：存储空间是否充足（剩余空间 > 1GB）
        import shutil
        total, used, free = shutil.disk_usage(DATA_DIR)
        if free < 1024 * 1024 * 1024:  # 1GB
            return False, f"存储空间不足: 剩余{free / 1024 / 1024 / 1024:.2f}GB，建议先清理"

        return True, ""

    @classmethod
    def validate_before_delete_klines(cls, table_name: str, estimated_count: int) -> Tuple[bool, str]:
        """
        删除K线前二次校验

        Args:
            table_name: 表名
            estimated_count: 预计删除条数

        Returns:
            (is_valid, warning_message)
        """
        if table_name in cls.PROTECTED_KLINE_TABLES:
            return False, f"保护表{table_name}不允许删除"

        if estimated_count > 10000000:  # 超过1000万条需要确认
            return True, f"即将删除大量数据({estimated_count}条)，请确认"

        return True, ""


# ==================== SQLite清理 ====================

class SQLiteCleaner:
    """SQLite数据清理"""

    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or SQLITE_PATH)

    def cleanup_cp_history(self, retention_days: int = None) -> CleanupResult:
        """
        清理过期的战力历史数据

        Args:
            retention_days: 保留天数，默认730天（2年）

        Returns:
            清理结果
        """
        retention_days = retention_days or SQLITE_RETENTION['cp_history']
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        try:
            # 获取清理前的大小估算
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cp_history WHERE recorded_at < ?", (cutoff_date,))
            to_delete = cursor.fetchone()[0]

            if to_delete == 0:
                return CleanupResult(success=True, operation="sqlite_cp_history", deleted_count=0)

            # 分批删除
            batch_size = BATCH_DELETE_CONFIG['sqlite_cp_history_batch']
            total_deleted = 0

            while True:
                cursor.execute("""
                    DELETE FROM cp_history
                    WHERE recorded_at < ?
                    LIMIT ?
                """, (cutoff_date, batch_size))

                deleted = cursor.rowcount
                if deleted == 0:
                    break

                total_deleted += deleted
                conn.commit()
                time.sleep(0.1)  # 避免长时间锁表

            return CleanupResult(
                success=True,
                operation="sqlite_cp_history",
                deleted_count=total_deleted,
                freed_bytes=total_deleted * 134,  # 估算每条约134字节
                details={"cutoff_date": cutoff_date, "retention_days": retention_days}
            )
        except Exception as e:
            return CleanupResult(success=False, operation="sqlite_cp_history", errors=[str(e)])
        finally:
            conn.close()

    def cleanup_price_history(self, retention_days: int = None) -> CleanupResult:
        """清理过期的价格历史"""
        retention_days = retention_days or SQLITE_RETENTION['price_history']
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM price_history WHERE record_date < ?", (cutoff_date,))
            to_delete = cursor.fetchone()[0]

            if to_delete == 0:
                return CleanupResult(success=True, operation="sqlite_price_history", deleted_count=0)

            cursor.execute("DELETE FROM price_history WHERE record_date < ?", (cutoff_date,))
            deleted = cursor.rowcount
            conn.commit()

            return CleanupResult(
                success=True,
                operation="sqlite_price_history",
                deleted_count=deleted,
                freed_bytes=deleted * 100,
                details={"cutoff_date": cutoff_date}
            )
        except Exception as e:
            return CleanupResult(success=False, operation="sqlite_price_history", errors=[str(e)])
        finally:
            conn.close()

    def cleanup_alerts(self, retention_days: int = None) -> CleanupResult:
        """清理过期的告警记录"""
        retention_days = retention_days or SQLITE_RETENTION['alerts']
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE created_at < ?", (cutoff_date,))
            to_delete = cursor.fetchone()[0]

            if to_delete == 0:
                return CleanupResult(success=True, operation="sqlite_alerts", deleted_count=0)

            cursor.execute("DELETE FROM alerts WHERE created_at < ?", (cutoff_date,))
            deleted = cursor.rowcount
            conn.commit()

            return CleanupResult(
                success=True,
                operation="sqlite_alerts",
                deleted_count=deleted,
                freed_bytes=deleted * 200,
                details={"cutoff_date": cutoff_date}
            )
        except Exception as e:
            return CleanupResult(success=False, operation="sqlite_alerts", errors=[str(e)])
        finally:
            conn.close()


# ==================== SQLite VACUUM优化 ====================

class SQLiteVacuumCleaner:
    """
    SQLite VACUUM优化清理

    策略：仅当碎片空间超过阈值时才执行VACUUM
    - 碎片超过100MB
    - 或删除记录超过总记录10%
    - 低峰期执行（凌晨02:00-04:00）
    """

    # 碎片阈值（字节）
    FRAGMENT_THRESHOLD = 100 * 1024 * 1024  # 100MB

    # 删除比例阈值
    DELETE_RATIO_THRESHOLD = 0.1  # 10%

    @classmethod
    def get_fragment_info(cls, conn: sqlite3.Connection) -> Dict:
        """
        获取数据库碎片信息

        Returns:
            {
                'page_count': int,
                'freelist_count': int,  # 空闲页数
                'fragment_bytes': int,   # 碎片估算
                'needs_vacuum': bool
            }
        """
        cursor = conn.cursor()

        # 获取页信息
        page_info = cursor.execute("PRAGMA page_count").fetchone()[0]
        page_size = cursor.execute("PRAGMA page_size").fetchone()[0]
        freelist_count = cursor.execute("PRAGMA freelist_count").fetchone()[0]

        # 碎片估算：空闲页占用的空间
        fragment_bytes = freelist_count * page_size

        # 判断是否需要VACUUM
        # 条件1：碎片超过100MB
        # 条件2：空闲页超过总页数的10%
        needs_vacuum = (
            fragment_bytes > cls.FRAGMENT_THRESHOLD or
            (page_info > 0 and freelist_count / page_info > cls.DELETE_RATIO_THRESHOLD)
        )

        return {
            'page_count': page_info,
            'page_size': page_size,
            'freelist_count': freelist_count,
            'fragment_bytes': fragment_bytes,
            'fragment_mb': round(fragment_bytes / 1024 / 1024, 2),
            'needs_vacuum': needs_vacuum,
            'reason': '碎片超限' if fragment_bytes > cls.FRAGMENT_THRESHOLD else
                     '空闲页比例过高' if freelist_count / page_info > cls.DELETE_RATIO_THRESHOLD else '正常'
        }

    @classmethod
    def should_vacuum(cls, db_path: str = None) -> Tuple[bool, str]:
        """
        判断是否应该执行VACUUM

        Returns:
            (should_vacuum, reason)
        """
        db_path = db_path or SQLITE_PATH
        conn = sqlite3.connect(db_path)
        try:
            info = cls.get_fragment_info(conn)
            return info['needs_vacuum'], info['reason']
        finally:
            conn.close()

    @classmethod
    def vacuum_if_needed(cls, db_path: str = None) -> CleanupResult:
        """
        条件执行VACUUM

        仅在以下条件满足时执行：
        1. 碎片超过100MB 或 空闲页比例>10%
        2. 当前时间在低峰期（02:00-04:00）

        Returns:
            清理结果
        """
        db_path = db_path or SQLITE_PATH
        conn = sqlite3.connect(db_path)
        try:
            # 检查是否需要VACUUM
            info = cls.get_fragment_info(conn)
            if not info['needs_vacuum']:
                return CleanupResult(
                    success=True,
                    operation="sqlite_vacuum",
                    deleted_count=0,
                    freed_bytes=0,
                    details={"skipped": True, "reason": info['reason']}
                )

            # 检查是否在低峰期
            current_hour = datetime.now().hour
            if current_hour < 2 or current_hour >= 4:
                return CleanupResult(
                    success=True,
                    operation="sqlite_vacuum",
                    deleted_count=0,
                    freed_bytes=0,
                    details={"skipped": True, "reason": "非低峰期(02:00-04:00)"}
                )

            # 执行VACUUM
            before_size = Path(db_path).stat().st_size
            conn.execute("VACUUM")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # 同时清理WAL
            after_size = Path(db_path).stat().st_size

            freed_bytes = before_size - after_size if after_size < before_size else 0

            return CleanupResult(
                success=True,
                operation="sqlite_vacuum",
                deleted_count=0,
                freed_bytes=freed_bytes,
                details={
                    "fragment_mb_before": info['fragment_mb'],
                    "size_before_mb": round(before_size / 1024 / 1024, 2),
                    "size_after_mb": round(after_size / 1024 / 1024, 2),
                    "reason": info['reason']
                }
            )
        except Exception as e:
            return CleanupResult(success=False, operation="sqlite_vacuum", errors=[str(e)])
        finally:
            conn.close()


# ==================== cp_history冷热分离 ====================

class CPHistoryColdHotSeparator:
    """
    cp_history 冷热分离

    策略：
    - 热数据（is_hot=1）：2年内的数据，查询默认返回
    - 冷数据（is_hot=0）：超过2年的数据，需要时再查询

    迁移：
    - 添加 is_hot 字段
    - 自动标记热/冷数据
    """

    # 热数据保留期（天）
    HOT_DATA_DAYS = 730  # 2年

    @classmethod
    def migrate_add_is_hot_field(cls) -> Tuple[bool, str]:
        """
        迁移：为 cp_history 表添加 is_hot 字段

        Returns:
            (success, message)
        """
        conn = sqlite3.connect(str(SQLITE_PATH))
        try:
            cursor = conn.cursor()

            # 检查字段是否已存在
            cursor.execute("PRAGMA table_info(cp_history)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'is_hot' not in columns:
                cursor.execute("ALTER TABLE cp_history ADD COLUMN is_hot INTEGER DEFAULT 1")
                conn.commit()
                return True, "已添加 is_hot 字段"
            else:
                return True, "is_hot 字段已存在"
        except Exception as e:
            return False, f"迁移失败: {e}"
        finally:
            conn.close()

    @classmethod
    def update_hot_flag(cls) -> CleanupResult:
        """
        更新冷热标记

        - 2年内的数据：is_hot = 1
        - 超过2年的数据：is_hot = 0

        Returns:
            清理结果
        """
        conn = sqlite3.connect(str(SQLITE_PATH))
        try:
            cursor = conn.cursor()

            # 检查字段是否存在
            cursor.execute("PRAGMA table_info(cp_history)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'is_hot' not in columns:
                return CleanupResult(
                    success=False,
                    operation="cp_history_hot_flag",
                    errors=["is_hot 字段不存在，请先执行 migrate_add_is_hot_field"]
                )

            cutoff_date = (datetime.now() - timedelta(days=cls.HOT_DATA_DAYS)).strftime("%Y-%m-%d")

            # 更新冷数据标记
            cursor.execute("""
                UPDATE cp_history
                SET is_hot = 0
                WHERE recorded_at < ? AND (is_hot = 1 OR is_hot IS NULL)
            """, (cutoff_date,))
            cold_count = cursor.rowcount

            # 更新热数据标记
            cursor.execute("""
                UPDATE cp_history
                SET is_hot = 1
                WHERE recorded_at >= ? AND is_hot = 0
            """, (cutoff_date,))
            hot_count = cursor.rowcount

            conn.commit()

            return CleanupResult(
                success=True,
                operation="cp_history_hot_flag",
                deleted_count=0,
                freed_bytes=0,
                details={
                    "cold_to_hot": hot_count,
                    "hot_to_cold": cold_count,
                    "cutoff_date": cutoff_date
                }
            )
        except Exception as e:
            return CleanupResult(success=False, operation="cp_history_hot_flag", errors=[str(e)])
        finally:
            conn.close()

    @classmethod
    def get_hot_status(cls) -> Dict:
        """
        获取冷热数据统计

        Returns:
            冷热数据统计信息
        """
        conn = sqlite3.connect(str(SQLITE_PATH))
        try:
            cursor = conn.cursor()

            # 检查字段是否存在
            cursor.execute("PRAGMA table_info(cp_history)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'is_hot' not in columns:
                return {"error": "is_hot 字段不存在"}

            # 统计热数据
            cursor.execute("SELECT COUNT(*) FROM cp_history WHERE is_hot = 1")
            hot_count = cursor.fetchone()[0]

            # 统计冷数据
            cursor.execute("SELECT COUNT(*) FROM cp_history WHERE is_hot = 0")
            cold_count = cursor.fetchone()[0]

            # 获取最早和最新的记录日期
            cursor.execute("SELECT MIN(recorded_at), MAX(recorded_at) FROM cp_history")
            min_date, max_date = cursor.fetchone()

            return {
                "hot_count": hot_count,
                "cold_count": cold_count,
                "total_count": hot_count + cold_count,
                "oldest_date": min_date,
                "newest_date": max_date,
                "hot_data_days": cls.HOT_DATA_DAYS
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            conn.close()


# ==================== DuckDB清理 ====================

class DuckDBCleaner:
    """DuckDB数据清理"""

    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or DUCKDB_PATH)
        self._conn = None

    def _get_conn(self):
        """获取DuckDB连接"""
        import duckdb
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path, read_only=False)
        return self._conn

    def init_archive_table(self):
        """初始化周K归档表"""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weekly_kline_archive (
                code VARCHAR(6) NOT NULL,
                trade_week VARCHAR(7) NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume BIGINT NOT NULL,
                archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code, trade_week)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_weekly_archive_code
            ON weekly_kline_archive(code)
        """)

    def archive_old_daily_klines(self, keep_years: int = 3, batch_size: int = 1000) -> Tuple[int, int]:
        """
        降采样归档旧日K线为周K

        Args:
            keep_years: 保留年数
            batch_size: 每批处理条数

        Returns:
            (archived_count, batch_count)
        """
        self.init_archive_table()
        conn = self._get_conn()

        cutoff_date = (datetime.now() - timedelta(days=keep_years * 365)).strftime("%Y-%m-%d")
        total_archived = 0

        try:
            # 降采样到周K并归档（使用 INSERT ... ON CONFLICT IGNORE 避免重复）
            result = conn.execute("""
                INSERT INTO weekly_kline_archive
                SELECT
                    code,
                    strftime('%Y-W%V', trade_date::DATE) as trade_week,
                    MIN(open) as open,
                    MAX(high) as high,
                    MIN(low) as low,
                    LAST(close) as close,
                    SUM(volume) as volume,
                    CURRENT_TIMESTAMP as archived_at
                FROM daily_kline
                WHERE trade_date < ?
                GROUP BY code, strftime('%Y-W%V', trade_date::DATE)
            """, [cutoff_date])

            total_archived = result.rowcount
        except Exception as e:
            # 如果归档失败（如表结构问题），记录错误但不阻断清理流程
            print(f"归档旧日K线失败: {e}")
            total_archived = 0

        return total_archived, 1

    def cleanup_old_daily_klines(self, keep_years: int = 3, batch_size: int = 5000) -> CleanupResult:
        """
        清理过期的日K线数据（分批删除）

        Args:
            keep_years: 保留年数
            batch_size: 每批删除条数

        Returns:
            清理结果
        """
        conn = self._get_conn()
        cutoff_date = (datetime.now() - timedelta(days=keep_years * 365)).strftime("%Y-%m-%d")

        try:
            # 先执行归档（如果表不存在会创建）
            archived_count, _ = self.archive_old_daily_klines(keep_years)

            # 直接删除旧数据（DuckDB 不支持 DELETE ... LIMIT）
            result = conn.execute("""
                DELETE FROM daily_kline
                WHERE trade_date < ?
            """, [cutoff_date])

            deleted = result.rowcount

            return CleanupResult(
                success=True,
                operation="duckdb_daily_kline",
                deleted_count=deleted,
                freed_bytes=deleted * 54,  # 每条约54字节
                details={
                    "cutoff_date": cutoff_date,
                    "keep_years": keep_years,
                    "archived_weeks": archived_count
                }
            )
        except Exception as e:
            return CleanupResult(success=False, operation="duckdb_daily_kline", errors=[str(e)])

    def cleanup_old_minute_klines(self, keep_days: int = 14, batch_size: int = 10000) -> CleanupResult:
        """
        清理过期的分钟K线数据（分批删除）

        Args:
            keep_days: 保留天数
            batch_size: 每批删除条数

        Returns:
            清理结果
        """
        conn = self._get_conn()
        cutoff_datetime = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%d %H:%M:%S")

        try:
            total_deleted = 0
            while True:
                # DuckDB 不支持 DELETE ... LIMIT，直接删除符合条件的记录
                result = conn.execute("""
                    DELETE FROM minute_kline
                    WHERE trade_time < ?
                """, [cutoff_datetime])

                deleted = result.rowcount
                if deleted == 0:
                    break

                total_deleted += deleted
                # 分钟K线数据量大，等待一下避免阻塞
                time.sleep(0.1)

            return CleanupResult(
                success=True,
                operation="duckdb_minute_kline",
                deleted_count=total_deleted,
                freed_bytes=total_deleted * 60,  # 每条约60字节
                details={"cutoff_datetime": cutoff_datetime, "keep_days": keep_days}
            )
        except Exception as e:
            return CleanupResult(success=False, operation="duckdb_minute_kline", errors=[str(e)])


# ==================== JSON缓存清理 ====================

class CacheCleaner:
    """
    JSON缓存文件清理

    策略：
    - 可重新下载的缓存（行情、财务）：基于TTL自动清理
    - 用户生成/修改的配置（stock_pool.json）：跳过清理，更新时覆盖
    """

    # 用户配置文件（永不自动删除，更新时覆盖）
    USER_CONFIG_FILES = {
        'stock_pool.json',        # 股票池配置
        'user_settings.json',     # 用户设置
        'watchlist.json',         # 自选股列表
    }

    # 可重新下载的缓存（按TTL清理）
    REDOWNLOADABLE_CACHE = {
        'market_': 1,           # 市场行情缓存：1天
        'fin_': 7,               # 财务数据缓存：7天
        'stock_list': 7,         # 股票列表缓存：7天
        'stock_list_cache': 7,   # 股票列表缓存：7天
        'market_trends': 7,      # 市场趋势：7天
        'enhancer_status': 30,   # 增强器状态：30天
        'cp_history': 30,       # 战力历史JSON：30天
        'tushare_ts_': 7,       # Tushare原始数据：7天
    }

    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR

    def is_user_config(self, filename: str) -> bool:
        """检查是否为用户配置文件"""
        return filename in self.USER_CONFIG_FILES

    def cleanup_expired_cache(self) -> CleanupResult:
        """
        清理过期的缓存文件（基于文件修改时间）

        策略：
        - 用户配置文件：永不自动删除
        - 可下载缓存：按TTL清理

        Returns:
            清理结果
        """
        import time

        total_deleted = 0
        total_freed = 0
        skipped_user_config = 0
        errors = []

        try:
            for filepath in self.data_dir.iterdir():
                if not filepath.is_file() or filepath.suffix != '.json':
                    continue

                filename = filepath.name

                # 跳过用户配置文件
                if self.is_user_config(filename):
                    skipped_user_config += 1
                    continue

                # 检查是否匹配缓存模式
                matched_ttl = None
                for pattern, ttl in self.REDOWNLOADABLE_CACHE.items():
                    if pattern in filename:
                        matched_ttl = ttl
                        break

                if matched_ttl is None:
                    continue

                # 检查是否过期
                file_age_days = (time.time() - filepath.stat().st_mtime) / 86400
                if file_age_days > matched_ttl:
                    try:
                        file_size = filepath.stat().st_size
                        filepath.unlink()
                        total_deleted += 1
                        total_freed += file_size
                    except Exception as e:
                        errors.append(f"删除{filename}失败: {e}")

            return CleanupResult(
                success=len(errors) == 0,
                operation="json_cache",
                deleted_count=total_deleted,
                freed_bytes=total_freed,
                errors=errors,
                details={
                    "cleaned_patterns": list(self.REDOWNLOADABLE_CACHE.keys()),
                    "skipped_user_config": skipped_user_config
                }
            )
        except Exception as e:
            return CleanupResult(success=False, operation="json_cache", errors=[str(e)])


# ==================== 统一清理调度器 ====================

class LifecycleCleanupScheduler:
    """
    统一清理调度器

    核心原则：先备份后清理
    执行顺序：
    1. 检查幂等性
    2. 创建清理保护备份
    3. 执行数据备份
    4. 清理JSON缓存
    5. 清理DuckDB K线
    6. 清理SQLite历史
    7. 记录审计日志
    8. 检查存储水位
    """

    def __init__(self):
        self.sqlite_cleaner = SQLiteCleaner()
        self.duckdb_cleaner = DuckDBCleaner()
        self.cache_cleaner = CacheCleaner()

    def daily_cleanup(self) -> Dict:
        """
        执行每日清理任务

        Returns:
            清理报告
        """
        # Step 0: 检查幂等性
        if CleanupState.is_running():
            return {"success": False, "error": "清理任务正在运行，跳过"}

        if CleanupState.is_already_cleaned_today():
            return {"success": False, "error": "今日已执行过清理，跳过"}

        # 获取锁
        if not CleanupState.acquire_lock():
            return {"success": False, "error": "无法获取清理锁"}

        results = {
            "timestamp": datetime.now().isoformat(),
            "operations": []
        }

        try:
            # Step 0.5: 清理前核心数据校验
            is_valid, error_msg = CleanupValidator.pre_cleanup_check()
            if not is_valid:
                return {"success": False, "error": f"清理前校验失败: {error_msg}"}

            # Step 1-2: 创建清理保护备份（由调用者负责，这里只记录）
            results["operations"].append({"operation": "protected_backup", "status": "skipped"})

            # Step 3: 清理JSON缓存
            cache_result = self.cache_cleaner.cleanup_expired_cache()
            results["operations"].append({
                "operation": "json_cache",
                "status": "success" if cache_result.success else "failed",
                "deleted_count": cache_result.deleted_count,
                "freed_bytes": cache_result.freed_bytes
            })

            # Step 4: 清理DuckDB K线
            daily_result = self.duckdb_cleaner.cleanup_old_daily_klines(
                keep_years=DUCKDB_RETENTION['daily_kline'] // 365
            )
            results["operations"].append({
                "operation": "duckdb_daily_kline",
                "status": "success" if daily_result.success else "failed",
                "deleted_count": daily_result.deleted_count,
                "freed_bytes": daily_result.freed_bytes
            })

            minute_result = self.duckdb_cleaner.cleanup_old_minute_klines(
                keep_days=DUCKDB_RETENTION['minute_kline_core']
            )
            results["operations"].append({
                "operation": "duckdb_minute_kline",
                "status": "success" if minute_result.success else "failed",
                "deleted_count": minute_result.deleted_count,
                "freed_bytes": minute_result.freed_bytes
            })

            # Step 5: SQLite历史清理（每周执行一次）
            if datetime.now().weekday() == 6:  # 周日
                cp_result = self.sqlite_cleaner.cleanup_cp_history()
                results["operations"].append({
                    "operation": "sqlite_cp_history",
                    "status": "success" if cp_result.success else "failed",
                    "deleted_count": cp_result.deleted_count,
                    "freed_bytes": cp_result.freed_bytes
                })

                price_result = self.sqlite_cleaner.cleanup_price_history()
                results["operations"].append({
                    "operation": "sqlite_price_history",
                    "status": "success" if price_result.success else "failed",
                    "deleted_count": price_result.deleted_count,
                    "freed_bytes": price_result.freed_bytes
                })

                alerts_result = self.sqlite_cleaner.cleanup_alerts()
                results["operations"].append({
                    "operation": "sqlite_alerts",
                    "status": "success" if alerts_result.success else "failed",
                    "deleted_count": alerts_result.deleted_count,
                    "freed_bytes": alerts_result.freed_bytes
                })

            # Step 6: 记录审计日志
            self._log_audit(results)

            # Step 7: 标记完成
            CleanupState.mark_completed("daily_cleanup", results)

            results["success"] = True

        except Exception as e:
            results["error"] = str(e)
            results["success"] = False

        finally:
            CleanupState.release_lock()

        return results

    def _log_audit(self, results: Dict):
        """记录审计日志到SQLite"""
        conn = sqlite3.connect(str(SQLITE_PATH))
        try:
            for op in results.get("operations", []):
                audit = CleanupAudit(
                    timestamp=results["timestamp"],
                    operation=op.get("operation", ""),
                    details=op,
                    records_deleted=op.get("deleted_count", 0),
                    space_freed_bytes=op.get("freed_bytes", 0),
                    status="success" if op.get("status") == "success" else "failed"
                )
                CleanupAuditor.log(conn, audit)
            conn.commit()
        finally:
            conn.close()


# ==================== 存储空间检查 ====================

def check_storage_water_level() -> Dict:
    """
    检查存储水位

    Returns:
        存储状态信息
    """
    import shutil

    total, used, free = shutil.disk_usage(DATA_DIR)
    usage_percent = (used / total) * 100

    return {
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "usage_percent": round(usage_percent, 2),
        "status": "normal" if usage_percent < 70 else
                  "warning" if usage_percent < 80 else
                  "danger" if usage_percent < 95 else "critical"
    }


# ==================== 清理报告生成 ====================

def generate_cleanup_report(results: Dict) -> str:
    """生成清理报告"""
    report = f"""
📊 数据清理报告 ({results.get('timestamp', datetime.now().isoformat())})

✅ 执行结果：
"""
    for op in results.get("operations", []):
        status_icon = "✅" if op.get("status") == "success" else "❌"
        report += f"{status_icon} {op.get('operation')}: 删除 {op.get('deleted_count', 0)} 条，释放 {op.get('freed_bytes', 0) / 1024:.1f} KB\n"

    storage = check_storage_water_level()
    report += f"""
📦 当前存储状态：
├── 使用率: {storage['usage_percent']}%
├── 状态: {storage['status']}
└── 可用空间: {storage['free_bytes'] / 1024 / 1024 / 1024:.2f} GB
"""
    return report
