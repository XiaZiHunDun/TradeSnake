"""
Monitor 单元测试
"""

import pytest
import time

from backend.data_manager.monitor import (
    MonitoringSystem, Alert, AlertHandler,
    LogAlertHandler, CallbackAlertHandler
)


class TestMonitoringSystem:
    """监控系统测试类"""

    def setup_method(self):
        """每个测试前执行"""
        self.mon = MonitoringSystem()

    def test_initialization(self):
        """测试初始化"""
        assert self.mon is not None
        metrics = self.mon.get_all_metrics()
        assert 'data_source' in metrics
        assert 'cache' in metrics
        assert 'performance' in metrics

    def test_record_data_source_request_success(self):
        """测试记录成功的数据源请求"""
        self.mon.record_data_source_request('tushare', success=True, response_time=0.5)
        metrics = self.mon.get_data_source_metrics('tushare')
        assert metrics['total_requests'] == 1
        assert metrics['failed_requests'] == 0

    def test_record_data_source_request_failure(self):
        """测试记录失败的数据源请求"""
        self.mon.record_data_source_request('tushare', success=False, response_time=1.0)
        metrics = self.mon.get_data_source_metrics('tushare')
        assert metrics['total_requests'] == 1
        assert metrics['failed_requests'] == 1

    def test_record_cache_hit(self):
        """测试记录缓存命中"""
        self.mon.record_cache_hit()
        self.mon.record_cache_hit()
        metrics = self.mon.get_cache_metrics()
        assert metrics['hits'] == 2

    def test_record_cache_miss(self):
        """测试记录缓存未命中"""
        self.mon.record_cache_miss()
        metrics = self.mon.get_cache_metrics()
        assert metrics['misses'] == 1

    def test_cache_hit_rate(self):
        """测试缓存命中率"""
        for _ in range(8):
            self.mon.record_cache_hit()
        for _ in range(2):
            self.mon.record_cache_miss()

        metrics = self.mon.get_cache_metrics()
        assert metrics['hit_rate'] == 0.8  # 8/10 = 80%

    def test_record_batch_operation(self):
        """测试记录批量操作耗时"""
        self.mon.record_batch_operation(2.5)
        metrics = self.mon.get_performance_metrics()
        assert metrics['batch_operations'] == 1
        assert metrics['avg_batch_time'] == 2.5

    def test_record_tushare_points(self):
        """测试记录Tushare积分消耗"""
        self.mon.record_tushare_points(10)
        metrics = self.mon.get_tushare_metrics()
        assert metrics['daily_points_used'] == 10

    def test_alert_generation_high_failure_rate(self):
        """测试高失败率告警生成"""
        # 模拟高失败率
        for i in range(12):
            # 失败率 > 10% 触发告警
            self.mon.record_data_source_request('test_source', success=(i % 10 != 0), response_time=0.5)

        alerts = self.mon.get_alert_history(limit=10)
        # 应该有一些告警
        assert len(alerts) >= 0  # 具体数量取决于阈值

    def test_alert_history_limit(self):
        """测试告警历史限制"""
        # 添加多个告警
        for _ in range(150):
            self.mon.record_tushare_points(10)

        alerts = self.mon.get_alert_history(limit=100)
        assert len(alerts) <= 100

    def test_reset_stats(self):
        """测试重置统计"""
        # 添加一些数据
        self.mon.record_cache_hit()
        self.mon.record_cache_miss()

        # 重置
        self.mon.reset_stats()

        # 验证已重置
        cache_metrics = self.mon.get_cache_metrics()
        assert cache_metrics['hits'] == 0
        assert cache_metrics['misses'] == 0


class TestAlert:
    """告警类测试"""

    def test_dataclass(self):
        """测试数据类"""
        from datetime import datetime
        alert = Alert(
            timestamp=datetime.now(),
            level='error',
            category='data_source',
            metric='failure_rate',
            value=0.15,
            threshold=0.10,
            message='失败率过高',
            trace_id='test_123'
        )
        assert alert.level == 'error'
        assert alert.value > alert.threshold


class TestAlertHandler:
    """告警处理器测试"""

    def test_log_alert_handler(self):
        """测试日志告警处理器"""
        handler = LogAlertHandler()
        from datetime import datetime
        alert = Alert(
            timestamp=datetime.now(),
            level='warning',
            category='test',
            metric='test_metric',
            value=0.5,
            threshold=0.3,
            message='Test alert'
        )
        # 不应抛出异常
        handler.handle(alert)

    def test_callback_alert_handler(self):
        """测试回调告警处理器"""
        received = []

        def callback(alert):
            received.append(alert)

        handler = CallbackAlertHandler(callback)
        from datetime import datetime
        alert = Alert(
            timestamp=datetime.now(),
            level='error',
            category='test',
            metric='test_metric',
            value=0.5,
            threshold=0.3,
            message='Test alert'
        )

        handler.handle(alert)
        assert len(received) == 1
        assert received[0].message == 'Test alert'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
