"""
Adjuster 单元测试
"""

import pytest

from backend.data_manager.adjuster import AdjustmentManager, AdjustmentFactor, ExRightEvent


class TestAdjustmentManager:
    """复权因子管理器测试类"""

    def setup_method(self):
        """每个测试前执行"""
        # 使用临时数据库
        import tempfile
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.manager = AdjustmentManager(db_path=self.temp_db.name)

    def teardown_method(self):
        """每个测试后执行"""
        import os
        try:
            os.unlink(self.temp_db.name)
        except OSError:
            pass

    def test_initialization(self):
        """测试初始化"""
        assert self.manager is not None
        stats = self.manager.get_stats()
        assert stats['total_factors'] == 0

    def test_save_and_get_factor(self):
        """测试保存和获取因子"""
        # 保存因子
        self.manager.save_factor('000001', '2024-01-01', 'qfq', 1.05)

        # 获取因子
        factor = self.manager.get_factor('000001', '2024-01-01', 'qfq')
        assert factor == 1.05

    def test_get_factor_not_found(self):
        """测试获取不存在的因子"""
        factor = self.manager.get_factor('999999', '2024-01-01', 'qfq')
        assert factor is None

    def test_save_factors_batch(self):
        """测试批量保存因子"""
        factors = [
            {'symbol': '000001', 'trade_date': '2024-01-01', 'adj_type': 'qfq', 'factor': 1.05},
            {'symbol': '000001', 'trade_date': '2024-01-02', 'adj_type': 'qfq', 'factor': 1.06},
            {'symbol': '000002', 'trade_date': '2024-01-01', 'adj_type': 'qfq', 'factor': 1.10},
        ]

        self.manager.save_factors(factors)
        stats = self.manager.get_stats()
        assert stats['total_factors'] == 3

    def test_get_latest_factor(self):
        """测试获取最新因子"""
        self.manager.save_factor('000001', '2024-01-01', 'qfq', 1.05)
        self.manager.save_factor('000001', '2024-01-03', 'qfq', 1.10)
        self.manager.save_factor('000001', '2024-01-02', 'qfq', 1.08)

        latest = self.manager.get_latest_factor('000001', 'qfq')
        assert latest == 1.10

    def test_calculate_adjusted_price(self):
        """测试复权价格计算"""
        # 前复权价格 = 原始价格 × (当前因子 / 历史因子)
        # 10.0 × (1.10 / 1.00) = 11.0
        result = self.manager.calculate_adjusted_price(10.0, 1.10, 1.00)
        assert result == 11.0

    def test_calculate_adjusted_price_with_none(self):
        """测试含None的计算"""
        result = self.manager.calculate_adjusted_price(10.0, None, 1.00)
        assert result == 10.0

        result = self.manager.calculate_adjusted_price(10.0, 1.10, None)
        assert result == 10.0

    def test_calculate_adjusted_price_with_zero(self):
        """测试含零的计算"""
        result = self.manager.calculate_adjusted_price(10.0, 0, 1.00)
        assert result == 10.0

        result = self.manager.calculate_adjusted_price(10.0, 1.10, 0)
        assert result == 10.0

    def test_get_adjusted_price(self):
        """测试获取复权价格"""
        # 保存历史和当前因子
        self.manager.save_factor('000001', '2024-01-01', 'qfq', 1.00)
        self.manager.save_factor('000001', '2024-01-15', 'qfq', 1.10)

        # 计算复权价格: 10.0 × (1.10 / 1.00) = 11.0
        result = self.manager.get_adjusted_price('000001', '2024-01-01', 10.0, 'qfq')
        assert result == 11.0

    def test_get_adjusted_price_no_factor(self):
        """测试无因子时返回原价"""
        result = self.manager.get_adjusted_price('999999', '2024-01-01', 10.0, 'qfq')
        assert result == 10.0

    def test_adjust_price_series(self):
        """测试批量调整价格序列"""
        self.manager.save_factor('000001', '2024-01-01', 'qfq', 1.00)
        self.manager.save_factor('000001', '2024-01-02', 'qfq', 1.05)
        self.manager.save_factor('000001', '2024-01-03', 'qfq', 1.10)

        prices = [
            {'code': '000001', 'date': '2024-01-01', 'close': 10.0},
            {'code': '000001', 'date': '2024-01-02', 'close': 10.5},
            {'code': '000001', 'date': '2024-01-03', 'close': 11.0},
        ]

        result = self.manager.adjust_price_series(prices, 'qfq')
        assert len(result) == 3
        # 当前因子1.10，历史因子1.00
        assert result[0]['close'] == 11.0

    def test_adjust_price_series_with_missing(self):
        """测试含缺失数据的价格序列"""
        prices = [
            {'code': '000001', 'date': '2024-01-01'},
            {'code': '000001', 'date': '2024-01-02', 'close': 10.5},
            {},  # 空数据
        ]

        result = self.manager.adjust_price_series(prices, 'qfq')
        assert len(result) == 3


class TestAdjustmentFactor:
    """复权因子数据类测试"""

    def test_dataclass(self):
        """测试数据类"""
        factor = AdjustmentFactor(
            symbol='000001',
            trade_date='2024-01-01',
            adj_type='qfq',
            factor=1.05
        )
        assert factor.symbol == '000001'
        assert factor.adj_type == 'qfq'
        assert factor.factor == 1.05

    def test_str_representation(self):
        """测试字符串表示"""
        factor = AdjustmentFactor(
            symbol='000001',
            trade_date='2024-01-01',
            adj_type='qfq',
            factor=1.05
        )
        assert '000001' in str(factor)
        assert 'qfq' in str(factor)


class TestExRightEvent:
    """除权事件数据类测试"""

    def test_dataclass(self):
        """测试数据类"""
        event = ExRightEvent(
            symbol='000001',
            ex_date='2024-01-01',
            ex_type='dividend',
            dividend=0.5
        )
        assert event.symbol == '000001'
        assert event.ex_type == 'dividend'
        assert event.dividend == 0.5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
