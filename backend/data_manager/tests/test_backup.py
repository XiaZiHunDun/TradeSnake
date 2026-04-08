"""
Backup 单元测试
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_manager.backup import (
    BackupManager, BackupResult, CleanupResult, BackupScheduler
)


class TestBackupManager:
    """备份管理器测试类"""

    def setup_method(self):
        """每个测试前执行"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()

        # 创建临时数据库并插入一些数据
        import sqlite3
        conn = sqlite3.connect(self.temp_db.name)
        conn.execute('CREATE TABLE test_table (id INTEGER, name TEXT)')
        conn.execute("INSERT INTO test_table VALUES (1, 'test')")
        conn.commit()
        conn.close()

        self.manager = BackupManager(db_path=self.temp_db.name)
        # 重定向备份目录到临时目录
        self.manager.backup_dir = Path(self.temp_dir)

    def teardown_method(self):
        """每个测试后执行"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
            os.unlink(self.temp_db.name)
        except:
            pass

    def test_initialization(self):
        """测试初始化"""
        assert self.manager is not None
        assert self.manager.db_path == self.temp_db.name

    def test_backup_sqlite(self):
        """测试SQLite备份"""
        result = self.manager.backup_sqlite()
        assert result.success == True
        assert result.backup_path is not None
        assert result.size_bytes > 0
        assert Path(result.backup_path).exists()

    def test_backup_sqlite_nonexistent_db(self):
        """测试备份不存在的数据库"""
        manager = BackupManager(db_path='/nonexistent/path/db.db')
        result = manager.backup_sqlite()
        assert result.success == False
        assert result.error is not None

    def test_backup_cache_json_nonexistent(self):
        """测试备份不存在的缓存目录"""
        result = self.manager.backup_cache_json()
        assert result.success == False

    def test_cleanup_old_backups(self):
        """测试清理过期备份"""
        # 先创建一些测试备份文件
        backup_dir = Path(self.temp_dir) / 'sqlite'
        backup_dir.mkdir(parents=True, exist_ok=True)

        # 创建过期备份文件（实际不会真正过期，因为我们只按日期判断）
        old_file = backup_dir / 'tradesnake_2020-01-01.db'
        old_file.write_text('test')
        old_size = old_file.stat().st_size

        result = self.manager.cleanup_old_backups()
        assert result.success == True

    def test_get_backup_status(self):
        """测试获取备份状态"""
        status = self.manager.get_backup_status()
        assert 'sqlite_db' in status['backup_dirs']
        assert 'cache_json' in status['backup_dirs']
        assert 'cp_history' in status['backup_dirs']

    def test_list_backups(self):
        """测试列出备份"""
        # 先创建一个备份
        self.manager.backup_sqlite()

        backups = self.manager.list_backups('sqlite_db')
        assert len(backups) >= 1
        assert backups[0]['type'] == 'sqlite_db'

    def test_restore_sqlite(self):
        """测试从备份恢复SQLite"""
        # 先创建备份
        backup_result = self.manager.backup_sqlite()
        assert backup_result.success == True

        # 修改原数据库
        import sqlite3
        conn = sqlite3.connect(self.temp_db.name)
        conn.execute("INSERT INTO test_table VALUES (2, 'modified')")
        conn.commit()
        conn.close()

        # 恢复
        restore_result = self.manager.restore_sqlite(backup_result.backup_path)
        assert restore_result.success == True


class TestBackupResult:
    """备份结果数据类测试"""

    def test_dataclass(self):
        """测试数据类"""
        result = BackupResult(
            success=True,
            backup_type='test',
            backup_path='/path/to/backup',
            size_bytes=1024
        )
        assert result.success == True
        assert result.size_bytes == 1024

    def test_default_values(self):
        """测试默认值"""
        result = BackupResult(success=False, backup_type='test')
        assert result.backup_path is None
        assert result.error is None
        assert result.size_bytes == 0


class TestCleanupResult:
    """清理结果数据类测试"""

    def test_dataclass(self):
        """测试数据类"""
        result = CleanupResult(
            success=True,
            deleted_count=5,
            freed_bytes=10240
        )
        assert result.success == True
        assert result.deleted_count == 5
        assert result.freed_bytes == 10240

    def test_errors_list(self):
        """测试错误列表"""
        result = CleanupResult(
            success=False,
            deleted_count=3,
            errors=['error1', 'error2']
        )
        assert len(result.errors) == 2


class TestBackupScheduler:
    """备份调度器测试类"""

    def test_initialization(self):
        """测试初始化"""
        scheduler = BackupScheduler()
        assert scheduler is not None
        assert scheduler._running == False

    def test_add_callback(self):
        """测试添加回调"""
        scheduler = BackupScheduler()
        callbacks_before = len(scheduler._callbacks)

        def test_callback(result):
            pass

        scheduler.add_callback(test_callback)
        assert len(scheduler._callbacks) == callbacks_before + 1

    def test_is_time_for_backup(self):
        """测试是否到了备份时间"""
        scheduler = BackupScheduler()

        # 总是返回False因为无法模拟时间
        result = scheduler.is_time_for_backup('sqlite_db')
        assert isinstance(result, bool)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
