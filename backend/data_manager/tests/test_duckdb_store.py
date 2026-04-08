"""
DuckDB Store 单元测试
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_manager.duckdb_store import (
    DuckDBStore, KlineRecord, QueryResult, HistoryMigrator
)


class TestKlineRecord:
    """K线记录数据类测试"""

    def test_dataclass(self):
        """测试数据类"""
        record = KlineRecord(
            code='000001',
            trade_date='2024-01-01',
            open=10.0,
            high=10.5,
            low=9.8,
            close=10.3,
            volume=1000000,
            amount=10000000,
            change_pct=1.5,
            adj_close=10.3
        )
        assert record.code == '000001'
        assert record.close == 10.3
        assert record.volume == 1000000


class TestDuckDBStore:
    """DuckDB存储管理器测试类"""

    def setup_method(self):
        """每个测试前执行"""
        # 使用不存在的临时路径，让DuckDB创建它
        self.temp_db_path = tempfile.mktemp(suffix='.duckdb')
        self.store = DuckDBStore(db_path=self.temp_db_path)

    def teardown_method(self):
        """每个测试后执行"""
        try:
            os.unlink(self.temp_db_path)
            # Also try to unlink WAL file if exists
            wal_path = self.temp_db_path + '.wal'
            if os.path.exists(wal_path):
                os.unlink(wal_path)
        except:
            pass

    def test_insert_daily_kline(self):
        """测试插入单条K线"""
        record = KlineRecord(
            code='000001',
            trade_date='2024-01-01',
            open=10.0,
            high=10.5,
            low=9.8,
            close=10.3,
            volume=1000000,
            amount=10000000,
            change_pct=1.5,
            adj_close=10.3
        )
        result = self.store.insert_daily_kline(record)
        assert result == True

        # 验证
        stats = self.store.get_stats()
        assert stats['total_rows'] == 1

    def test_insert_daily_klines_batch(self):
        """测试批量插入K线"""
        records = [
            KlineRecord(
                code='000001',
                trade_date=f'2024-01-{i+1:02d}',
                open=10.0 + i,
                high=10.5 + i,
                low=9.8 + i,
                close=10.3 + i,
                volume=1000000 + i * 100000,
                amount=10000000 + i * 1000000,
                change_pct=1.5 + i * 0.1,
                adj_close=10.3 + i
            )
            for i in range(5)
        ]

        success, errors = self.store.insert_daily_klines_batch(records)
        assert success == 5
        assert errors == 0

    def test_get_klines(self):
        """测试查询K线"""
        # 插入测试数据
        record = KlineRecord(
            code='000001',
            trade_date='2024-01-01',
            open=10.0,
            high=10.5,
            low=9.8,
            close=10.3,
            volume=1000000,
            amount=10000000,
            change_pct=1.5,
            adj_close=10.3
        )
        self.store.insert_daily_kline(record)

        # 查询
        result = self.store.get_klines('000001')
        assert result.success == True
        assert result.row_count == 1
        assert result.data is not None

    def test_get_klines_with_date_range(self):
        """测试按日期范围查询"""
        # 插入多条数据
        for i in range(10):
            record = KlineRecord(
                code='000001',
                trade_date=f'2024-01-{i+1:02d}',
                open=10.0 + i,
                high=10.5 + i,
                low=9.8 + i,
                close=10.3 + i,
                volume=1000000,
                amount=10000000,
                change_pct=1.5,
                adj_close=10.3 + i
            )
            self.store.insert_daily_kline(record)

        # 按范围查询
        result = self.store.get_klines('000001', start_date='2024-01-03', end_date='2024-01-07', limit=10)
        assert result.success == True
        assert result.row_count == 5

    def test_get_latest_kline(self):
        """测试获取最新K线"""
        # 插入多条数据
        for date_str in ['2024-01-01', '2024-01-02', '2024-01-03']:
            record = KlineRecord(
                code='000001',
                trade_date=date_str,
                open=10.0,
                high=10.5,
                low=9.8,
                close=10.3,
                volume=1000000,
                amount=10000000,
                change_pct=1.5,
                adj_close=10.3
            )
            self.store.insert_daily_kline(record)

        latest = self.store.get_latest_kline('000001')
        assert latest is not None

    def test_get_ma(self):
        """测试计算均线"""
        # 插入多条数据
        for i in range(10):
            record = KlineRecord(
                code='000001',
                trade_date=f'2024-01-{i+1:02d}',
                open=10.0 + i,
                high=10.5 + i,
                low=9.8 + i,
                close=10.0 + i,  # 收盘价从10到19
                volume=1000000,
                amount=10000000,
                change_pct=1.5,
                adj_close=10.0 + i
            )
            self.store.insert_daily_kline(record)

        # 计算MA5
        result = self.store.get_ma('000001', days=5)
        assert result.success == True
        assert result.data.iloc[0]['ma'] is not None

    def test_get_volume_history(self):
        """测试获取成交量历史"""
        # 插入多条数据
        for i in range(20):
            record = KlineRecord(
                code='000001',
                trade_date=f'2024-01-{i+1:02d}',
                open=10.0,
                high=10.5,
                low=9.8,
                close=10.3,
                volume=1000000 + i * 100000,
                amount=10000000,
                change_pct=1.5,
                adj_close=10.3
            )
            self.store.insert_daily_kline(record)

        volumes = self.store.get_volume_history('000001', days=10)
        assert len(volumes) == 10

    def test_get_stats(self):
        """测试获取统计信息"""
        # 插入测试数据
        for code in ['000001', '000002']:
            for i in range(3):
                record = KlineRecord(
                    code=code,
                    trade_date=f'2024-01-{i+1:02d}',
                    open=10.0,
                    high=10.5,
                    low=9.8,
                    close=10.3,
                    volume=1000000,
                    amount=10000000,
                    change_pct=1.5,
                    adj_close=10.3
                )
                self.store.insert_daily_kline(record)

        stats = self.store.get_stats()
        assert stats['total_rows'] == 6
        assert stats['total_codes'] == 2

    def test_query(self):
        """测试自定义SQL查询"""
        # 插入测试数据
        record = KlineRecord(
            code='000001',
            trade_date='2024-01-01',
            open=10.0,
            high=10.5,
            low=9.8,
            close=10.3,
            volume=1000000,
            amount=10000000,
            change_pct=1.5,
            adj_close=10.3
        )
        self.store.insert_daily_kline(record)

        # 执行自定义查询
        result = self.store.query("SELECT COUNT(*) as cnt FROM daily_kline")
        assert result.success == True
        assert result.data.iloc[0]['cnt'] == 1


class TestHistoryMigrator:
    """历史数据迁移器测试"""

    def test_initialization(self):
        """测试初始化"""
        migrator = HistoryMigrator()
        assert migrator is not None
        assert migrator.duckdb is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
