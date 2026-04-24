"""
股票池状态持久化模块

功能：
- 将 PoolManager 的池状态定期保存到 SQLite
- 服务重启时优先从持久化状态恢复池组成
- 确保池状态在服务重启后保持一致

设计：
- 存储位置：SQLite stocks 表同库 (tradesnake.db)
- 表结构：
  - pool_state (pool_tier TEXT PRIMARY KEY, codes TEXT, updated_at TEXT)
  - pool_metadata (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)
- 持久化内容：核心池+活跃池的股票代码列表（包含名称）
- 元数据：白名单/黑名单/观察期记录保存在 pool_metadata 表
"""

import sqlite3
import json
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认数据库路径
DATA_DIR = Path("/home/ailearn/projects/TradeSnake/data")
SQLITE_PATH = DATA_DIR / "tradesnake.db"

# codes 字段的 JSON 结构: [{"code": "000001", "name": "平安银行"}, ...]
StockInfoJSON = Dict[str, str]  # {"code": str, "name": str}


class PoolStateStore:
    """股票池状态持久化存储"""

    _instance: Optional['PoolStateStore'] = None
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

        self.db_path = str(db_path or SQLITE_PATH)
        self._write_lock = threading.Lock()
        self._ensure_db()
        self._initialized = True
        logger.info(f"PoolStateStore 初始化完成，数据库: {self.db_path}")

    def _ensure_db(self):
        """确保数据库和表存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pool_state (
                    pool_tier TEXT PRIMARY KEY,
                    codes TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pool_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save_pool_state(self, pool_tier: str, stocks: List[Dict[str, str]]) -> bool:
        """
        保存单个池的状态

        Args:
            pool_tier: 池层级 (CORE/ACTIVE/OBSERVE/TEMP)
            stocks: 股票信息列表 [{"code": "000001", "name": "平安银行"}, ...]

        Returns:
            是否保存成功
        """
        with self._write_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.execute("""
                        INSERT OR REPLACE INTO pool_state (pool_tier, codes, updated_at)
                        VALUES (?, ?, ?)
                    """, (pool_tier, json.dumps(stocks, ensure_ascii=False), datetime.now().isoformat()))
                    conn.commit()
                    logger.debug(f"保存池状态: {pool_tier}, {len(stocks)} 只股票")
                    return True
                finally:
                    conn.close()
            except Exception as e:
                logger.error(f"保存池状态失败: {pool_tier}, {e}")
                return False

    def save_all_pools(self, pools: Dict[str, List[Dict[str, str]]]) -> bool:
        """
        保存所有池的状态（过滤掉 _meta 元数据）

        Args:
            pools: {pool_tier: [{"code": "000001", "name": "平安银行"}, ...]} 字典

        Returns:
            是否保存成功
        """
        for pool_tier, stocks in pools.items():
            if pool_tier == '_meta':
                continue  # _meta 应保存到 pool_metadata 表，不是 pool_state 表
            if not self.save_pool_state(pool_tier, stocks):
                return False
        logger.info(f"保存所有池状态完成: {list(pools.keys())}")
        return True

    def load_pool_state(self, pool_tier: str) -> Optional[List[Dict[str, str]]]:
        """
        加载单个池的状态

        Args:
            pool_tier: 池层级

        Returns:
            股票信息列表 [{"code": "000001", "name": "平安银行"}, ...]，如果不存在则返回 None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT codes FROM pool_state WHERE pool_tier = ?",
                    (pool_tier,)
                )
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"加载池状态失败: {pool_tier}, {e}")
            return None

    def load_all_pools(self) -> Dict[str, List[Dict[str, str]]]:
        """
        加载所有池的状态

        Returns:
            {pool_tier: [{"code": "000001", "name": "平安银行"}, ...]} 字典
        """
        result = {}
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute("SELECT pool_tier, codes FROM pool_state")
                for row in cursor:
                    result[row[0]] = json.loads(row[1])
                logger.info(f"加载池状态完成: {list(result.keys())}")
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"加载池状态失败: {e}")
        return result

    def get_pool_state_age(self, pool_tier: str) -> Optional[datetime]:
        """
        获取池状态的更新时间

        Args:
            pool_tier: 池层级

        Returns:
            更新时间，如果不存在则返回 None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT updated_at FROM pool_state WHERE pool_tier = ?",
                    (pool_tier,)
                )
                row = cursor.fetchone()
                if row:
                    return datetime.fromisoformat(row[0])
                return None
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"获取池状态更新时间失败: {pool_tier}, {e}")
            return None

    def save_metadata(self, metadata: Dict) -> bool:
        """
        保存白名单、黑名单、观察期记录等元数据

        Args:
            metadata: {'whitelist': [], 'blacklist': [], 'probation_records': {code: date_str}}

        Returns:
            是否保存成功
        """
        with self._write_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                try:
                    # 转换日期为字符串
                    serializable = {
                        'whitelist': list(metadata.get('whitelist', [])),
                        'blacklist': list(metadata.get('blacklist', [])),
                        'probation_records': {
                            code: dt.isoformat() if isinstance(dt, (date, datetime))
                            else str(dt) for code, dt in metadata.get('probation_records', {}).items()
                        }
                    }
                    conn.execute("""
                        INSERT OR REPLACE INTO pool_metadata (key, value, updated_at)
                        VALUES (?, ?, ?)
                    """, ('_meta', json.dumps(serializable, ensure_ascii=False), datetime.now().isoformat()))
                    conn.commit()
                    logger.debug(f"保存池元数据完成")
                    return True
                finally:
                    conn.close()
            except Exception as e:
                logger.error(f"保存池元数据失败: {e}")
                return False

    def load_metadata(self) -> Optional[Dict]:
        """
        加载白名单、黑名单、观察期记录等元数据

        Returns:
            metadata dict or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT value FROM pool_metadata WHERE key = ?",
                    ('_meta',)
                )
                row = cursor.fetchone()
                if row:
                    data = json.loads(row[0])
                    # 反序列化日期
                    if 'probation_records' in data:
                        data['probation_records'] = {
                            code: datetime.fromisoformat(dt_str).date()
                            for code, dt_str in data['probation_records'].items()
                        }
                    return data
                return None
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"加载池元数据失败: {e}")
            return None

    def is_pool_state_fresh(self, pool_tier: str, max_age_hours: int = 24) -> bool:
        """
        检查池状态是否新鲜（最近24小时内更新）

        Args:
            pool_tier: 池层级
            max_age_hours: 最大有效期（小时）

        Returns:
            是否新鲜
        """
        updated_at = self.get_pool_state_age(pool_tier)
        if updated_at is None:
            return False
        age = datetime.now() - updated_at
        return age.total_seconds() < (max_age_hours * 3600)


# ==================== 全局单例 ====================

_pool_state_store: Optional[PoolStateStore] = None


def get_pool_state_store() -> PoolStateStore:
    """获取 PoolStateStore 单例"""
    global _pool_state_store
    if _pool_state_store is None:
        _pool_state_store = PoolStateStore()
    return _pool_state_store
