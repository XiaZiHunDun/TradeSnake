"""
数据备份机制 - Backup Mechanism
================================
职责：SQLite在线备份、缓存备份、历史数据备份、备份恢复

备份策略：
- SQLite数据库：每日收盘后(23:30)备份，保留7天
- 缓存JSON：每日备份，保留3天
- 战力历史：每周备份，保留30天

特点：
- SQLite使用在线备份API（backup to），不影响服务
- 原子写入保证备份完整性
- 自动清理过期备份
"""

import os
import shutil
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
import threading
import json


# ==================== 路径配置 ====================

from backend.config import DATA_DIR, BACKUP_DIR, SQLITE_PATH
SQLITE_DB_PATH = str(SQLITE_PATH)


# ==================== 备份配置 ====================

@dataclass
class BackupStrategy:
    """备份策略配置"""
    frequency: str  # 'daily', 'weekly'
    time: str       # 'HH:MM' format
    retention: int  # 保留天数
    location: Path  # 备份目录


BACKUP_STRATEGIES = {
    'sqlite_db': BackupStrategy(
        frequency='daily',
        time='02:00',  # 凌晨执行，与清理协同
        retention=7,
        location=BACKUP_DIR / 'sqlite'
    ),
    'cache_json': BackupStrategy(
        frequency='daily',
        time='02:00',
        retention=3,
        location=BACKUP_DIR / 'cache'
    ),
    'cp_history': BackupStrategy(
        frequency='weekly',
        time='sun 02:00',
        retention=365,  # 战力历史备份保留1年
        location=BACKUP_DIR / 'history'
    ),
    'protected_backup': BackupStrategy(
        frequency='on_cleanup',
        time='',
        retention=7,  # 清理保护备份保留7天
        location=BACKUP_DIR / 'protected'
    ),
}


# ==================== 备份结果 ====================

@dataclass
class BackupResult:
    """备份结果"""
    success: bool
    backup_type: str
    backup_path: Optional[str] = None
    error: Optional[str] = None
    size_bytes: int = 0


@dataclass
class CleanupResult:
    """清理结果"""
    success: bool
    deleted_count: int = 0
    freed_bytes: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


# ==================== 备份管理器 ====================

class BackupManager:
    """
    备份管理器

    功能：
    1. SQLite在线备份（不中断服务）
    2. 缓存JSON备份
    3. 战力历史备份
    4. 自动清理过期备份
    5. 备份状态查询
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(SQLITE_DB_PATH)
        self.backup_dir = BACKUP_DIR
        self._ensure_backup_dirs()
        self._lock = threading.Lock()

    def _ensure_backup_dirs(self):
        """确保备份目录存在"""
        for strategy in BACKUP_STRATEGIES.values():
            strategy.location.mkdir(parents=True, exist_ok=True)

    def backup_sqlite(self) -> BackupResult:
        """
        SQLite在线备份

        使用SQLite的backup to命令，不影响服务运行。
        """
        try:
            today = date.today().isoformat()
            backup_file = BACKUP_STRATEGIES['sqlite_db'].location / f"tradesnake_{today}.db"

            # 连接源数据库和目标文件
            source_conn = sqlite3.connect(self.db_path, timeout=30)
            backup_conn = sqlite3.connect(str(backup_file), timeout=30)

            # 执行在线备份
            source_conn.backup(backup_conn)

            backup_conn.close()
            source_conn.close()

            size = backup_file.stat().st_size

            return BackupResult(
                success=True,
                backup_type='sqlite_db',
                backup_path=str(backup_file),
                size_bytes=size
            )

        except Exception as e:
            return BackupResult(
                success=False,
                backup_type='sqlite_db',
                error=str(e)
            )

    def backup_cache_json(self, data_dir: Path = None) -> BackupResult:
        """
        缓存JSON备份

        v19.9.3: 修复路径问题 - cache.py 写入 data/*.json，而非 data/cache/*.json
        """
        data_path = data_dir or DATA_DIR

        try:
            today = date.today().isoformat()
            backup_location = BACKUP_STRATEGIES['cache_json'].location
            backup_file = backup_location / f"cache_{today}.tar.gz"

            # 使用tarball备份，保持原子性
            import tarfile
            import tempfile

            # v19.9.3: 直接从 data/ 目录备份 *.json 文件
            json_files = list(data_path.glob("*.json"))
            if not json_files:
                return BackupResult(
                    success=False,
                    backup_type='cache_json',
                    error=f"No JSON cache files found in {data_path}"
                )

            with tarfile.open(str(backup_file), "w:gz") as tar:
                for json_file in json_files:
                    tar.add(json_file, arcname=json_file.name)

            size = backup_file.stat().st_size

            return BackupResult(
                success=True,
                backup_type='cache_json',
                backup_path=str(backup_file),
                size_bytes=size
            )

        except Exception as e:
            return BackupResult(
                success=False,
                backup_type='cache_json',
                error=str(e)
            )

    def backup_cp_history(self, data_dir: Path = None) -> BackupResult:
        """
        战力历史备份

        备份战力历史相关的数据。
        """
        data_path = data_dir or DATA_DIR

        try:
            today = date.today().isoformat()
            backup_location = BACKUP_STRATEGIES['cp_history'].location
            backup_file = backup_location / f"cp_history_{today}.json"

            # 查找并合并历史数据文件
            history_data = []

            # 查找所有历史记录文件
            history_files = list(data_path.glob("cp_history_*.json"))
            for hf in history_files:
                try:
                    with open(hf, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            history_data.extend(data)
                        else:
                            history_data.append(data)
                except Exception:
                    continue

            # 保存合并后的历史
            if history_data:
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(history_data, f, ensure_ascii=False, indent=2)

                size = backup_file.stat().st_size
            else:
                # 没有历史数据，仍然创建空文件标记
                backup_file.write_text('[]', encoding='utf-8')
                size = 0

            return BackupResult(
                success=True,
                backup_type='cp_history',
                backup_path=str(backup_file),
                size_bytes=size
            )

        except Exception as e:
            return BackupResult(
                success=False,
                backup_type='cp_history',
                error=str(e)
            )

    def backup_all(self) -> List[BackupResult]:
        """执行所有备份"""
        results = []
        results.append(self.backup_sqlite())
        results.append(self.backup_cache_json())
        results.append(self.backup_cp_history())
        return results

    def cleanup_old_backups(self) -> CleanupResult:
        """清理过期备份"""
        result = CleanupResult(success=True)
        today = date.today()

        for name, strategy in BACKUP_STRATEGIES.items():
            try:
                cutoff_date = today - timedelta(days=strategy.retention)
                cutoff_str = cutoff_date.isoformat()

                # 查找过期备份
                for backup_file in strategy.location.glob(f"{name}_*.db") or \
                                  strategy.location.glob(f"*.json") or \
                                  strategy.location.glob(f"*.tar.gz"):
                    # 从文件名提取日期
                    filename = backup_file.stem
                    parts = filename.split('_')

                    if len(parts) >= 2:
                        file_date_str = parts[-1]  # 取最后一部分作为日期

                        try:
                            file_date = datetime.strptime(file_date_str, '%Y-%m-%d').date()
                            if file_date < cutoff_date:
                                size = backup_file.stat().st_size
                                backup_file.unlink()
                                result.deleted_count += 1
                                result.freed_bytes += size
                        except ValueError:
                            # 日期解析失败，跳过
                            continue

            except Exception as e:
                result.errors.append(f"{name}: {str(e)}")
                result.success = False

        return result

    def get_backup_status(self) -> Dict:
        """获取备份状态"""
        status = {
            'backup_dirs': {},
            'latest_backups': {},
            'total_size': 0,
        }

        today = date.today()

        for name, strategy in BACKUP_STRATEGIES.items():
            dir_path = strategy.location

            if not dir_path.exists():
                status['backup_dirs'][name] = {
                    'exists': False,
                    'file_count': 0,
                    'total_size': 0,
                }
                continue

            files = list(dir_path.iterdir())
            total_size = sum(f.stat().st_size for f in files if f.is_file())

            # 找最新备份
            latest = None
            latest_date = None
            for f in files:
                if f.is_file():
                    parts = f.stem.split('_')
                    if len(parts) >= 2:
                        try:
                            file_date = datetime.strptime(parts[-1], '%Y-%m-%d').date()
                            if latest_date is None or file_date > latest_date:
                                latest_date = file_date
                                latest = f
                        except ValueError:
                            continue

            # 检查是否需要备份
            needs_backup = False
            if latest is None:
                needs_backup = True
            elif (today - latest_date).days >= 1 and strategy.frequency == 'daily':
                needs_backup = True

            status['backup_dirs'][name] = {
                'exists': True,
                'file_count': len(files),
                'total_size': total_size,
                'latest_backup': str(latest) if latest else None,
                'latest_date': latest_date.isoformat() if latest_date else None,
                'needs_backup': needs_backup,
                'retention_days': strategy.retention,
            }
            status['total_size'] += total_size

        return status

    def restore_sqlite(self, backup_file: str) -> BackupResult:
        """从备份恢复SQLite数据库"""
        try:
            backup_path = Path(backup_file)
            if not backup_path.exists():
                return BackupResult(
                    success=False,
                    backup_type='sqlite_db',
                    error=f"Backup file not found: {backup_file}"
                )

            # 备份当前数据库
            current_backup = self.db_path + f".pre_restore_{date.today().isoformat()}"
            shutil.copy2(self.db_path, current_backup)

            # v19.9.3: 修复恢复方向 - 应从备份文件恢复到当前数据库
            restore_conn = sqlite3.connect(str(backup_path))
            current_conn = sqlite3.connect(self.db_path)

            restore_conn.backup(current_conn)  # 从备份恢复到当前

            restore_conn.close()
            current_conn.close()

            return BackupResult(
                success=True,
                backup_type='sqlite_db',
                backup_path=f"恢复前已备份到: {current_backup}",
                size_bytes=backup_path.stat().st_size
            )

        except Exception as e:
            return BackupResult(
                success=False,
                backup_type='sqlite_db',
                error=str(e)
            )

    def list_backups(self, backup_type: str = None) -> List[Dict]:
        """列出可用备份"""
        backups = []

        types_to_check = [backup_type] if backup_type else BACKUP_STRATEGIES.keys()

        for name in types_to_check:
            if name not in BACKUP_STRATEGIES:
                continue

            strategy = BACKUP_STRATEGIES[name]
            dir_path = strategy.location

            if not dir_path.exists():
                continue

            for f in dir_path.iterdir():
                if f.is_file():
                    backups.append({
                        'type': name,
                        'file': f.name,
                        'path': str(f),
                        'size': f.stat().st_size,
                        'date': f.stat().st_mtime,
                        'retention_days': strategy.retention,
                    })

        return sorted(backups, key=lambda x: x['date'], reverse=True)


# ==================== 调度支持 ====================

class BackupScheduler:
    """备份调度器"""

    def __init__(self, backup_manager: BackupManager = None):
        self.backup_manager = backup_manager or BackupManager()
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[BackupResult], None]] = []

    def add_callback(self, callback: Callable[[BackupResult], None]):
        """添加备份完成回调"""
        self._callbacks.append(callback)

    def _run_daily_backup(self):
        """执行每日备份"""
        results = self.backup_manager.backup_all()

        for result in results:
            for callback in self._callbacks:
                try:
                    callback(result)
                except Exception:
                    pass

        # 清理过期备份
        self.backup_manager.cleanup_old_backups()

        # 清理过期的K线数据
        self._cleanup_old_klines()

        return results

    def _cleanup_old_klines(
        self,
        daily_keep_days: int = 730,
        minute_keep_days: int = 30
    ) -> Dict:
        """
        清理过期的K线数据

        Args:
            daily_keep_days: 日K线保留天数，默认730天（2年）
            minute_keep_days: 分钟K线保留天数，默认30天
        """
        try:
            from .duckdb_store import cleanup_all_old_data
            result = cleanup_all_old_data(
                daily_keep_days=daily_keep_days,
                minute_keep_days=minute_keep_days
            )
            print(f"K线数据清理完成: 日K线保留{daily_keep_days}天，分钟K线保留{minute_keep_days}天")
            return result
        except Exception as e:
            print(f"K线数据清理失败: {e}")
            return {'success': False, 'error': str(e)}

    def is_time_for_backup(self, strategy_name: str) -> bool:
        """检查是否到了备份时间"""
        from datetime import datetime

        strategy = BACKUP_STRATEGIES.get(strategy_name)
        if not strategy:
            return False

        now = datetime.now()
        target_time = datetime.strptime(strategy.time, '%H:%M').time()

        # 检查是否接近目标时间（5分钟窗口）
        current_minutes = now.hour * 60 + now.minute
        target_minutes = target_time.hour * 60 + target_time.minute

        return abs(current_minutes - target_minutes) < 5

    def check_and_run_scheduled_backup(self) -> List[BackupResult]:
        """检查并运行调度的备份"""
        with self._lock:
            results = []
            for name in BACKUP_STRATEGIES.keys():
                if self.is_time_for_backup(name):
                    result = self.backup_manager.backup_all()
                    results.extend(result)
                    break  # 只执行一次

            if results:
                # 清理过期备份
                self.backup_manager.cleanup_old_backups()

            return results


# ==================== 全局单例 ====================

_backup_manager = None


def get_backup_manager() -> BackupManager:
    """获取备份管理器单例"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager


# ==================== 便捷函数 ====================

def backup_sqlite() -> BackupResult:
    """备份SQLite"""
    return get_backup_manager().backup_sqlite()


def backup_cache() -> BackupResult:
    """备份缓存"""
    return get_backup_manager().backup_cache_json()


def backup_all() -> List[BackupResult]:
    """执行所有备份"""
    return get_backup_manager().backup_all()


def cleanup_old_backups() -> CleanupResult:
    """清理过期备份"""
    return get_backup_manager().cleanup_old_backups()


def get_backup_status() -> Dict:
    """获取备份状态"""
    return get_backup_manager().get_backup_status()
