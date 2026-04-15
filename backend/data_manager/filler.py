"""
数据填充模块 - Data Filler
===========================
职责：从外部数据源填充历史数据到本地存储

包含：
- ExRightFactorFiller: 除权因子填充器（P0）
- KlineFiller: K线数据填充器（规划中）
- MinuteKlineFiller: 分钟K线填充器（规划中）

与 cleanup.py 共同完成数据的完整生命周期管理：
- filler: 初始化/补数（历史数据）
- cleanup: 过期删除
"""

import sqlite3
import time
import gc
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path


def _ensure_path():
    """确保data_manager在sys.path中"""
    import sys
    from pathlib import Path
    backend_dir = Path(__file__).parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


def _get_duckdb_store():
    """获取DuckDB store，支持直接运行和包导入"""
    _ensure_path()
    try:
        from .duckdb_store import get_duckdb_store
    except ImportError:
        from data_manager.duckdb_store import get_duckdb_store
    return get_duckdb_store()


def _get_cp_history_store():
    """获取CP历史存储，支持直接运行和包导入"""
    _ensure_path()
    try:
        from .cp_history_store import get_cp_history_store
    except ImportError:
        from data_manager.cp_history_store import get_cp_history_store
    return get_cp_history_store()


def _get_kline_record():
    """获取KlineRecord类，支持直接运行和包导入"""
    _ensure_path()
    try:
        from .duckdb_store import KlineRecord
    except ImportError:
        from data_manager.duckdb_store import KlineRecord
    return KlineRecord


# ==================== 路径配置 ====================

DATA_DIR = Path("/home/ailearn/projects/TradeSnake/data")
DB_PATH = DATA_DIR / "tradesnake.db"


# ==================== ST/退市股过滤 ====================

def _is_st_stock(name: str) -> bool:
    """判断股票是否为ST/*ST/退市股"""
    if not name:
        return False
    return '*' in name or 'ST' in name or '退市' in name


def _get_active_stock_codes(db_path: str = None) -> List[str]:
    """获取可交易股票代码（排除ST/*ST/退市股）

    我们的交易系统不关注ST、退市、停牌股，填充时直接跳过。
    这避免了：
    - 大量无意义的API请求（这些股票数据源确实没有）
    - 填充状态表中的僵尸记录
    - 战力引擎处理无效数据
    """
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    # 排除名称含 ST/*/退市 的股票
    cursor.execute("""
        SELECT code FROM stocks
        WHERE name NOT LIKE '%*%'
          AND name NOT LIKE '%ST%'
          AND name NOT LIKE '%退市%'
    """)
    codes = [row[0] for row in cursor.fetchall()]
    conn.close()
    return codes


# ==================== 重试机制 ====================

def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """
    指数退避延迟计算

    Args:
        attempt: 当前重试次数 (0-based)
        base_delay: 基础延迟秒数
        max_delay: 最大延迟秒数

    Returns:
        延迟秒数
    """
    delay = min(base_delay * (2 ** attempt), max_delay)
    # 添加随机抖动 (±10%)
    import random
    jitter = delay * 0.1 * random.uniform(-1, 1)
    return delay + jitter


def is_retriable_error(exception: Exception) -> Tuple[bool, str]:
    """
    判断异常是否可重试

    Args:
        exception: 异常对象

    Returns:
        (is_retriable, error_category)
    """
    error_msg = str(exception).lower()
    error_type = type(exception).__name__

    # 网络错误 - 可重试
    if 'timeout' in error_msg or 'connection' in error_msg or 'network' in error_msg:
        return True, 'network'
    if 'reset' in error_msg or 'refused' in error_msg:
        return True, 'network'

    # 限流错误 - 可重试
    if 'rate limit' in error_msg or '429' in error_msg or 'too many' in error_msg:
        return True, 'rate_limit'

    # 临时服务不可用 - 可重试
    if '503' in error_msg or '502' in error_msg or 'service unavailable' in error_msg:
        return True, 'service'

    # 数据源熔断 - 可重试
    if 'circuit' in error_msg or 'breaker' in error_msg:
        return True, 'circuit'

    # 权限/认证问题 - 不可重试
    if 'auth' in error_msg or 'permission' in error_msg or '401' in error_msg or '403' in error_msg:
        return False, 'auth'

    # 业务逻辑错误 - 不可重试
    if 'invalid' in error_msg or 'not found' in error_msg or '404' in error_msg:
        return False, 'business'

    # 默认为可重试（保守策略）
    return True, 'unknown'


# ==================== 数据类 ====================

@dataclass
class FillResult:
    """填充结果"""
    success: int = 0
    failed: int = 0
    total_records: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class FillStatus:
    """填充状态"""
    code: str
    last_date: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    retry_count: int = 0
    error_message: str = None


# ==================== ExRightFactorFiller ====================

class ExRightFactorFiller:
    """
    除权因子填充器

    职责：
    1. 从 Tushare pro.adj_factor 获取全市场股票的复权因子
    2. 存储到 SQLite ex_right_factor 表
    3. 支持增量更新（只获取最新变化的部分）

    表结构：
    CREATE TABLE ex_right_factor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        adj_type TEXT NOT NULL,      -- qfq前复权, hfq后复权
        factor REAL NOT NULL,
        created_at TEXT,
        UNIQUE(symbol, trade_date, adj_type)
    )

    状态表：
    CREATE TABLE ex_right_fill_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        last_date TEXT,
        status TEXT DEFAULT 'pending',
        retry_count INTEGER DEFAULT 0,
        error_message TEXT,
        updated_at TEXT
    )
    """

    def __init__(self, db_path: str = None, rate_limit_sleep: float = 0.5):
        """
        初始化除权因子填充器

        Args:
            db_path: 数据库路径
            rate_limit_sleep: 限流睡眠时间（秒），默认0.5秒避免超过Tushare 120次/分钟限制
        """
        self.db_path = db_path or str(DB_PATH)
        self.rate_limit_sleep = rate_limit_sleep
        self._ensure_tables()

    def _ensure_tables(self):
        """确保状态表存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 启用 WAL 模式
        cursor.execute("PRAGMA journal_mode=WAL")

        # 状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ex_right_fill_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                last_date TEXT,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _get_stock_codes(self) -> List[str]:
        """获取可交易股票代码（排除ST/*ST/退市股）"""
        return _get_active_stock_codes(self.db_path)

    def _convert_to_ts_code(self, code: str) -> str:
        """转换代码为Tushare格式"""
        code = code.strip()
        # 去掉 sh/sz 前缀（如 sh600088 -> 600088）
        if code.startswith('sh') or code.startswith('sz'):
            code = code[2:]
        code = code.zfill(6)
        suffix = '.SH' if code.startswith('6') else '.SZ'
        return f"{code}{suffix}"

    def _convert_from_ts_code(self, ts_code: str) -> str:
        """从Tushare格式转换回标准代码"""
        return ts_code.replace('.SH', '').replace('.SZ', '')

    def _get_status(self, code: str) -> Optional[FillStatus]:
        """获取填充状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code, last_date, status, retry_count, error_message
            FROM ex_right_fill_status WHERE code = ?
        """, (code,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return FillStatus(
                code=row[0],
                last_date=row[1],
                status=row[2],
                retry_count=row[3],
                error_message=row[4]
            )
        return None

    def _update_status(self, code: str, status: str, last_date: str = None,
                       error_message: str = None, increment_retry: bool = False):
        """更新填充状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        current_retry = 0
        if increment_retry:
            cursor.execute("SELECT retry_count FROM ex_right_fill_status WHERE code = ?", (code,))
            row = cursor.fetchone()
            if row:
                current_retry = row[0] + 1

        cursor.execute("""
            INSERT OR REPLACE INTO ex_right_fill_status
            (code, last_date, status, retry_count, error_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (code, last_date, status, current_retry, error_message,
              datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def _fetch_from_tushare(self, ts_code: str) -> List[Dict]:
        """
        从Tushare获取单只股票的复权因子

        Args:
            ts_code: Tushare格式的股票代码

        Returns:
            复权因子列表
        """
        try:
            import tushare as ts
        except ImportError:
            print("Tushare未安装")
            return []

        try:
            pro = ts.pro_api()
            df = pro.adj_factor(ts_code=ts_code, trade_date='')

            if df is None or len(df) == 0:
                return []

            factors = []
            for _, row in df.iterrows():
                factors.append({
                    'symbol': self._convert_from_ts_code(ts_code),
                    'trade_date': row['trade_date'],
                    'adj_type': 'qfq',
                    'factor': row['adj_factor']
                })

            return factors

        except Exception as e:
            print(f"获取 {ts_code} 复权因子失败: {e}")
            return []

    def _save_factors(self, factors: List[Dict]):
        """批量保存复权因子"""
        if not factors:
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        data = [
            (
                f['symbol'],
                f['trade_date'],
                f['adj_type'],
                f['factor'],
                datetime.now().isoformat()
            )
            for f in factors
        ]

        cursor.executemany("""
            INSERT OR REPLACE INTO ex_right_factor
            (symbol, trade_date, adj_type, factor, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, data)

        conn.commit()
        conn.close()

        return len(data)

    def fill_stock(self, code: str, force: bool = False) -> Tuple[int, str]:
        """
        填充单只股票的除权因子

        Args:
            code: 股票代码
            force: 是否强制重新填充（忽略已有状态）

        Returns:
            (插入记录数, 状态)
        """
        # 检查状态
        if not force:
            status = self._get_status(code)
            if status and status.status == 'completed':
                return 0, 'skipped'

        self._update_status(code, 'running')

        ts_code = self._convert_to_ts_code(code)
        factors = self._fetch_from_tushare(ts_code)

        if not factors:
            self._update_status(code, 'failed', error_message='No data from Tushare')
            return 0, 'failed'

        count = self._save_factors(factors)
        last_date = max(f['trade_date'] for f in factors)
        self._update_status(code, 'completed', last_date=last_date)

        return count, 'success'

    def fill_all(self, codes: List[str] = None, limit: int = None,
                 rate_limit: float = None) -> FillResult:
        """
        填充所有（或指定）股票的除权因子

        Args:
            codes: 股票代码列表，None表示所有股票
            limit: 限制处理数量
            rate_limit: 限流睡眠时间（秒）

        Returns:
            FillResult: 填充结果统计
        """
        result = FillResult()

        if codes is None:
            codes = self._get_stock_codes()

        if limit:
            codes = codes[:limit]

        sleep_time = rate_limit or self.rate_limit_sleep
        total = len(codes)

        print(f"开始填充除权因子，共 {total} 只股票")

        for i, code in enumerate(codes):
            try:
                count, status = self.fill_stock(code)

                result.total_records += count
                if status == 'success':
                    result.success += 1
                elif status == 'skipped':
                    pass  # 跳过不计数
                else:
                    result.failed += 1
                    result.errors.append(f"{code}: {status}")

                # 限流控制
                if i < total - 1:
                    time.sleep(sleep_time)

                # 进度显示
                if (i + 1) % 100 == 0:
                    print(f"进度: {i+1}/{total}, 成功: {result.success}, 失败: {result.failed}")
                    gc.collect()  # 内存优化

            except Exception as e:
                result.failed += 1
                result.errors.append(f"{code}: {str(e)}")
                self._update_status(code, 'failed', error_message=str(e))

        gc.collect()
        print(f"填充完成: 成功 {result.success}, 失败 {result.failed}, 总记录 {result.total_records}")
        return result

    def fill_incremental(self, days_back: int = 7) -> FillResult:
        """
        增量更新：只获取最近几天有变化的股票

        Args:
            days_back: 检查最近多少天内的变化

        Returns:
            FillResult: 填充结果统计
        """
        # 获取最近有K线数据变化的股票
        # 这里简化处理，实际应该检查Tushare的公告日期
        cutoff_date = (date.today() - timedelta(days=days_back)).strftime('%Y%m%d')

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取最近有除权事件的股票（简化版：获取所有pending状态的）
        cursor.execute("""
            SELECT code FROM ex_right_fill_status
            WHERE status IN ('pending', 'failed')
            LIMIT 500
        """)

        codes = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not codes:
            print("没有需要增量更新的股票")
            return FillResult()

        return self.fill_all(codes=codes)

    def resume(self) -> FillResult:
        """
        断点续跑：继续上次失败的填充任务

        Returns:
            FillResult: 填充结果统计
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT code FROM ex_right_fill_status
            WHERE status = 'failed' AND retry_count < 3
        """)

        codes = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not codes:
            print("没有需要重试的股票")
            return FillResult()

        print(f"开始断点续跑，共 {len(codes)} 只股票")

        # 重试时增加重试计数
        for code in codes:
            self._update_status(code, 'pending', increment_retry=True)

        return self.fill_all(codes=codes)

    def get_stats(self) -> Dict:
        """获取填充统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 总股票数
        cursor.execute("SELECT COUNT(DISTINCT code) FROM stocks")
        total_stocks = cursor.fetchone()[0]

        # 已处理的股票
        cursor.execute("""
            SELECT COUNT(*) FROM ex_right_fill_status
            WHERE status = 'completed'
        """)
        completed = cursor.fetchone()[0]

        # 失败的股票
        cursor.execute("""
            SELECT COUNT(*) FROM ex_right_fill_status
            WHERE status = 'failed'
        """)
        failed = cursor.fetchone()[0]

        # 除权因子总数
        cursor.execute("SELECT COUNT(*) FROM ex_right_factor")
        total_factors = cursor.fetchone()[0]

        # 涉及股票数
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM ex_right_factor")
        factor_symbols = cursor.fetchone()[0]

        conn.close()

        return {
            'total_stocks': total_stocks,
            'completed': completed,
            'failed': failed,
            'pending': total_stocks - completed - failed,
            'total_factors': total_factors,
            'factor_symbols': factor_symbols,
            'coverage': f"{completed}/{total_stocks}" if total_stocks > 0 else "0/0"
        }


# ==================== KlineFiller ====================

class KlineFiller:
    """
    K线数据填充器

    职责：
    1. 从 Tushare 获取日K线数据
    2. 检测数据缺口
    3. 存储到 DuckDB daily_kline 表
    4. 支持断点续跑

    表结构 (DuckDB daily_kline):
    - code: 股票代码
    - trade_date: 交易日期
    - open/high/low/close: 价格
    - volume: 成交量
    - amount: 成交额
    - change_pct: 涨跌幅
    - adj_close: 复权收盘价

    状态表 (SQLite kline_fill_status):
    - code: 股票代码
    - last_date: 最后填充日期
    - status: pending/running/completed/failed
    - retry_count: 重试次数
    """

    def __init__(self, db_path: str = None, rate_limit_sleep: float = 0.5):
        """
        初始化K线填充器

        Args:
            db_path: SQLite数据库路径（存储状态）
            rate_limit_sleep: 限流睡眠时间（秒）
        """
        self.db_path = db_path or str(DB_PATH)
        self.rate_limit_sleep = rate_limit_sleep
        self._ensure_tables()

        # 延迟导入避免循环依赖
        self.duckdb = _get_duckdb_store()

    def _ensure_tables(self):
        """确保状态表存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 启用 WAL 模式
        cursor.execute("PRAGMA journal_mode=WAL")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kline_fill_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                last_date TEXT,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _get_stock_codes(self) -> List[str]:
        """获取可交易股票代码（排除ST/*ST/退市股）"""
        return _get_active_stock_codes(self.db_path)

    def _convert_to_ts_code(self, code: str) -> str:
        """转换代码为Tushare格式"""
        code = code.strip()
        # 去掉 sh/sz 前缀（如 sh600088 -> 600088）
        if code.startswith('sh') or code.startswith('sz'):
            code = code[2:]
        code = code.zfill(6)
        suffix = '.SH' if code.startswith('6') else '.SZ'
        return f"{code}{suffix}"

    def _get_existing_date_range(self, code: str) -> Tuple[Optional[str], Optional[str]]:
        """获取某股票已有数据的日期范围"""
        try:
            # 使用 DuckDB 聚合查询直接获取 MIN/MAX，避免 limit=1 只返回最新一条的问题
            min_date, max_date = self.duckdb.get_date_range(code)
            if min_date and max_date:
                # trade_date 格式为 YYYY-MM-DD，转换为 YYYYMMDD
                min_str = min_date.replace('-', '') if '-' in min_date else min_date
                max_str = max_date.replace('-', '') if '-' in max_date else max_date
                return min_str, max_str
        except Exception:
            pass
        return None, None

    def _detect_gaps(self, code: str, start_date: str, end_date: str) -> List[Tuple[str, str]]:
        """
        检测数据缺口（使用交易日历避免周末/节假日误判）

        Args:
            code: 股票代码
            start_date: 目标开始日期 (YYYYMMDD)
            end_date: 目标结束日期 (YYYYMMDD)

        Returns:
            [(gap_start, gap_end), ...] 缺口区间列表
        """
        existing_min, existing_max = self._get_existing_date_range(code)

        # 尝试使用交易日历进行精确缺口检测
        try:
            trade_cal = TradeCalendar()
            # 获取交易日列表
            all_trading_days = trade_cal.get_trading_days_between(start_date, end_date)
            if not all_trading_days:
                # 没有交易日历数据，回退到简单检测
                return self._detect_gaps_simple(existing_min, existing_max, start_date, end_date)

            existing_trading_days = set()
            if existing_min and existing_max:
                existing_trading_days = set(
                    trade_cal.get_trading_days_between(existing_min, existing_max)
                )

            # 找出缺失的交易日在all_trading_days中但不在existing_trading_days中的
            missing_days = [d for d in all_trading_days if d not in existing_trading_days]

            if not missing_days:
                return []  # 没有缺口

            # 将连续的缺失日期合并为区间
            gaps = self._merge_missing_days_to_gaps(missing_days)
            return gaps

        except Exception as e:
            # 交易日历出错，回退到简单检测
            return self._detect_gaps_simple(existing_min, existing_max, start_date, end_date)

    def _detect_gaps_simple(self, existing_min: str, existing_max: str,
                           start_date: str, end_date: str) -> List[Tuple[str, str]]:
        """
        简单缺口检测（不使用交易日历）

        Args:
            existing_min: 现有数据最小日期
            existing_max: 现有数据最大日期
            start_date: 目标开始日期
            end_date: 目标结束日期

        Returns:
            [(gap_start, gap_end), ...] 缺口区间列表
        """
        if existing_min is None:
            # 完全新数据
            return [(start_date, end_date)]

        gaps = []
        from datetime import datetime as dt

        start = dt.strptime(start_date, '%Y%m%d')
        end = dt.strptime(end_date, '%Y%m%d')
        existing_start = dt.strptime(existing_min, '%Y%m%d')
        existing_end = dt.strptime(existing_max, '%Y%m%d')

        # 检查开头缺口
        if existing_start > start:
            gaps.append((start_date, existing_min))

        # 检查结尾缺口
        if existing_end < end:
            gaps.append((existing_max, end_date))

        return gaps

    def _merge_missing_days_to_gaps(self, missing_days: List[str]) -> List[Tuple[str, str]]:
        """
        将缺失的日期列表合并为连续的区间

        Args:
            missing_days: 缺失的日期列表 (YYYY-MM-DD格式)

        Returns:
            [(gap_start, gap_end), ...] 缺口区间列表
        """
        if not missing_days:
            return []

        from datetime import datetime, timedelta

        # 排序
        missing_days.sort()
        gaps = []
        gap_start = missing_days[0]
        prev_date = datetime.strptime(missing_days[0], '%Y-%m-%d')

        for i in range(1, len(missing_days)):
            current_date = datetime.strptime(missing_days[i], '%Y-%m-%d')
            # 如果当前日期是前一天+1，说明是连续的
            if (current_date - prev_date).days == 1:
                prev_date = current_date
            else:
                # 不连续，保存当前区间并开始新区间
                gaps.append((gap_start, prev_date.strftime('%Y-%m-%d')))
                gap_start = missing_days[i]
                prev_date = current_date

        # 保存最后一个区间
        gaps.append((gap_start, prev_date.strftime('%Y-%m-%d')))

        return gaps

    def _get_status(self, code: str) -> Optional[FillStatus]:
        """获取填充状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code, last_date, status, retry_count, error_message
            FROM kline_fill_status WHERE code = ?
        """, (code,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return FillStatus(
                code=row[0],
                last_date=row[1],
                status=row[2],
                retry_count=row[3],
                error_message=row[4]
            )
        return None

    def _update_status(self, code: str, status: str, last_date: str = None,
                       error_message: str = None, increment_retry: bool = False):
        """更新填充状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        current_retry = 0
        if increment_retry:
            cursor.execute("SELECT retry_count FROM kline_fill_status WHERE code = ?", (code,))
            row = cursor.fetchone()
            if row:
                current_retry = row[0] + 1

        cursor.execute("""
            INSERT OR REPLACE INTO kline_fill_status
            (code, last_date, status, retry_count, error_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (code, last_date, status, current_retry, error_message,
              datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def _fetch_from_tushare(self, code: str, start_date: str, end_date: str) -> List[Dict]:
        """
        从Tushare获取K线数据

        Args:
            code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            K线数据列表
        """
        try:
            import tushare as ts
        except ImportError:
            print("Tushare未安装")
            return []

        try:
            pro = ts.pro_api()
            ts_code = self._convert_to_ts_code(code)

            # Tushare每次最多返回5000条，需要分页
            all_data = []
            page = 1
            page_size = 5000

            while True:
                try:
                    df = pro.daily(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date,
                        limit=page_size,
                        offset=(page - 1) * page_size
                    )

                    if df is None or len(df) == 0:
                        break

                    all_data.append(df)

                    if len(df) < page_size:
                        break

                    page += 1

                    # 限流
                    time.sleep(self.rate_limit_sleep)

                except Exception as e:
                    print(f"分页获取失败 (page={page}): {e}")
                    break

            if not all_data:
                return []

            import pandas as pd
            combined_df = pd.concat(all_data, ignore_index=True)

            # 转换格式
            records = []
            for _, row in combined_df.iterrows():
                records.append({
                    'code': code,
                    'trade_date': row['trade_date'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['vol']),
                    'amount': float(row['amount']) if 'amount' in row else 0.0,
                    'change_pct': float(row['pct_chg']) if 'pct_chg' in row else 0.0,
                })

            return records

        except Exception as e:
            print(f"获取 {code} K线失败: {e}")
            return []

    def _save_klines(self, klines: List[Dict]) -> int:
        """保存K线到DuckDB"""
        if not klines:
            return 0

        KlineRecord = _get_kline_record()

        records = []
        for k in klines:
            # 转换日期格式 YYYYMMDD -> YYYY-MM-DD
            trade_date = k['trade_date']
            if isinstance(trade_date, str) and len(trade_date) == 8:
                trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"

            records.append(KlineRecord(
                code=k['code'],
                trade_date=trade_date,
                open=k['open'],
                high=k['high'],
                low=k['low'],
                close=k['close'],
                volume=k['volume'],
                amount=k.get('amount', 0.0),
                change_pct=k.get('change_pct', 0.0),
                adj_close=k.get('adj_close', 0.0),
            ))

        success, _ = self.duckdb.insert_daily_klines_batch(records)
        return success

    def fill_stock(self, code: str, days_back: int = 730, force: bool = False,
                  max_retries: int = 3) -> Tuple[int, str]:
        """
        填充单只股票的K线（带指数退避重试）

        Args:
            code: 股票代码
            days_back: 填充最近多少天的数据
            force: 是否强制重新填充
            max_retries: 最大重试次数

        Returns:
            (插入记录数, 状态)
        """
        # 检查状态
        if not force:
            status = self._get_status(code)
            if status and status.status == 'completed':
                return 0, 'skipped'

        self._update_status(code, 'running')

        # 计算日期范围
        end_date = date.today().strftime('%Y%m%d')
        start_date = (date.today() - timedelta(days=days_back)).strftime('%Y%m%d')

        # 检测缺口
        gaps = self._detect_gaps(code, start_date, end_date)

        if not gaps:
            self._update_status(code, 'completed', last_date=end_date)
            return 0, 'skipped'

        total_count = 0
        last_error = None

        for gap_start, gap_end in gaps:
            # 对每个缺口尝试获取数据，带重试
            klines = None
            for attempt in range(max_retries):
                try:
                    klines = self._fetch_from_tushare(code, gap_start, gap_end)
                    if klines:
                        break
                    # 如果没有数据但没有异常，检查是否是可重试的错误
                    # 继续重试
                except Exception as e:
                    is_retriable, error_type = is_retriable_error(e)
                    if not is_retriable:
                        last_error = f"{error_type}: {str(e)}"
                        break
                    # 指数退避等待
                    if attempt < max_retries - 1:
                        wait_time = exponential_backoff(attempt, base_delay=1.0)
                        time.sleep(wait_time)
                        last_error = f"{error_type}: {str(e)}"
                    else:
                        last_error = f"{error_type}: {str(e)}"

            if klines:
                count = self._save_klines(klines)
                total_count += count

        if total_count > 0:
            last_date = max(k['trade_date'] for k in klines) if klines else end_date
            self._update_status(code, 'completed', last_date=last_date)
            return total_count, 'success'
        else:
            error_msg = last_error or 'No data from Tushare'
            self._update_status(code, 'failed', error_message=error_msg)
            return 0, 'failed'

    def fill_all(self, codes: List[str] = None, limit: int = None,
                days_back: int = 730, rate_limit: float = None) -> FillResult:
        """
        填充所有（或指定）股票的K线

        Args:
            codes: 股票代码列表，None表示所有股票
            limit: 限制处理数量
            days_back: 填充最近多少天的数据
            rate_limit: 限流睡眠时间（秒）

        Returns:
            FillResult: 填充结果统计
        """
        result = FillResult()

        if codes is None:
            codes = self._get_stock_codes()

        if limit:
            codes = codes[:limit]

        sleep_time = rate_limit or self.rate_limit_sleep
        total = len(codes)

        print(f"开始填充K线，共 {total} 只股票，填充最近 {days_back} 天数据")

        for i, code in enumerate(codes):
            try:
                count, status = self.fill_stock(code, days_back=days_back)

                result.total_records += count
                if status == 'success':
                    result.success += 1
                elif status == 'skipped':
                    pass
                else:
                    result.failed += 1
                    result.errors.append(f"{code}: {status}")

                # 限流控制
                if i < total - 1:
                    time.sleep(sleep_time)

                # 进度显示
                if (i + 1) % 50 == 0:
                    print(f"进度: {i+1}/{total}, 成功: {result.success}, 失败: {result.failed}, 记录: {result.total_records}")

                # 内存优化：每100只强制GC
                if (i + 1) % 100 == 0:
                    gc.collect()

            except Exception as e:
                result.failed += 1
                result.errors.append(f"{code}: {str(e)}")
                self._update_status(code, 'failed', error_message=str(e))

        # 最终GC
        gc.collect()
        print(f"填充完成: 成功 {result.success}, 失败 {result.failed}, 总记录 {result.total_records}")
        return result

    def fill_incremental(self, days_back: int = 7) -> FillResult:
        """
        增量更新：只获取最近几天的新数据

        Args:
            days_back: 检查最近多少天

        Returns:
            FillResult: 填充结果统计
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取已完成的股票
        cursor.execute("""
            SELECT code FROM kline_fill_status
            WHERE status = 'completed'
        """)

        codes = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not codes:
            print("没有已完成的股票，执行全量填充")
            return self.fill_all(limit=100, days_back=days_back)

        print(f"增量更新 {len(codes)} 只股票...")
        return self.fill_all(codes=codes, days_back=days_back)

    def resume(self) -> FillResult:
        """
        断点续跑：继续上次失败的任务

        Returns:
            FillResult: 填充结果统计
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT code FROM kline_fill_status
            WHERE status = 'failed' AND retry_count < 3
        """)

        codes = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not codes:
            print("没有需要重试的股票")
            return FillResult()

        print(f"开始断点续跑，共 {len(codes)} 只股票")

        for code in codes:
            self._update_status(code, 'pending', increment_retry=True)

        return self.fill_all(codes=codes)

    def get_stats(self) -> Dict:
        """获取填充统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 总股票数
        cursor.execute("SELECT COUNT(DISTINCT code) FROM stocks")
        total_stocks = cursor.fetchone()[0]

        # 已完成的股票
        cursor.execute("""
            SELECT COUNT(*) FROM kline_fill_status
            WHERE status = 'completed'
        """)
        completed = cursor.fetchone()[0]

        # 失败的股票
        cursor.execute("""
            SELECT COUNT(*) FROM kline_fill_status
            WHERE status = 'failed'
        """)
        failed = cursor.fetchone()[0]

        conn.close()

        # DuckDB统计
        duckdb_stats = self.duckdb.get_stats()

        return {
            'total_stocks': total_stocks,
            'completed': completed,
            'failed': failed,
            'pending': total_stocks - completed - failed,
            'duckdb_rows': duckdb_stats.get('total_rows', 0),
            'duckdb_codes': duckdb_stats.get('total_codes', 0),
            'coverage': f"{completed}/{total_stocks}" if total_stocks > 0 else "0/0"
        }


# ==================== MinuteKlineFiller ====================

class MinuteKlineFiller:
    """
    分钟K线填充器

    职责：
    1. 从 akshare/东方财富 获取1分钟K线数据
    2. 存储到 DuckDB minute_kline 表
    3. 支持断点续跑

    表结构 (DuckDB minute_kline):
    - code: 股票代码
    - trade_date: 交易日期
    - trade_time: 交易时间戳
    - open/high/low/close: 价格
    - volume: 成交量
    - amount: 成交额
    - interval_type: '1min'

    状态表 (SQLite minute_kline_fill_status):
    - code: 股票代码
    - last_date: 最后填充日期
    - status: pending/running/completed/failed
    - retry_count: 重试次数
    """

    def __init__(self, db_path: str = None, rate_limit_sleep: float = 0.3):
        """
        初始化分钟K线填充器

        Args:
            db_path: SQLite数据库路径（存储状态）
            rate_limit_sleep: 限流睡眠时间（秒）
        """
        self.db_path = db_path or str(DB_PATH)
        self.rate_limit_sleep = rate_limit_sleep
        self._ensure_tables()

        self.duckdb = _get_duckdb_store()

    def _ensure_tables(self):
        """确保状态表存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 启用 WAL 模式
        cursor.execute("PRAGMA journal_mode=WAL")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS minute_kline_fill_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                last_date TEXT,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _get_stock_codes(self) -> List[str]:
        """获取可交易股票代码（排除ST/*ST/退市股）"""
        return _get_active_stock_codes(self.db_path)

    def _get_status(self, code: str) -> Optional[FillStatus]:
        """获取填充状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code, last_date, status, retry_count, error_message
            FROM minute_kline_fill_status WHERE code = ?
        """, (code,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return FillStatus(
                code=row[0],
                last_date=row[1],
                status=row[2],
                retry_count=row[3],
                error_message=row[4]
            )
        return None

    def _update_status(self, code: str, status: str, last_date: str = None,
                       error_message: str = None, increment_retry: bool = False):
        """更新填充状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        current_retry = 0
        if increment_retry:
            cursor.execute("SELECT retry_count FROM minute_kline_fill_status WHERE code = ?", (code,))
            row = cursor.fetchone()
            if row:
                current_retry = row[0] + 1

        cursor.execute("""
            INSERT OR REPLACE INTO minute_kline_fill_status
            (code, last_date, status, retry_count, error_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (code, last_date, status, current_retry, error_message,
              datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def _fetch_from_akshare(self, code: str, date_str: str) -> List[Dict]:
        """
        从AkShare获取单只股票单日的1分钟K线

        优先使用东方财富(EM)接口，失败后使用新浪(Sina)接口作为备用

        Args:
            code: 股票代码
            date_str: 日期 (YYYYMMDD)

        Returns:
            分钟K线数据列表
        """
        try:
            import akshare as ak
        except ImportError:
            print("AkShare未安装")
            return []

        # 先尝试新浪接口（国内连接更稳定）
        records = self._fetch_from_sina(code, date_str)
        if records:
            return records

        # 备用：尝试东方财富接口
        records = self._fetch_from_eastmoney(code, date_str)
        return records

    def _fetch_from_eastmoney(self, code: str, date_str: str) -> List[Dict]:
        """从东方财富获取分钟K线"""
        try:
            import akshare as ak

            start_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            end_date = start_date

            df = ak.stock_zh_a_hist_min_em(
                symbol=code,
                period='1',
                start_date=start_date,
                end_date=end_date,
                adjust='qfq'
            )

            if df is None or len(df) == 0:
                return []

            records = []
            for _, row in df.iterrows():
                records.append({
                    'code': code,
                    'trade_time': row['时间'],
                    'open': float(row['开盘']),
                    'high': float(row['最高']),
                    'low': float(row['最低']),
                    'close': float(row['收盘']),
                    'volume': int(row['成交量']),
                    'amount': float(row['成交额']),
                    'interval_type': '1min',
                })

            return records

        except Exception as e:
            # 不打印，直接返回空列表让备用源尝试
            return []

    def _fetch_from_sina(self, code: str, date_str: str) -> List[Dict]:
        """从新浪获取分钟K线（备用源）"""
        try:
            import akshare as ak

            # 转换代码格式: 600519 -> sh600519, 000001 -> sz000001
            if code.startswith('6'):
                symbol = f'sh{code}'
            else:
                symbol = f'sz{code}'

            df = ak.stock_zh_a_minute(symbol=symbol, period='1', adjust='qfq')

            if df is None or len(df) == 0:
                return []

            # 过滤指定日期的数据
            target_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            df = df[df['day'].astype(str).str.startswith(target_date)]

            if len(df) == 0:
                return []

            records = []
            for _, row in df.iterrows():
                # 跳过NaN行（当日最后可能有无数据的时间点）
                if pd.isna(row['close']):
                    continue
                records.append({
                    'code': code,
                    'trade_time': row['day'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': int(row['volume']),
                    'amount': float(row['amount']),
                    'interval_type': '1min',
                })

            return records

        except Exception as e:
            print(f"Sina获取 {code} {date_str} 分钟K线失败: {e}")
            return []

    def _save_minute_klines(self, klines: List[Dict]) -> int:
        """保存分钟K线到DuckDB"""
        if not klines:
            return 0

        success = 0
        try:
            with self.duckdb._get_conn() as conn:
                for k in klines:
                    try:
                        conn.execute("""
                            INSERT OR REPLACE INTO minute_kline
                            (code, trade_date, trade_time, open, high, low, close, volume, amount, interval_type)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            k['code'],
                            k['trade_time'].strftime('%Y-%m-%d') if hasattr(k['trade_time'], 'strftime') else str(k['trade_time'])[:10],
                            k['trade_time'],
                            k['open'],
                            k['high'],
                            k['low'],
                            k['close'],
                            k['volume'],
                            k['amount'],
                            k.get('interval_type', '1min'),
                        ))
                        success += 1
                    except Exception as e:
                        pass
        except Exception as e:
            print(f"保存分钟K线失败: {e}")

        return success

    def _has_recent_data(self, code: str, days_back: int = 2) -> bool:
        """检查最近N个交易日是否已有数据（DuckDB中有记录）"""
        try:
            from datetime import date, timedelta
            today = date.today()

            # 检查最近1-2个交易日
            for i in range(days_back):
                check_date = today - timedelta(days=i)
                date_str = check_date.strftime('%Y-%m-%d')

                with self.duckdb._get_conn() as conn:
                    cursor = conn.cursor()
                    # 使用 DuckDB 的 DATE() 函数转换 TIMESTAMP 进行比较
                    cursor.execute("""
                        SELECT COUNT(*) FROM minute_kline
                        WHERE code = ? AND DATE(trade_time) = ?
                    """, (code, date_str))
                    count = cursor.fetchone()[0]
                    if count > 0:
                        return True
            return False
        except Exception:
            return False

    def fill_stock(self, code: str, days_back: int = 14, force: bool = False) -> Tuple[int, str]:
        """
        填充单只股票的分钟K线

        策略：
        - 每次都尝试获取最近1-2天数据（忽略completed状态）
        - 旧数据（>2天）按completed状态跳过
        - 定时任务负责控制填充时机

        Args:
            code: 股票代码
            days_back: 填充最近多少天的数据
            force: 是否强制重新填充（包括旧数据）

        Returns:
            (插入记录数, 状态)
        """
        # 检查状态 - 仅用于跳过旧数据
        if not force:
            status = self._get_status(code)
            if status and status.status == 'completed':
                # 检查最近2天是否已有数据
                if self._has_recent_data(code, days_back=2):
                    return 0, 'skipped'

        self._update_status(code, 'running')

        # 获取最近交易日
        from datetime import datetime, timedelta
        today = date.today()
        total_count = 0

        for i in range(days_back):
            check_date = today - timedelta(days=i)
            date_str = check_date.strftime('%Y%m%d')

            klines = self._fetch_from_akshare(code, date_str)
            if klines:
                count = self._save_minute_klines(klines)
                total_count += count

            # 限流
            time.sleep(self.rate_limit_sleep)

        if total_count > 0:
            last_date = today.strftime('%Y%m%d')
            self._update_status(code, 'completed', last_date=last_date)
            return total_count, 'success'
        else:
            self._update_status(code, 'failed', error_message='No data from AkShare')
            return 0, 'failed'

    def fill_all(self, codes: List[str] = None, limit: int = None,
                days_back: int = 14, rate_limit: float = None) -> FillResult:
        """
        填充所有（或指定）股票的分钟K线

        Args:
            codes: 股票代码列表，None表示所有股票
            limit: 限制处理数量
            days_back: 填充最近多少天的数据
            rate_limit: 限流睡眠时间（秒）

        Returns:
            FillResult: 填充结果统计
        """
        result = FillResult()

        if codes is None:
            codes = self._get_stock_codes()

        if limit:
            codes = codes[:limit]

        sleep_time = rate_limit or self.rate_limit_sleep
        total = len(codes)

        print(f"开始填充分钟K线，共 {total} 只股票，填充最近 {days_back} 天数据")

        for i, code in enumerate(codes):
            try:
                count, status = self.fill_stock(code, days_back=days_back)

                result.total_records += count
                if status == 'success':
                    result.success += 1
                elif status == 'skipped':
                    pass
                else:
                    result.failed += 1
                    result.errors.append(f"{code}: {status}")

                # 限流控制
                if i < total - 1:
                    time.sleep(sleep_time)

                # 进度显示
                if (i + 1) % 50 == 0:
                    print(f"进度: {i+1}/{total}, 成功: {result.success}, 失败: {result.failed}, 记录: {result.total_records}")

                # 内存优化：每100只强制GC
                if (i + 1) % 100 == 0:
                    gc.collect()

            except Exception as e:
                result.failed += 1
                result.errors.append(f"{code}: {str(e)}")
                self._update_status(code, 'failed', error_message=str(e))

        gc.collect()
        print(f"填充完成: 成功 {result.success}, 失败 {result.failed}, 总记录 {result.total_records}")
        return result

    def fill_incremental(self, days_back: int = 1) -> FillResult:
        """
        增量更新：只获取最近1天的新数据

        Args:
            days_back: 检查最近多少天

        Returns:
            FillResult: 填充结果统计
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT code FROM minute_kline_fill_status
            WHERE status = 'completed'
        """)

        codes = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not codes:
            print("没有已完成的股票，执行全量填充")
            return self.fill_all(limit=100, days_back=days_back)

        print(f"增量更新 {len(codes)} 只股票...")
        return self.fill_all(codes=codes, days_back=days_back)

    def resume(self) -> FillResult:
        """
        断点续跑：继续上次失败的任务

        Returns:
            FillResult: 填充结果统计
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT code FROM minute_kline_fill_status
            WHERE status = 'failed' AND retry_count < 3
        """)

        codes = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not codes:
            print("没有需要重试的股票")
            return FillResult()

        print(f"开始断点续跑，共 {len(codes)} 只股票")

        for code in codes:
            self._update_status(code, 'pending', increment_retry=True)

        return self.fill_all(codes=codes)

    def get_stats(self) -> Dict:
        """获取填充统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 总股票数
        cursor.execute("SELECT COUNT(DISTINCT code) FROM stocks")
        total_stocks = cursor.fetchone()[0]

        # 已完成的股票
        cursor.execute("""
            SELECT COUNT(*) FROM minute_kline_fill_status
            WHERE status = 'completed'
        """)
        completed = cursor.fetchone()[0]

        # 失败的股票
        cursor.execute("""
            SELECT COUNT(*) FROM minute_kline_fill_status
            WHERE status = 'failed'
        """)
        failed = cursor.fetchone()[0]

        conn.close()

        # DuckDB分钟K线统计
        try:
            info = self.duckdb.get_retention_info()
            minute_info = info.get('minute_kline', {})
        except Exception:
            minute_info = {}

        return {
            'total_stocks': total_stocks,
            'completed': completed,
            'failed': failed,
            'pending': total_stocks - completed - failed,
            'duckdb_rows': minute_info.get('total_rows', 0),
            'duckdb_codes': 0,  # 需要单独查询
            'coverage': f"{completed}/{total_stocks}" if total_stocks > 0 else "0/0"
        }


# ==================== CPHistoryBatchCalculator ====================

class CPHistoryBatchCalculator:
    """
    战力历史批量计算器

    职责：
    1. 批量计算全市场股票的战力历史
    2. 利用 DuckDB K线数据 + SQLite 财务数据
    3. 保存到 cp_history 表

    v19.14: 集成 CPEngine 进行真实战力计算
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)

        self.duckdb = _get_duckdb_store()
        self.cp_store = _get_cp_history_store()

        # CPEngine 延迟导入避免循环依赖
        self._cp_engine = None

    def _get_cp_engine(self):
        """获取 CPEngine 实例（延迟加载）"""
        if self._cp_engine is None:
            try:
                from backend.engine.cp_engine import CPEngine
                self._cp_engine = CPEngine()
            except ImportError:
                print("Warning: CPEngine not available, using simplified calculation")
                self._cp_engine = None
        return self._cp_engine

    def _get_codes_with_klines(self) -> List[str]:
        """获取有K线数据的股票代码"""
        try:
            with self.duckdb._get_conn() as conn:
                result = conn.execute("SELECT DISTINCT code FROM daily_kline").fetchall()
                return [row[0] for row in result]
        except Exception as e:
            print(f"获取K线股票列表失败: {e}")
            return []

    def _get_stock_financials(self, codes: List[str]) -> Dict[str, Dict]:
        """从SQLite获取股票财务数据"""
        if not codes:
            return {}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        placeholders = ','.join(['?' for _ in codes])
        cursor.execute(f"""
            SELECT code, name, price, pe, roe, net_profit_growth, revenue_growth,
                   pb, gross_margin, cashflow, debt_ratio, sector
            FROM stocks WHERE code IN ({placeholders})
        """, codes)

        result = {}
        for row in cursor.fetchall():
            result[row[0]] = {
                'code': row[0],
                'name': row[1],
                'price': row[2] or 0,
                'pe': row[3] or 0,
                'roe': row[4] or 0,
                'net_profit_growth': row[5] or 0,
                'revenue_growth': row[6] or 0,
                'pb': row[7] or 0,
                'gross_margin': row[8] or 0,
                'cashflow': row[9] or 0,
                'debt_ratio': row[10] or 0,
                'sector': row[11] or '',
            }
        conn.close()
        return result

    def _get_latest_klines(self, code: str, days: int = 30) -> List[Dict]:
        """获取某股票最近的K线数据"""
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        result = self.duckdb.get_klines(code, start_date=start_date, end_date=end_date, limit=500)
        if result.success and result.data is not None:
            return result.data.to_dict('records')
        return []

    def _create_stock_cp(self, stock_data: Dict, klines: List[Dict]):
        """
        使用 CPEngine 创建 StockCP 对象

        Args:
            stock_data: 股票财务数据
            klines: K线数据

        Returns:
            StockCP 对象或 None
        """
        try:
            from backend.engine.cp_engine import create_stock_from_raw

            # 从K线计算动量分
            momentum_score = 0
            if len(klines) >= 5:
                recent_avg = sum(k['close'] for k in klines[:5]) / min(5, len(klines))
                older_avg = sum(k['close'] for k in klines[-5:]) / min(5, len(klines))
                if older_avg > 0:
                    momentum_score = ((recent_avg - older_avg) / older_avg) * 100

            # 计算涨跌幅
            change_pct = 0
            if len(klines) >= 1:
                latest_close = klines[0].get('close', 0)
                prev_close = klines[-1].get('close', 0)
                if prev_close > 0:
                    change_pct = ((latest_close - prev_close) / prev_close) * 100

            # 使用 create_stock_from_raw 创建 StockCP
            stock = create_stock_from_raw(
                code=stock_data['code'],
                name=stock_data['name'],
                price=stock_data.get('price', 0),
                pe=stock_data.get('pe', 0),
                roe=stock_data.get('roe', 0),
                net_profit_growth=stock_data.get('net_profit_growth', 0),
                revenue_growth=stock_data.get('revenue_growth', 0),
                change_pct=change_pct,
                pb=stock_data.get('pb', 0),
                gross_margin=stock_data.get('gross_margin', 0),
                cashflow=stock_data.get('cashflow', 0),
                debt_ratio=stock_data.get('debt_ratio', 0),
                sector=stock_data.get('sector', ''),
                data_quality='medium',
            )

            # 设置计算得到的动量分
            stock.momentum_score = momentum_score

            return stock
        except Exception as e:
            print(f"创建 StockCP 失败 {stock_data.get('code')}: {e}")
            return None

    def _calculate_simple_cp(self, stock_data: Dict, klines: List[Dict]) -> Dict:
        """
        简化版战力计算（当 CPEngine 不可用时回退）

        注意：仅用于兼容模式，建议使用 CPEngine 进行真实计算
        """
        # 基于K线计算动量分
        momentum_score = 0
        if len(klines) >= 5:
            recent_avg = sum(k['close'] for k in klines[:5]) / min(5, len(klines))
            older_avg = sum(k['close'] for k in klines[-5:]) / min(5, len(klines))
            if older_avg > 0:
                momentum_score = ((recent_avg - older_avg) / older_avg) * 100

        # 成长分（使用财务数据）
        growth_score = min(100, max(0, stock_data.get('net_profit_growth', 0) * 2))

        # 价值分（使用PE/PB）
        pe = stock_data.get('pe', 0)
        if pe > 0 and pe < 30:
            value_score = (30 - pe) / 30 * 100
        else:
            value_score = 0

        # 质量分（使用ROE）
        roe = stock_data.get('roe', 0)
        quality_score = min(100, max(0, roe * 5))

        # 简化总分
        total_cp = (growth_score * 0.3 + value_score * 0.2 +
                   momentum_score * 0.3 + quality_score * 0.2)

        return {
            'code': stock_data['code'],
            'name': stock_data['name'],
            'total_cp': total_cp,
            'growth_score': growth_score,
            'value_score': value_score,
            'quality_score': quality_score,
            'momentum_score': momentum_score,
            'risk_score': 0,
            'rank': 0,
        }

    def calculate_all(self, days_back: int = 30, use_real_cp: bool = True) -> FillResult:
        """
        批量计算所有股票的战力

        Args:
            days_back: 使用最近多少天的K线数据
            use_real_cp: 是否使用真实 CPEngine 计算（默认 True）

        Returns:
            FillResult: 计算结果统计
        """
        result = FillResult()

        # 获取有K线数据的股票
        codes = self._get_codes_with_klines()
        if not codes:
            print("没有找到有K线数据的股票")
            return result

        print(f"开始计算 {len(codes)} 只股票的战力...")

        # 批量获取财务数据
        financials = self._get_stock_financials(codes)

        if use_real_cp:
            # 使用真实 CPEngine 计算
            stocks_to_save = self._calculate_with_cp_engine(codes, financials, days_back, result)
        else:
            # 使用简化计算（兼容模式）
            stocks_to_save = self._calculate_simple_all(codes, financials, days_back, result)

        # 批量保存
        if stocks_to_save:
            try:
                self.cp_store.record_cp_history(stocks_to_save)
                result.total_records = len(stocks_to_save)
            except Exception as e:
                print(f"保存战力历史失败: {e}")

        print(f"计算完成: 成功 {result.success}, 失败 {result.failed}")
        return result

    def _calculate_with_cp_engine(self, codes: List[str], financials: Dict[str, Dict],
                                   days_back: int, result: FillResult) -> List[Dict]:
        """
        使用 CPEngine 进行真实战力计算

        CPEngine 需要对所有股票一起计算才能保证归一化的正确性
        """
        cp_engine = self._get_cp_engine()
        if cp_engine is None:
            print("CPEngine 不可用，回退到简化计算")
            return self._calculate_simple_all(codes, financials, days_back, result)

        stocks_to_save = []

        # 第一步：创建所有 StockCP 对象
        stock_objects = []
        for code in codes:
            try:
                klines = self._get_latest_klines(code, days=days_back)
                stock_data = financials.get(code, {'code': code, 'name': '', 'pe': 0, 'roe': 0, 'net_profit_growth': 0})

                stock = self._create_stock_cp(stock_data, klines)
                if stock:
                    stock_objects.append(stock)
                    cp_engine.add_stock(stock)
                    result.success += 1
                else:
                    result.failed += 1
            except Exception as e:
                result.failed += 1
                result.errors.append(f"{code}: {str(e)}")

        # 第二步：使用 CPEngine.calculate_all() 进行归一化计算
        if stock_objects:
            try:
                # CPEngine.calculate_all() 会对所有股票进行归一化
                calculated_stocks = cp_engine.calculate_all(use_multi_day_momentum=True)

                # 提取结果
                for stock in calculated_stocks:
                    stocks_to_save.append({
                        'code': stock.code,
                        'name': stock.name,
                        'total_cp': stock.total_cp,
                        'growth_score': stock.growth_score,
                        'value_score': stock.value_score,
                        'quality_score': stock.quality_score,
                        'momentum_score': stock.momentum_score,
                        'risk_score': stock.risk_score,
                        'rank': 0,
                    })

                print(f"CPEngine 计算完成，{len(calculated_stocks)} 只股票")

            except Exception as e:
                print(f"CPEngine 计算失败: {e}，回退到简化计算")
                # 回退：使用已计算的原始分数
                for stock in stock_objects:
                    stocks_to_save.append({
                        'code': stock.code,
                        'name': stock.name,
                        'total_cp': stock.total_cp,
                        'growth_score': stock.growth_score,
                        'value_score': stock.value_score,
                        'quality_score': stock.quality_score,
                        'momentum_score': stock.momentum_score,
                        'risk_score': stock.risk_score,
                        'rank': 0,
                    })

        return stocks_to_save

    def _calculate_simple_all(self, codes: List[str], financials: Dict[str, Dict],
                              days_back: int, result: FillResult) -> List[Dict]:
        """简化版批量计算（兼容模式）"""
        stocks_to_save = []

        for code in codes:
            try:
                klines = self._get_latest_klines(code, days=days_back)
                stock_data = financials.get(code, {'code': code, 'name': '', 'pe': 0, 'roe': 0, 'net_profit_growth': 0})

                cp_data = self._calculate_simple_cp(stock_data, klines)
                stocks_to_save.append(cp_data)
                result.success += 1

            except Exception as e:
                result.failed += 1
                result.errors.append(f"{code}: {str(e)}")

        return stocks_to_save

    def get_stats(self) -> Dict:
        """获取计算统计"""
        try:
            all_codes = self.cp_store.get_all_codes()
            cp_count = len(all_codes)
        except Exception:
            cp_count = 0

        duckdb_codes = len(self._get_codes_with_klines())

        return {
            'cp_history_count': cp_count,
            'codes_count': cp_count,
            'duckdb_codes': duckdb_codes,
        }


# ==================== FinancialHistoryFiller ====================

class FinancialHistoryFiller:
    """
    历史财务数据填充器

    职责：
    1. 从 Tushare 获取历史财务数据（利润表、资产负债表、现金流量表）
    2. 存储到 SQLite financial_history 表
    3. 支持断点续跑

    注意：当前 stocks 表只存储最新快照，财务历史需要单独表存储
    """

    def __init__(self, db_path: str = None, rate_limit_sleep: float = 0.5):
        self.db_path = db_path or str(DB_PATH)
        self.rate_limit_sleep = rate_limit_sleep
        self._ensure_tables()

    def _ensure_tables(self):
        """确保财务历史表存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 启用 WAL 模式
        cursor.execute("PRAGMA journal_mode=WAL")

        # 财务历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                end_date TEXT NOT NULL,           -- 报告期
                ann_date TEXT,                     -- 公告日期
                report_type INTEGER,               -- 报告类型 1-一季度 2-半年度 3-三季度 4-年度
                total_revenue REAL,                -- 营业总收入
                revenue REAL,                      -- 营业收入
                oper_profit REAL,                   -- 营业利润
                n_income REAL,                     -- 净利润
                total_profit REAL,                 -- 利润总额
                adj_income REAL,                   -- 扣非净利润
                total_assets REAL,                 -- 总资产
                total_liab REAL,                   -- 总负债
                equity REAL,                       -- 股东权益
                roe REAL,                          -- 净资产收益率
                pe_ratio REAL,                     -- 市盈率
                pb_ratio REAL,                     -- 市净率
                gross_margin REAL,                 -- 毛利率
                net_margin REAL,                   -- 净利率
                debt_ratio REAL,                   -- 资产负债率
                created_at TEXT,
                UNIQUE(code, end_date)
            )
        """)

        # 状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS financial_fill_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                last_date TEXT,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _get_stock_codes(self) -> List[str]:
        """获取可交易股票代码（排除ST/*ST/退市股）"""
        return _get_active_stock_codes(self.db_path)

    def _convert_to_ts_code(self, code: str) -> str:
        """转换代码为Tushare格式"""
        code = code.strip()
        # 去掉 sh/sz 前缀（如 sh600088 -> 600088）
        if code.startswith('sh') or code.startswith('sz'):
            code = code[2:]
        code = code.zfill(6)
        suffix = '.SH' if code.startswith('6') else '.SZ'
        return f"{code}{suffix}"

    def _get_status(self, code: str) -> Optional[FillStatus]:
        """获取填充状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT code, last_date, status, retry_count, error_message
            FROM financial_fill_status WHERE code = ?
        """, (code,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return FillStatus(
                code=row[0],
                last_date=row[1],
                status=row[2],
                retry_count=row[3],
                error_message=row[4]
            )
        return None

    def _update_status(self, code: str, status: str, last_date: str = None,
                      error_message: str = None, increment_retry: bool = False):
        """更新填充状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        current_retry = 0
        if increment_retry:
            cursor.execute("SELECT retry_count FROM financial_fill_status WHERE code = ?", (code,))
            row = cursor.fetchone()
            if row:
                current_retry = row[0] + 1

        cursor.execute("""
            INSERT OR REPLACE INTO financial_fill_status
            (code, last_date, status, retry_count, error_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (code, last_date, status, current_retry, error_message,
              datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def _fetch_financial_data(self, ts_code: str, start_year: int = 2020) -> List[Dict]:
        """
        从Tushare获取单只股票的财务数据

        Args:
            ts_code: Tushare格式的股票代码
            start_year: 开始年份

        Returns:
            财务数据列表
        """
        try:
            import tushare as ts
        except ImportError:
            print("Tushare未安装")
            return []

        try:
            pro = ts.pro_api()
            end_date = date.today().strftime('%Y%m%d')
            start_date = f"{start_year}0101"

            all_data = []

            # 获取利润表
            try:
                df_income = pro.income(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    limit=5000
                )
                if df_income is not None and len(df_income) > 0:
                    all_data.append(('income', df_income))
            except Exception as e:
                print(f"获取利润表失败: {e}")

            # 获取资产负债表
            try:
                df_balance = pro.balancesheet(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    limit=5000
                )
                if df_balance is not None and len(df_balance) > 0:
                    all_data.append(('balance', df_balance))
            except Exception as e:
                print(f"获取资产负债表失败: {e}")

            # 获取现金流量表
            try:
                df_cashflow = pro.cashflow(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    limit=5000
                )
                if df_cashflow is not None and len(df_cashflow) > 0:
                    all_data.append(('cashflow', df_cashflow))
            except Exception as e:
                print(f"获取现金流量表失败: {e}")

            # 合并数据（按end_date关联）
            return self._merge_financial_data(all_data)

        except Exception as e:
            print(f"获取 {ts_code} 财务数据失败: {e}")
            return []

    def _merge_financial_data(self, data_list: List[Tuple[str, Any]]) -> List[Dict]:
        """合并多张财务表数据"""
        if not data_list:
            return []

        # 使用第一张表作为基础
        base_type, base_df = data_list[0]
        result = []

        for _, row in base_df.iterrows():
            record = {
                'code': self._convert_from_ts_code(row.get('ts_code', '')),
                'end_date': row.get('end_date', ''),
                'ann_date': row.get('ann_date', ''),
                'report_type': row.get('report_type', 0),
                'total_revenue': row.get('total_revenue', 0),
                'revenue': row.get('revenue', 0),
                'n_income': row.get('n_income', 0),
                'total_profit': row.get('total_profit', 0),
            }

            # 从资产负债表中补充字段
            if len(data_list) > 1:
                bal_type, bal_df = data_list[1]
                for _, bal_row in bal_df.iterrows():
                    if bal_row.get('end_date') == row.get('end_date'):
                        record['total_assets'] = bal_row.get('total_assets', 0)
                        record['total_liab'] = bal_row.get('total_liab', 0)
                        record['equity'] = bal_row.get('equity', 0)
                        record['debt_ratio'] = bal_row.get('debt_ratio', 0)
                        break

            result.append(record)

        return result

    def _convert_from_ts_code(self, ts_code: str) -> str:
        """从Tushare格式转换回标准代码"""
        return ts_code.replace('.SH', '').replace('.SZ', '')

    def _save_financial_data(self, data_list: List[Dict]) -> int:
        """保存财务数据到数据库"""
        if not data_list:
            return 0

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        data = [
            (
                d['code'],
                d['end_date'],
                d.get('ann_date', ''),
                d.get('report_type', 0),
                d.get('total_revenue', 0),
                d.get('revenue', 0),
                d.get('oper_profit', 0),
                d.get('n_income', 0),
                d.get('total_profit', 0),
                d.get('adj_income', 0),
                d.get('total_assets', 0),
                d.get('total_liab', 0),
                d.get('equity', 0),
                d.get('roe', 0),
                d.get('pe_ratio', 0),
                d.get('pb_ratio', 0),
                d.get('gross_margin', 0),
                d.get('net_margin', 0),
                d.get('debt_ratio', 0),
                datetime.now().isoformat(),
            )
            for d in data_list
        ]

        cursor.executemany("""
            INSERT OR REPLACE INTO financial_history
            (code, end_date, ann_date, report_type, total_revenue, revenue,
             oper_profit, n_income, total_profit, adj_income, total_assets,
             total_liab, equity, roe, pe_ratio, pb_ratio, gross_margin,
             net_margin, debt_ratio, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)

        conn.commit()
        conn.close()

        return len(data)

    def fill_stock(self, code: str, start_year: int = 2020, force: bool = False) -> Tuple[int, str]:
        """
        填充单只股票的历史财务数据

        Args:
            code: 股票代码
            start_year: 开始年份
            force: 是否强制重新填充

        Returns:
            (插入记录数, 状态)
        """
        if not force:
            status = self._get_status(code)
            if status and status.status == 'completed':
                return 0, 'skipped'

        self._update_status(code, 'running')

        ts_code = self._convert_to_ts_code(code)
        data_list = self._fetch_financial_data(ts_code, start_year=start_year)

        if not data_list:
            self._update_status(code, 'failed', error_message='No data from Tushare')
            return 0, 'failed'

        count = self._save_financial_data(data_list)
        if count > 0:
            last_date = max(d.get('end_date', '') for d in data_list)
            self._update_status(code, 'completed', last_date=last_date)
            return count, 'success'
        else:
            self._update_status(code, 'failed', error_message='Save failed')
            return 0, 'failed'

    def fill_all(self, codes: List[str] = None, limit: int = None,
                 start_year: int = 2020, rate_limit: float = None) -> FillResult:
        """
        批量填充财务数据

        Args:
            codes: 股票代码列表
            limit: 限制数量
            start_year: 开始年份
            rate_limit: 限流时间

        Returns:
            FillResult
        """
        result = FillResult()

        if codes is None:
            codes = self._get_stock_codes()

        if limit:
            codes = codes[:limit]

        sleep_time = rate_limit or self.rate_limit_sleep
        total = len(codes)

        print(f"开始填充财务历史，共 {total} 只股票，从 {start_year} 年开始")

        for i, code in enumerate(codes):
            try:
                count, status = self.fill_stock(code, start_year=start_year)

                result.total_records += count
                if status == 'success':
                    result.success += 1
                elif status == 'skipped':
                    pass
                else:
                    result.failed += 1
                    result.errors.append(f"{code}: {status}")

                if i < total - 1:
                    time.sleep(sleep_time)

                if (i + 1) % 50 == 0:
                    print(f"进度: {i+1}/{total}, 成功: {result.success}, 失败: {result.failed}")
                    gc.collect()  # 内存优化

            except Exception as e:
                result.failed += 1
                result.errors.append(f"{code}: {str(e)}")

        gc.collect()
        print(f"填充完成: 成功 {result.success}, 失败 {result.failed}, 总记录 {result.total_records}")
        return result

    def get_stats(self) -> Dict:
        """获取填充统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(DISTINCT code) FROM stocks")
        total_stocks = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM financial_history")
        total_records = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT code) FROM financial_history")
        codes_with_data = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM financial_fill_status WHERE status = 'completed'
        """)
        completed = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM financial_fill_status WHERE status = 'failed'
        """)
        failed = cursor.fetchone()[0]

        conn.close()

        return {
            'total_stocks': total_stocks,
            'completed': completed,
            'failed': failed,
            'pending': total_stocks - completed - failed,
            'total_records': total_records,
            'codes_with_data': codes_with_data,
        }


# ==================== TradeCalendar ====================

class TradeCalendar:
    """
    交易日历管理器

    职责：
    1. 从 Tushare 获取并存储 A 股交易日历
    2. 提供交易日判断
    3. 供 GapDetector 使用，避免周末/节假日误判为缺口

    表结构 (DuckDB trade_cal):
    - cal_date: 日期 (YYYY-MM-DD)
    - is_open: 是否交易 (1=是, 0=否)
    - pretrade_date: 前一个交易日
    """

    def __init__(self):
        self.duckdb = _get_duckdb_store()
        self._ensure_table()

    def _ensure_table(self):
        """确保交易日历表存在"""
        try:
            with self.duckdb._get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS trade_cal (
                        cal_date DATE PRIMARY KEY,
                        is_open INTEGER NOT NULL,
                        pretrade_date DATE
                    )
                """)
        except Exception as e:
            print(f"创建交易日历表失败: {e}")

    def fetch_from_tushare(self, start_date: str = None, end_date: str = None) -> int:
        """
        从Tushare获取交易日历

        Args:
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)

        Returns:
            获取的记录数
        """
        try:
            import tushare as ts
        except ImportError:
            print("Tushare未安装")
            return 0

        if start_date is None:
            start_date = (date.today() - timedelta(days=365)).strftime('%Y%m%d')
        if end_date is None:
            end_date = (date.today() + timedelta(days=30)).strftime('%Y%m%d')

        try:
            pro = ts.pro_api()
            df = pro.trade_cal(start_date=start_date, end_date=end_date)

            if df is None or len(df) == 0:
                return 0

            count = 0
            with self.duckdb._get_conn() as conn:
                for _, row in df.iterrows():
                    try:
                        conn.execute("""
                            INSERT OR REPLACE INTO trade_cal (cal_date, is_open, pretrade_date)
                            VALUES (?, ?, ?)
                        """, (
                            row['cal_date'],
                            row['is_open'],
                            row['pretrade_date']
                        ))
                        count += 1
                    except Exception:
                        pass

            return count

        except Exception as e:
            print(f"获取交易日历失败: {e}")
            return 0

    def is_trading_day(self, check_date: str = None) -> bool:
        """
        判断是否为交易日

        Args:
            check_date: 日期 (YYYY-MM-DD 或 YYYYMMDD)，默认今天

        Returns:
            True=是交易日, False=非交易日
        """
        if check_date is None:
            check_date = date.today()
        elif isinstance(check_date, str):
            if len(check_date) == 8:
                check_date = f"{check_date[:4]}-{check_date[4:6]}-{check_date[6:8]}"

        try:
            with self.duckdb._get_conn() as conn:
                result = conn.execute(
                    "SELECT is_open FROM trade_cal WHERE cal_date = ?",
                    [check_date]
                ).fetchone()

                if result:
                    return result[0] == 1
        except Exception:
            pass

        # 如果数据库没有，返回True（假设）
        return True

    def get_next_trading_day(self, from_date: str = None) -> str:
        """获取下一个交易日"""
        if from_date is None:
            from_date = date.today()
        elif isinstance(from_date, str):
            if len(from_date) == 8:
                from_date = f"{from_date[:4]}-{from_date[4:6]}-{from_date[6:8]}"
                from_date = datetime.strptime(from_date, '%Y-%m-%d').date()

        try:
            with self.duckdb._get_conn() as conn:
                result = conn.execute("""
                    SELECT cal_date FROM trade_cal
                    WHERE cal_date > ? AND is_open = 1
                    ORDER BY cal_date ASC
                    LIMIT 1
                """, [from_date]).fetchone()

                if result:
                    return result[0]
        except Exception:
            pass

        return (from_date + timedelta(days=1)).strftime('%Y-%m-%d')

    def get_trading_days_between(self, start_date: str, end_date: str) -> List[str]:
        """获取两个日期之间的所有交易日"""
        if len(start_date) == 8:
            start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
        if len(end_date) == 8:
            end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

        try:
            with self.duckdb._get_conn() as conn:
                result = conn.execute("""
                    SELECT cal_date FROM trade_cal
                    WHERE cal_date BETWEEN ? AND ? AND is_open = 1
                    ORDER BY cal_date ASC
                """, [start_date, end_date]).fetchall()

                return [row[0] for row in result]
        except Exception:
            return []

    def get_stats(self) -> Dict:
        """获取统计"""
        try:
            with self.duckdb._get_conn() as conn:
                total = conn.execute("SELECT COUNT(*) FROM trade_cal").fetchone()[0]
                trading = conn.execute("SELECT COUNT(*) FROM trade_cal WHERE is_open = 1").fetchone()[0]
                latest = conn.execute("SELECT MAX(cal_date) FROM trade_cal").fetchone()[0]
        except Exception:
            total = trading = latest = 0

        return {
            'total_days': total,
            'trading_days': trading,
            'latest_date': str(latest) if latest else None,
        }


# ==================== 便捷函数 ====================

_ex_right_filler = None
_kline_filler = None
_minute_kline_filler = None
_cp_calculator = None
_financial_filler = None


def get_ex_right_factor_filler() -> ExRightFactorFiller:
    """获取除权因子填充器单例"""
    global _ex_right_filler
    if _ex_right_filler is None:
        _ex_right_filler = ExRightFactorFiller()
    return _ex_right_filler


def get_kline_filler() -> KlineFiller:
    """获取K线填充器单例"""
    global _kline_filler
    if _kline_filler is None:
        _kline_filler = KlineFiller()
    return _kline_filler


def get_minute_kline_filler() -> MinuteKlineFiller:
    """获取分钟K线填充器单例"""
    global _minute_kline_filler
    if _minute_kline_filler is None:
        _minute_kline_filler = MinuteKlineFiller()
    return _minute_kline_filler


def fill_ex_right_factors(codes: List[str] = None, limit: int = None) -> FillResult:
    """便捷函数：填充除权因子"""
    return get_ex_right_factor_filler().fill_all(codes=codes, limit=limit)


def fill_klines(codes: List[str] = None, limit: int = None, days_back: int = 730) -> FillResult:
    """便捷函数：填充K线数据"""
    return get_kline_filler().fill_all(codes=codes, limit=limit, days_back=days_back)


def fill_minute_klines(codes: List[str] = None, limit: int = None, days_back: int = 14) -> FillResult:
    """便捷函数：填充分钟K线数据"""
    return get_minute_kline_filler().fill_all(codes=codes, limit=limit, days_back=days_back)


def resume_ex_right_factors() -> FillResult:
    """便捷函数：除权因子断点续跑"""
    return get_ex_right_factor_filler().resume()


def resume_klines() -> FillResult:
    """便捷函数：K线断点续跑"""
    return get_kline_filler().resume()


def resume_minute_klines() -> FillResult:
    """便捷函数：分钟K线断点续跑"""
    return get_minute_kline_filler().resume()


def get_cp_history_calculator() -> CPHistoryBatchCalculator:
    """获取战力历史批量计算器单例"""
    global _cp_calculator
    if _cp_calculator is None:
        _cp_calculator = CPHistoryBatchCalculator()
    return _cp_calculator


def calculate_cp_history(days_back: int = 30) -> FillResult:
    """便捷函数：批量计算战力历史"""
    return get_cp_history_calculator().calculate_all(days_back=days_back)


def get_financial_history_filler() -> FinancialHistoryFiller:
    """获取财务历史填充器单例"""
    global _financial_filler
    if _financial_filler is None:
        _financial_filler = FinancialHistoryFiller()
    return _financial_filler


def fill_financial_history(codes: List[str] = None, limit: int = None, start_year: int = 2020) -> FillResult:
    """便捷函数：填充财务历史数据"""
    return get_financial_history_filler().fill_all(codes=codes, limit=limit, start_year=start_year)


def resume_financial_history() -> FillResult:
    """便捷函数：财务历史断点续跑"""
    return get_financial_history_filler().resume()


_trade_calendar = None


def get_trade_calendar() -> TradeCalendar:
    """获取交易日历单例"""
    global _trade_calendar
    if _trade_calendar is None:
        _trade_calendar = TradeCalendar()
    return _trade_calendar


def is_trading_day(check_date: str = None) -> bool:
    """便捷函数：判断是否为交易日"""
    return get_trade_calendar().is_trading_day(check_date)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("=" * 50)
        print("数据填充器 (Filler)")
        print("=" * 50)
        print("\n用法:")
        print("  python filler.py ex_right fill      # 填充除权因子")
        print("  python filler.py ex_right resume   # 除权因子断点续跑")
        print("  python filler.py kline fill        # 填充K线")
        print("  python filler.py kline resume      # K线断点续跑")
        print("  python filler.py kline incremental # K线增量更新")
        print("  python filler.py minute fill       # 填充分钟K线")
        print("  python filler.py minute resume    # 分钟K线断点续跑")
        print("  python filler.py financial fill   # 填充财务历史")
        print("  python filler.py cp calculate     # 计算战力历史")
        print("  python filler.py stats            # 查看状态")
        sys.exit(1)

    command = sys.argv[1]

    if command == "ex_right":
        filler = get_ex_right_factor_filler()
        stats = filler.get_stats()
        print(f"\n除权因子状态:")
        print(f"  总股票数: {stats['total_stocks']}")
        print(f"  已完成: {stats['completed']}")
        print(f"  失败: {stats['failed']}")
        print(f"  除权因子记录: {stats['total_factors']}")

        if len(sys.argv) > 2:
            sub_cmd = sys.argv[2]
            if sub_cmd == "fill":
                result = filler.fill_all()
                print(f"结果: 成功 {result.success}, 失败 {result.failed}, 记录 {result.total_records}")
            elif sub_cmd == "resume":
                result = filler.resume()
                print(f"结果: 成功 {result.success}, 失败 {result.failed}, 记录 {result.total_records}")

    elif command == "kline":
        filler = get_kline_filler()
        stats = filler.get_stats()
        print(f"\nK线填充状态:")
        print(f"  总股票数: {stats['total_stocks']}")
        print(f"  已完成: {stats['completed']}")
        print(f"  失败: {stats['failed']}")
        print(f"  DuckDB记录: {stats['duckdb_rows']}")
        print(f"  DuckDB股票: {stats['duckdb_codes']}")

        if len(sys.argv) > 2:
            sub_cmd = sys.argv[2]
            if sub_cmd == "fill":
                result = filler.fill_all(limit=100)
                print(f"结果: 成功 {result.success}, 失败 {result.failed}, 记录 {result.total_records}")
            elif sub_cmd == "resume":
                result = filler.resume()
                print(f"结果: 成功 {result.success}, 失败 {result.failed}, 记录 {result.total_records}")
            elif sub_cmd == "incremental":
                result = filler.fill_incremental()
                print(f"结果: 成功 {result.success}, 失败 {result.failed}, 记录 {result.total_records}")

    elif command == "minute":
        filler = get_minute_kline_filler()
        stats = filler.get_stats()
        print(f"\n分钟K线填充状态:")
        print(f"  总股票数: {stats['total_stocks']}")
        print(f"  已完成: {stats['completed']}")
        print(f"  失败: {stats['failed']}")
        print(f"  DuckDB记录: {stats['duckdb_rows']}")

        if len(sys.argv) > 2:
            sub_cmd = sys.argv[2]
            if sub_cmd == "fill":
                result = filler.fill_all(limit=100, days_back=3)
                print(f"结果: 成功 {result.success}, 失败 {result.failed}, 记录 {result.total_records}")
            elif sub_cmd == "resume":
                result = filler.resume()
                print(f"结果: 成功 {result.success}, 失败 {result.failed}, 记录 {result.total_records}")

    elif command == "cp":
        calculator = get_cp_history_calculator()
        stats = calculator.get_stats()
        print(f"\n战力历史计算状态:")
        print(f"  DuckDB有K线股票: {stats['duckdb_codes']}")
        print(f"  cp_history记录数: {stats['cp_history_count']}")

        if len(sys.argv) > 2:
            sub_cmd = sys.argv[2]
            if sub_cmd == "calculate":
                result = calculator.calculate_all()
                print(f"结果: 成功 {result.success}, 失败 {result.failed}, 记录 {result.total_records}")

    elif command == "financial":
        filler = get_financial_history_filler()
        stats = filler.get_stats()
        print(f"\n财务历史填充状态:")
        print(f"  总股票数: {stats['total_stocks']}")
        print(f"  已完成: {stats['completed']}")
        print(f"  失败: {stats['failed']}")
        print(f"  财务历史记录: {stats['total_records']}")

        if len(sys.argv) > 2:
            sub_cmd = sys.argv[2]
            if sub_cmd == "fill":
                result = filler.fill_all(limit=50)
                print(f"结果: 成功 {result.success}, 失败 {result.failed}, 记录 {result.total_records}")

    elif command == "stats":
        ex_right_filler = get_ex_right_factor_filler()
        kline_filler = get_kline_filler()
        minute_filler = get_minute_kline_filler()
        cp_calculator = get_cp_history_calculator()
        financial_filler = get_financial_history_filler()

        print("\n=== 除权因子 ===")
        stats = ex_right_filler.get_stats()
        print(f"  总股票数: {stats['total_stocks']}, 已完成: {stats['completed']}, 失败: {stats['failed']}")
        print(f"  除权因子记录: {stats['total_factors']}, 覆盖股票: {stats['factor_symbols']}")

        print("\n=== K线数据 ===")
        stats = kline_filler.get_stats()
        print(f"  总股票数: {stats['total_stocks']}, 已完成: {stats['completed']}, 失败: {stats['failed']}")
        print(f"  DuckDB记录: {stats['duckdb_rows']}, DuckDB股票: {stats['duckdb_codes']}")

        print("\n=== 分钟K线 ===")
        stats = minute_filler.get_stats()
        print(f"  总股票数: {stats['total_stocks']}, 已完成: {stats['completed']}, 失败: {stats['failed']}")
        print(f"  DuckDB记录: {stats['duckdb_rows']}")

        print("\n=== 交易日历 ===")
        trade_cal = get_trade_calendar()
        cal_stats = trade_cal.get_stats()
        print(f"  总天数: {cal_stats['total_days']}, 交易日: {cal_stats['trading_days']}")
        print(f"  最新日期: {cal_stats['latest_date']}")

    elif command == "trade_cal":
        trade_cal = get_trade_calendar()
        if len(sys.argv) > 2:
            sub_cmd = sys.argv[2]
            if sub_cmd == "fetch":
                count = trade_cal.fetch_from_tushare()
                print(f"获取了 {count} 条交易日历记录")
            elif sub_cmd == "check":
                check_date = sys.argv[3] if len(sys.argv) > 3 else None
                result = trade_cal.is_trading_day(check_date)
                date_str = check_date or "今天"
                print(f"{date_str} 是{'交易日' if result else '非交易日'}")
            elif sub_cmd == "next":
                next_day = trade_cal.get_next_trading_day()
                print(f"下一个交易日: {next_day}")
        else:
            stats = trade_cal.get_stats()
            print(f"\n交易日历状态:")
            print(f"  总天数: {stats['total_days']}, 交易日: {stats['trading_days']}")
            print(f"  最新日期: {stats['latest_date']}")
            print("\n用法:")
            print("  python filler.py trade_cal fetch    # 从Tushare获取日历")
            print("  python filler.py trade_cal check    # 检查今天是否为交易日")
            print("  python filler.py trade_cal check 20240101  # 检查指定日期")
            print("  python filler.py trade_cal next     # 获取下一个交易日")
