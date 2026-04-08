"""
Batcher 单元测试
"""

import pytest
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_manager.batcher import AsyncBatcher, BatchResult, AdaptiveConcurrency


class TestBatchResult:
    """批量结果数据类测试"""

    def test_dataclass(self):
        """测试数据类"""
        result = BatchResult(
            success_count=10,
            failed_count=2,
            total_time=1.5,
            results={'code1': {'data': 'test'}},
            errors={'code2': 'error'}
        )
        assert result.success_count == 10
        assert result.failed_count == 2
        assert result.total_time == 1.5

    def test_default_values(self):
        """测试默认值"""
        result = BatchResult()
        assert result.success_count == 0
        assert result.failed_count == 0
        assert result.total_time == 0.0
        assert result.results == {}
        assert result.errors == {}


class TestAsyncBatcher:
    """异步批量获取器测试类"""

    def setup_method(self):
        """每个测试前执行"""
        self.batcher = AsyncBatcher(max_workers=5)

    def test_initialization(self):
        """测试初始化"""
        assert self.batcher is not None
        assert self.batcher.max_workers == 5

    def test_batch_get_financial_success(self):
        """测试批量获取财务数据成功"""
        def mock_fetch(code):
            time.sleep(0.01)  # 模拟延迟
            return {'code': code, 'name': f'股票{code}'}

        codes = ['000001', '000002', '000003']
        result = self.batcher.batch_get_financial(codes, mock_fetch)

        assert result.success_count == 3
        assert result.failed_count == 0
        assert len(result.results) == 3

    def test_batch_get_financial_partial_failure(self):
        """测试批量获取部分失败"""
        def mock_fetch(code):
            if code == '000002':
                raise Exception("模拟失败")
            return {'code': code, 'name': f'股票{code}'}

        codes = ['000001', '000002', '000003']
        result = self.batcher.batch_get_financial(codes, mock_fetch)

        assert result.success_count == 2
        assert result.failed_count == 1
        assert '000002' in result.errors

    def test_batch_get_financial_empty(self):
        """测试空列表"""
        result = self.batcher.batch_get_financial([], lambda x: None)
        assert result.success_count == 0
        assert result.failed_count == 0

    def test_batch_get_market(self):
        """测试批量获取行情"""
        def mock_batch_fetch(codes):
            time.sleep(0.01)
            return [{'code': c, 'close': 10.0} for c in codes]

        codes = ['000001', '000002', '000003', '000004', '000005']
        results, errors = self.batcher.batch_get_market(
            codes, mock_batch_fetch, batch_size=2
        )

        assert len(results) == 5

    def test_get_stats(self):
        """测试获取统计信息"""
        # 执行一些操作
        def mock_fetch(code):
            time.sleep(0.01)
            return {'code': code}

        codes = ['000001', '000002']
        self.batcher.batch_get_financial(codes, mock_fetch)

        stats = self.batcher.get_stats()
        assert 'total_requests' in stats
        assert 'success_requests' in stats
        assert 'success_rate' in stats


class TestAdaptiveConcurrency:
    """自适应并发控制器测试类"""

    def test_initialization(self):
        """测试初始化"""
        ctrl = AdaptiveConcurrency(initial=10)
        assert ctrl.value == 10
        assert ctrl.min_val == 5
        assert ctrl.max_val == 100

    def test_record_response_time(self):
        """测试记录响应时间"""
        ctrl = AdaptiveConcurrency(initial=10)

        # 记录一些快速响应
        for _ in range(10):
            ctrl.record(0.1)  # 100ms

        # 不应该减少（因为是快速响应）
        assert ctrl.value >= 5

    def test_adjust_increases_concurrency(self):
        """测试调整增加并发"""
        ctrl = AdaptiveConcurrency(initial=5, min_val=5, max_val=100)

        # 记录很多快速响应
        for _ in range(20):
            ctrl.record(0.05)  # 50ms，远低于阈值

        # 应该增加并发
        assert ctrl.value > 5

    def test_adjust_decreases_concurrency(self):
        """测试调整减少并发"""
        ctrl = AdaptiveConcurrency(initial=50, min_val=5, max_val=100)

        # 记录慢响应
        for _ in range(20):
            ctrl.record(5.0)  # 5秒，远高于阈值

        # 应该减少并发
        assert ctrl.value < 50

    def test_bounds(self):
        """测试边界限制"""
        ctrl = AdaptiveConcurrency(initial=10, min_val=5, max_val=20)

        # 尝试增加到超过最大值
        for _ in range(50):
            ctrl.record(0.01)

        assert ctrl.value <= 20

        # 尝试减少到低于最小值
        for _ in range(50):
            ctrl.record(10.0)

        assert ctrl.value >= 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
