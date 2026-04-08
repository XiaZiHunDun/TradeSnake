"""
熔断与限流器 - Circuit Breaker & Rate Limiter
============================================
职责：保护数据源调用，防止雪崩和封禁

功能：
1. CircuitBreaker - 熔断器，连续失败N次后暂停
2. RateLimiter - 令牌桶限流器
3. AdaptiveLimiter - 自适应限流器
4. TushareBudget - Tushare积分预算管理器
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any
from collections import defaultdict
from dataclasses import dataclass, field


# ==================== 熔断器 ====================

class CircuitBreaker:
    """
    熔断器

    状态转换：
    - Closed: 正常状态，请求通过
    - Open: 熔断状态，连续失败超过阈值，暂停所有请求
    - HalfOpen: 半开状态，Open后等待timeout，进入半开尝试一次

    配置：
    - failure_threshold: 连续失败次数阈值（默认5次）
    - timeout: 熔断持续时间（默认60秒）
    - half_open_max_calls: 半开状态允许的尝试次数（默认1次）
    """

    STATE_CLOSED = 'closed'
    STATE_OPEN = 'open'
    STATE_HALF_OPEN = 'half_open'

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = self.STATE_CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.RLock()

        self._stats = {
            'total_calls': 0,
            'success_calls': 0,
            'failed_calls': 0,
            'rejected_calls': 0,
            'state_changes': [],
        }

    @property
    def state(self) -> str:
        """获取当前状态"""
        with self._lock:
            if self._state == self.STATE_OPEN:
                # 检查是否应该转为半开
                if self._last_failure_time:
                    if time.time() - self._last_failure_time >= self.timeout:
                        self._state = self.STATE_HALF_OPEN
                        self._half_open_calls = 0
                        self._log_state_change(self.STATE_HALF_OPEN)
            return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器执行函数

        Args:
            func: 要执行的函数
            *args, **kwargs: 函数参数

        Returns:
            函数返回值

        Raises:
            CircuitOpenError: 熔断状态时抛出
        """
        with self._lock:
            self._stats['total_calls'] += 1

            current_state = self.state

            if current_state == self.STATE_OPEN:
                self._stats['rejected_calls'] += 1
                raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")

            elif current_state == self.STATE_HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    self._stats['rejected_calls'] += 1
                    raise CircuitOpenError(f"Circuit '{self.name}' is HALF_OPEN, max calls reached")

                self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise

    def on_success(self):
        """记录成功"""
        with self._lock:
            self._failure_count = 0
            self._success_count += 1
            self._stats['success_calls'] += 1

            if self._state == self.STATE_HALF_OPEN:
                # 半开状态下成功，转为Closed
                self._state = self.STATE_CLOSED
                self._log_state_change(self.STATE_CLOSED)

    def on_failure(self):
        """记录失败"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._stats['failed_calls'] += 1

            if self._state == self.STATE_HALF_OPEN:
                # 半开状态下失败，转为Open
                self._state = self.STATE_OPEN
                self._log_state_change(self.STATE_OPEN)

            elif self._failure_count >= self.failure_threshold:
                self._state = self.STATE_OPEN
                self._log_state_change(self.STATE_OPEN)

    def _log_state_change(self, new_state: str):
        """记录状态变化"""
        self._stats['state_changes'].append({
            'time': datetime.now().isoformat(),
            'state': new_state,
            'failure_count': self._failure_count,
        })

    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            return {
                **self._stats,
                'current_state': self.state,
                'failure_count': self._failure_count,
                'success_count': self._success_count,
            }

    def reset(self):
        """重置熔断器"""
        with self._lock:
            self._state = self.STATE_CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0


class CircuitOpenError(Exception):
    """熔断开启异常"""
    pass


# ==================== 令牌桶限流器 ====================

class RateLimiter:
    """
    令牌桶限流器

    原理：
    - 桶容量：max_tokens
    - 补充速率：tokens_per_second
    - 每次请求消耗1个令牌

    使用场景：
    - 限制API调用频率
    - 防止被数据源封禁
    """

    def __init__(self, max_tokens: int = 100, tokens_per_second: float = 10.0):
        self.max_tokens = max_tokens
        self.tokens_per_second = tokens_per_second

        self._tokens = float(max_tokens)
        self._last_update = time.time()
        self._lock = threading.Lock()

        self._stats = {
            'total_requests': 0,
            'allowed_requests': 0,
            'rejected_requests': 0,
        }

    def acquire(self, tokens: int = 1) -> bool:
        """
        获取令牌

        Args:
            tokens: 需要获取的令牌数

        Returns:
            True: 获取成功
            False: 获取失败（令牌不足）
        """
        with self._lock:
            self._stats['total_requests'] += 1

            # 补充令牌
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(self.max_tokens, self._tokens + elapsed * self.tokens_per_second)
            self._last_update = now

            # 尝试获取
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._stats['allowed_requests'] += 1
                return True
            else:
                self._stats['rejected_requests'] += 1
                return False

    def wait_and_acquire(self, tokens: int = 1, timeout: float = 5.0) -> bool:
        """
        等待并获取令牌

        Args:
            tokens: 需要获取的令牌数
            timeout: 最大等待时间

        Returns:
            True: 获取成功
            False: 超时失败
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.acquire(tokens):
                return True
            time.sleep(0.01)  # 短暂等待
        return False

    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            return {
                **self._stats,
                'current_tokens': round(self._tokens, 2),
                'max_tokens': self.max_tokens,
            }


# ==================== 自适应限流器 ====================

class AdaptiveLimiter:
    """
    自适应限流器

    原理：根据数据源响应时间动态调整并发数
    - 响应时间 > threshold: 减少并发
    - 响应时间 < threshold: 增加并发
    """

    def __init__(
        self,
        initial_concurrency: int = 30,
        min_concurrency: int = 5,
        max_concurrency: int = 100,
        slow_threshold: float = 2.0,  # >2秒认为是慢请求
        fast_threshold: float = 0.5,  # <500ms认为是快请求
    ):
        self.concurrency = initial_concurrency
        self.min_concurrency = min_concurrency
        self.max_concurrency = max_concurrency
        self.slow_threshold = slow_threshold
        self.fast_threshold = fast_threshold

        self._lock = threading.Lock()
        self._response_times: List[float] = []
        self._max_samples = 100

    def record_response_time(self, response_time: float):
        """记录响应时间"""
        with self._lock:
            self._response_times.append(response_time)
            if len(self._response_times) > self._max_samples:
                self._response_times.pop(0)

            self._adjust_concurrency(response_time)

    def _adjust_concurrency(self, response_time: float):
        """根据响应时间调整并发数"""
        if response_time > self.slow_threshold:
            # 慢请求，减少并发
            self.concurrency = max(self.min_concurrency, self.concurrency - 5)
        elif response_time < self.fast_threshold:
            # 快请求，增加并发
            self.concurrency = min(self.max_concurrency, self.concurrency + 5)

    def get_average_response_time(self) -> float:
        """获取平均响应时间"""
        with self._lock:
            if not self._response_times:
                return 0
            return sum(self._response_times) / len(self._response_times)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            return {
                'concurrency': self.concurrency,
                'min_concurrency': self.min_concurrency,
                'max_concurrency': self.max_concurrency,
                'avg_response_time': round(self.get_average_response_time(), 3),
                'sample_count': len(self._response_times),
            }


# ==================== Tushare积分预算管理器 ====================

@dataclass
class TushareBudget:
    """Tushare积分预算"""
    daily_budget: int = 100  # 每日预算
    used_today: int = 0     # 今日已使用
    last_reset_date: str = ''  # 上次重置日期

    # 各接口消耗（示例，实际以Tushare文档为准）
    INTERFACE_COSTS = {
        'daily_basic': 100,    # 每日指标
        'moneyflow': 200,      # 资金流向
        'fina_indicator': 500, # 财务指标
        'income': 300,         # 利润表
        'balancesheet': 300,  # 资产负债表
        'cashflow': 300,      # 现金流量表
    }

    def check_and_use(self, interface: str) -> bool:
        """
        检查预算并使用

        Args:
            interface: 接口名称

        Returns:
            True: 使用成功
            False: 预算不足
        """
        cost = self.INTERFACE_COSTS.get(interface, 100)

        self._check_daily_reset()

        if self.used_today + cost > self.daily_budget:
            return False

        self.used_today += cost
        return True

    def _check_daily_reset(self):
        """检查是否需要每日重置"""
        today = datetime.now().strftime('%Y-%m-%d')
        if self.last_reset_date != today:
            self.used_today = 0
            self.last_reset_date = today

    def get_remaining(self) -> int:
        """获取剩余预算"""
        self._check_daily_reset()
        return max(0, self.daily_budget - self.used_today)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        self._check_daily_reset()
        return {
            'daily_budget': self.daily_budget,
            'used_today': self.used_today,
            'remaining': self.get_remaining(),
            'usage_percent': round(self.used_today / self.daily_budget * 100, 1),
        }


# ==================== 数据源熔断管理器 ====================

class DataSourceCircuitManager:
    """
    数据源熔断管理器

    为每个数据源管理独立的熔断器和限流器
    """

    def __init__(self):
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = threading.Lock()

        # 默认配置
        self._configs = {
            'tencent': {'failure_threshold': 5, 'timeout': 60, 'max_tokens': 50, 'tokens_per_second': 10},
            'sina': {'failure_threshold': 5, 'timeout': 60, 'max_tokens': 50, 'tokens_per_second': 10},
            'eastmoney': {'failure_threshold': 5, 'timeout': 60, 'max_tokens': 30, 'tokens_per_second': 5},
            'baostock': {'failure_threshold': 5, 'timeout': 60, 'max_tokens': 30, 'tokens_per_second': 5},
            'akshare': {'failure_threshold': 5, 'timeout': 60, 'max_tokens': 30, 'tokens_per_second': 5},
            'tushare': {'failure_threshold': 5, 'timeout': 120, 'max_tokens': 20, 'tokens_per_second': 2},
        }

        # Tushare积分预算
        self._tushare_budget = TushareBudget()

    def get_circuit(self, source: str) -> CircuitBreaker:
        """获取数据源的熔断器"""
        with self._lock:
            if source not in self._circuits:
                config = self._configs.get(source, self._configs['tencent'])
                self._circuits[source] = CircuitBreaker(
                    name=source,
                    failure_threshold=config['failure_threshold'],
                    timeout=config['timeout'],
                )
            return self._circuits[source]

    def get_limiter(self, source: str) -> RateLimiter:
        """获取数据源的限流器"""
        with self._lock:
            if source not in self._limiters:
                config = self._configs.get(source, self._configs['tencent'])
                self._limiters[source] = RateLimiter(
                    max_tokens=config['max_tokens'],
                    tokens_per_second=config['tokens_per_second'],
                )
            return self._limiters[source]

    def call_with_protection(
        self,
        source: str,
        func: Callable,
        *args,
        use_tushare_budget: bool = False,
        tushare_interface: str = None,
        **kwargs
    ) -> Any:
        """
        带熔断和限流保护调用

        Args:
            source: 数据源名称
            func: 要执行的函数
            use_tushare_budget: 是否使用Tushare预算
            tushare_interface: Tushare接口名称

        Returns:
            函数返回值
        """
        # Tushare积分预算检查
        if use_tushare_budget and tushare_interface:
            if not self._tushare_budget.check_and_use(tushare_interface):
                raise TushareBudgetExhaustedError(
                    f"Tushare budget exhausted for {tushare_interface}"
                )

        # 限流检查
        limiter = self.get_limiter(source)
        if not limiter.acquire():
            raise RateLimitExceededError(f"Rate limit exceeded for {source}")

        # 熔断器调用
        circuit = self.get_circuit(source)
        return circuit.call(func, *args, **kwargs)

    def get_stats(self) -> Dict:
        """获取所有数据源状态"""
        with self._lock:
            stats = {
                'circuits': {},
                'limiters': {},
                'tushare_budget': self._tushare_budget.get_stats(),
            }

            for source, circuit in self._circuits.items():
                stats['circuits'][source] = circuit.get_stats()

            for source, limiter in self._limiters.items():
                stats['limiters'][source] = limiter.get_stats()

            return stats


class RateLimitExceededError(Exception):
    """限流异常"""
    pass


class TushareBudgetExhaustedError(Exception):
    """Tushare积分耗尽异常"""
    pass


# ==================== 全局单例 ====================

_circuit_manager = None


def get_circuit_manager() -> DataSourceCircuitManager:
    """获取熔断管理器单例"""
    global _circuit_manager
    if _circuit_manager is None:
        _circuit_manager = DataSourceCircuitManager()
    return _circuit_manager


# ==================== 便捷函数 ====================

def call_with_protection(
    source: str,
    func: Callable,
    *args,
    **kwargs
) -> Any:
    """带保护的调用"""
    return get_circuit_manager().call_with_protection(source, func, *args, **kwargs)


def get_source_stats(source: str = None) -> Dict:
    """获取数据源状态"""
    manager = get_circuit_manager()
    if source:
        return {
            'circuit': manager.get_circuit(source).get_stats(),
            'limiter': manager.get_limiter(source).get_stats(),
        }
    return manager.get_stats()
