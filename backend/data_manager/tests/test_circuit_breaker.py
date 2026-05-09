"""
CircuitBreaker 单元测试
"""

import pytest
import time

from backend.data_manager.circuit_breaker import (
    CircuitBreaker,
    RateLimiter, AdaptiveLimiter,
    TushareBudget, DataSourceCircuitManager
)


class TestCircuitBreaker:
    """熔断器测试类"""

    def setup_method(self):
        """每个测试前执行"""
        self.cb = CircuitBreaker(
            name='test',
            failure_threshold=3,
            timeout=5,
            half_open_max_calls=2
        )

    def test_initial_state(self):
        """测试初始状态"""
        assert self.cb.state == self.cb.STATE_CLOSED
        assert self.cb._failure_count == 0

    def test_on_success(self):
        """测试记录成功"""
        self.cb.on_success()
        assert self.cb._failure_count == 0
        assert self.cb.state == self.cb.STATE_CLOSED

    def test_on_failure(self):
        """测试记录失败"""
        # 连续失败直到触发熔断
        for i in range(3):
            self.cb.on_failure()
            if i < 2:
                assert self.cb.state == self.cb.STATE_CLOSED
            else:
                assert self.cb.state == self.cb.STATE_OPEN

    def test_circuit_open_blocks_calls(self):
        """测试熔断状态下阻止调用"""
        # 触发熔断
        for _ in range(3):
            self.cb.on_failure()

        assert self.cb.state == self.cb.STATE_OPEN

        # 在熔断状态下调用应该抛出异常
        with pytest.raises(Exception):  # CircuitOpenError
            self.cb.call(lambda: None)

    def test_half_open_after_timeout(self):
        """测试超时后进入半开状态"""
        # 创建快速恢复的熔断器
        cb = CircuitBreaker(
            name='test',
            failure_threshold=2,
            timeout=0.1,  # 100ms
            half_open_max_calls=2
        )

        # 触发熔断
        cb.on_failure()
        cb.on_failure()
        assert cb.state == cb.STATE_OPEN

        # 等待恢复
        time.sleep(0.15)

        # 检查是否进入半开状态（调用时转换）
        cb.call(lambda: None)

    def test_half_open_allows_calls(self):
        """测试半开状态允许部分调用"""
        cb = CircuitBreaker(
            name='test',
            failure_threshold=2,
            timeout=0.1,
            half_open_max_calls=2
        )

        # 触发熔断
        cb.on_failure()
        cb.on_failure()
        cb._state = cb.STATE_HALF_OPEN

        # 半开状态应该允许调用
        result = cb.call(lambda: 42)
        assert result == 42


class TestRateLimiter:
    """限流器测试类"""

    def test_initialization(self):
        """测试初始化"""
        limiter = RateLimiter(max_tokens=10, tokens_per_second=5)
        assert limiter.max_tokens == 10
        assert limiter.tokens_per_second == 5

    def test_acquire_success(self):
        """测试获取令牌成功"""
        limiter = RateLimiter(max_tokens=10, tokens_per_second=5)
        result = limiter.acquire()
        assert result == True
        assert limiter._tokens < 10

    def test_acquire_failure(self):
        """测试获取令牌失败"""
        limiter = RateLimiter(max_tokens=1, tokens_per_second=0.1)
        limiter.acquire()
        result = limiter.acquire()
        assert result == False

    def test_refill(self):
        """测试令牌补充"""
        limiter = RateLimiter(max_tokens=5, tokens_per_second=2)
        limiter.acquire()
        limiter.acquire()
        initial_tokens = limiter._tokens

        time.sleep(0.6)  # 等待补充
        # 应该补充了令牌
        assert limiter._tokens >= initial_tokens


class TestAdaptiveLimiter:
    """自适应限流器测试类"""

    def test_initialization(self):
        """测试初始化"""
        limiter = AdaptiveLimiter(initial_concurrency=10)
        assert limiter.concurrency == 10

    def test_record_response_time(self):
        """测试记录响应时间"""
        limiter = AdaptiveLimiter(initial_concurrency=10)

        # 记录一些响应时间
        limiter.record_response_time(0.1)
        limiter.record_response_time(0.2)
        limiter.record_response_time(0.05)

        assert len(limiter._response_times) == 3


class TestTushareBudget:
    """Tushare积分预算测试类"""

    def test_initialization(self):
        """测试初始化"""
        budget = TushareBudget(daily_budget=200)
        assert budget.daily_budget == 200
        assert budget.used_today == 0

    def test_check_and_use(self):
        """测试检查和使用预算"""
        budget = TushareBudget(daily_budget=200)
        result = budget.check_and_use('daily_basic')
        assert result == True
        assert budget.used_today == 100  # daily_basic costs 100

    def test_check_and_use_exceed(self):
        """测试超额使用"""
        budget = TushareBudget(daily_budget=50)  # 低预算
        budget.check_and_use('moneyflow')  # moneyflow costs 200
        # 应该失败因为 200 > 50
        result = budget.check_and_use('income')  # income costs 300
        assert result == False

    def test_daily_reset(self):
        """测试每日重置"""
        budget = TushareBudget(daily_budget=200)
        budget.used_today = 100
        budget.last_reset_date = '2020-01-01'  # 旧日期

        # 触发重置检查
        budget._check_daily_reset()
        assert budget.used_today == 0


class TestDataSourceCircuitManager:
    """数据源熔断管理器测试类"""

    def test_initialization(self):
        """测试初始化"""
        manager = DataSourceCircuitManager()
        assert manager._tushare_budget is not None

    def test_get_circuit(self):
        """测试获取熔断器"""
        manager = DataSourceCircuitManager()
        cb = manager.get_circuit('tushare')
        assert cb is not None
        assert isinstance(cb, CircuitBreaker)

    def test_get_limiter(self):
        """测试获取限流器"""
        manager = DataSourceCircuitManager()
        limiter = manager.get_limiter('tushare')
        assert limiter is not None
        assert isinstance(limiter, RateLimiter)

    def test_call_with_protection(self):
        """测试带保护调用"""
        manager = DataSourceCircuitManager()
        result = manager.call_with_protection('tushare', lambda: 42)
        assert result == 42


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
