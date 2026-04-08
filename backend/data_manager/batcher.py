"""
异步批量获取器 - Async Batcher
===============================
职责：并发批量获取数据，提升性能

实现方式：
- 阶段1: ThreadPoolExecutor（保持同步接口，避免大规模重构）
- 阶段2: 迁移到 httpx 异步（需要SQLite异步封装）

性能对比：
- 串行: 200只 × 100ms = 20秒
- 并发30: 200只 ÷ 30 × 100ms = 0.67秒
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Callable, Any, Optional, Tuple
from dataclasses import dataclass
import threading


# ==================== 配置 ====================

# 默认并发数
DEFAULT_CONCURRENCY = 30

# 单个请求超时（秒）
REQUEST_TIMEOUT = 10


# ==================== 结果封装 ====================

@dataclass
class BatchResult:
    """批量操作结果"""
    success_count: int = 0
    failed_count: int = 0
    total_time: float = 0.0
    results: Dict[str, Any] = None
    errors: Dict[str, str] = None

    def __post_init__(self):
        if self.results is None:
            self.results = {}
        if self.errors is None:
            self.errors = {}


# ==================== 异步批量获取器 ====================

class AsyncBatcher:
    """
    异步批量获取器

    使用 ThreadPoolExecutor 实现并发批量获取，
    保持同步接口，避免大规模重构。
    """

    def __init__(self, max_workers: int = DEFAULT_CONCURRENCY):
        self.max_workers = max_workers
        self._lock = threading.Lock()

        # 统计信息
        self._stats = {
            'total_requests': 0,
            'success_requests': 0,
            'failed_requests': 0,
            'total_time': 0.0,
        }

    def batch_get_financial(
        self,
        codes: List[str],
        fetch_func: Callable[[str], Optional[Dict]],
        concurrency: int = None,
        use_cache: bool = True
    ) -> BatchResult:
        """
        批量获取财务数据（并发）

        Args:
            codes: 股票代码列表
            fetch_func: 获取函数，签名为 (code: str) -> Optional[Dict]
            concurrency: 并发数，默认使用 self.max_workers
            use_cache: 是否使用缓存（由调用方保证）

        Returns:
            BatchResult: 包含成功/失败数量、耗时、结果、错误信息
        """
        if not codes:
            return BatchResult()

        workers = concurrency or self.max_workers
        start_time = time.time()

        results = {}
        errors = {}
        success_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有任务
            future_to_code = {
                executor.submit(fetch_func, code): code
                for code in codes
            }

            # 收集结果
            for future in as_completed(future_to_code):
                code = future_to_code[future]

                try:
                    data = future.result(timeout=REQUEST_TIMEOUT)
                    if data:
                        results[code] = data
                        success_count += 1
                    else:
                        errors[code] = "No data returned"
                        failed_count += 1
                except Exception as e:
                    errors[code] = str(e)
                    failed_count += 1

        total_time = time.time() - start_time

        # 更新统计
        self._update_stats(success_count, failed_count, total_time)

        return BatchResult(
            success_count=success_count,
            failed_count=failed_count,
            total_time=total_time,
            results=results,
            errors=errors
        )

    def batch_get_market(
        self,
        codes: List[str],
        fetch_func: Callable[[List[str]], List[Dict]],
        batch_size: int = 50,
        concurrency: int = None
    ) -> Tuple[List[Dict], Dict[str, str]]:
        """
        批量获取行情数据（分批并发）

        行情数据通常需要分批获取（如每批50只），
        但批与批之间可以并发。

        Args:
            codes: 股票代码列表
            fetch_func: 获取函数，签名为 (codes: List[str]) -> List[Dict]
            batch_size: 每批大小
            concurrency: 并发批数

        Returns:
            (all_results, errors)
        """
        if not codes:
            return [], {}

        workers = concurrency or max(1, self.max_workers // 10)
        start_time = time.time()

        # 分批
        batches = [
            codes[i:i + batch_size]
            for i in range(0, len(codes), batch_size)
        ]

        all_results = []
        errors = {}
        success_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_batch = {
                executor.submit(fetch_func, batch): i
                for i, batch in enumerate(batches)
            }

            # 按顺序收集结果
            batch_results = [None] * len(batches)
            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]

                try:
                    results = future.result(timeout=REQUEST_TIMEOUT * 2)
                    batch_results[batch_idx] = results
                    success_count += 1
                except Exception as e:
                    errors[f"batch_{batch_idx}"] = str(e)
                    batch_results[batch_idx] = []
                    failed_count += 1

        # 合并结果
        for results in batch_results:
            if results:
                all_results.extend(results)

        total_time = time.time() - start_time
        self._update_stats(success_count, failed_count, total_time)

        return all_results, errors

    def _update_stats(self, success: int, failed: int, duration: float):
        """更新统计信息"""
        with self._lock:
            self._stats['total_requests'] += success + failed
            self._stats['success_requests'] += success
            self._stats['failed_requests'] += failed
            self._stats['total_time'] += duration

    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            total = self._stats['total_requests']
            return {
                **self._stats,
                'success_rate': round(
                    self._stats['success_requests'] / total * 100, 2
                ) if total > 0 else 0,
                'avg_time_per_request': round(
                    self._stats['total_time'] / total * 1000, 2
                ) if total > 0 else 0,
            }


# ==================== 自适应并发控制器 ====================

class AdaptiveConcurrency:
    """
    自适应并发控制器

    根据响应时间动态调整并发数：
    - 响应时间 > 阈值：减少并发
    - 响应时间 < 阈值：增加并发
    """

    def __init__(
        self,
        initial: int = DEFAULT_CONCURRENCY,
        min_val: int = 5,
        max_val: int = 100,
        slow_threshold: float = 2.0,
        fast_threshold: float = 0.5,
    ):
        self.value = initial
        self.min_val = min_val
        self.max_val = max_val
        self.slow_threshold = slow_threshold
        self.fast_threshold = fast_threshold

        self._response_times: List[float] = []
        self._lock = threading.Lock()

    def record(self, response_time: float):
        """记录响应时间"""
        with self._lock:
            self._response_times.append(response_time)
            if len(self._response_times) > 100:
                self._response_times.pop(0)

            self._adjust()

    def _adjust(self):
        """根据响应时间调整并发数"""
        if len(self._response_times) < 10:
            return

        avg_time = sum(self._response_times) / len(self._response_times)

        if avg_time > self.slow_threshold:
            self.value = max(self.min_val, self.value - 5)
        elif avg_time < self.fast_threshold:
            self.value = min(self.max_val, self.value + 5)

    def get_value(self) -> int:
        """获取当前并发数"""
        with self._lock:
            return self.value


# ==================== 全局实例 ====================

_batcher = None
_adaptive_concurrency = AdaptiveConcurrency()


def get_batcher() -> AsyncBatcher:
    """获取批量获取器单例"""
    global _batcher
    if _batcher is None:
        _batcher = AsyncBatcher(
            max_workers=_adaptive_concurrency.get_value()
        )
    return _batcher


def get_adaptive_concurrency() -> AdaptiveConcurrency:
    """获取自适应并发控制器"""
    return _adaptive_concurrency
