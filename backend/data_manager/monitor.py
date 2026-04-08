"""
监控告警体系 - Monitoring and Alerting System
=============================================
职责：数据源监控、缓存监控、数据质量监控、性能监控、Tushare预算监控

告警阈值：
| 指标类型 | 监控指标 | 告警阈值 |
|---------|---------|---------|
| 数据源 | 失败率、平均响应时间 | 失败率>10%，响应>3秒 |
| 缓存 | 命中率、内存占用、磁盘占用 | 命中率<80% |
| 数据质量 | D级占比、必填字段缺失率 | D级占比>5% |
| 性能 | 批量获取耗时、单股查询耗时 | 批量>5秒 |
| Tushare | 每日积分消耗 | 单日消耗>80%预算 |
"""

import time
import logging
import threading
from datetime import datetime, date
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path


# ==================== 日志配置 ====================

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(trace_id)s - %(source_module)s - %(message)s"


def get_logger(name: str = "data_manager") -> logging.Logger:
    """获取带统一格式的logger"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ==================== 告警阈值配置 ====================

ALERT_THRESHOLDS = {
    "data_source": {
        "failure_rate": 0.10,      # 失败率 > 10%
        "response_time": 3.0,       # 响应时间 > 3秒
    },
    "cache": {
        "hit_rate": 0.80,          # 命中率 < 80%
    },
    "data_quality": {
        "d_level_ratio": 0.05,      # D级占比 > 5%
    },
    "performance": {
        "batch_time": 5.0,         # 批量获取 > 5秒
    },
    "tushare": {
        "daily_budget": 0.80,      # 单日消耗 > 80%预算
    }
}


# ==================== 数据类 ====================

@dataclass
class Alert:
    """告警信息"""
    timestamp: datetime
    level: str  # 'warning', 'error', 'critical'
    category: str  # 'data_source', 'cache', 'data_quality', 'performance', 'tushare'
    metric: str
    value: float
    threshold: float
    message: str
    trace_id: str = ""


@dataclass
class DataSourceMetrics:
    """数据源指标"""
    source: str
    total_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    last_request_time: Optional[datetime] = None

    @property
    def failure_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    @property
    def avg_response_time(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time / self.total_requests


@dataclass
class CacheMetrics:
    """缓存指标"""
    hits: int = 0
    misses: int = 0
    memory_entries: int = 0
    disk_entries: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


@dataclass
class DataQualityMetrics:
    """数据质量指标"""
    total_records: int = 0
    d_level_records: int = 0
    missing_required_fields: int = 0

    @property
    def d_level_ratio(self) -> float:
        if self.total_records == 0:
            return 0.0
        return self.d_level_records / self.total_records

    @property
    def missing_required_rate(self) -> float:
        if self.total_records == 0:
            return 0.0
        return self.missing_required_fields / self.total_records


@dataclass
class PerformanceMetrics:
    """性能指标"""
    batch_operations: int = 0
    batch_total_time: float = 0.0
    single_operations: int = 0
    single_total_time: float = 0.0

    @property
    def avg_batch_time(self) -> float:
        if self.batch_operations == 0:
            return 0.0
        return self.batch_total_time / self.batch_operations

    @property
    def avg_single_time(self) -> float:
        if self.single_operations == 0:
            return 0.0
        return self.single_total_time / self.single_operations


@dataclass
class TushareMetrics:
    """Tushare指标"""
    daily_points_used: int = 0
    daily_budget: int = 200  # 默认每日预算200点
    last_reset_date: date = field(default_factory=date.today)

    @property
    def daily_usage_ratio(self) -> float:
        if self.daily_budget == 0:
            return 0.0
        return self.daily_points_used / self.daily_budget


# ==================== 告警处理器 ====================

class AlertHandler:
    """告警处理器接口"""

    def handle(self, alert: Alert):
        """处理告警"""
        raise NotImplementedError


class LogAlertHandler(AlertHandler):
    """日志告警处理器"""

    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or get_logger()

    def handle(self, alert: Alert):
        log_method = {
            'warning': self.logger.warning,
            'error': self.logger.error,
            'critical': self.logger.critical,
        }.get(alert.level, self.logger.warning)

        log_method(alert.message, extra={
            'trace_id': alert.trace_id,
            'source_module': 'monitor'
        })


class CallbackAlertHandler(AlertHandler):
    """回调告警处理器"""

    def __init__(self, callback: Callable[[Alert], None]):
        self.callback = callback

    def handle(self, alert: Alert):
        self.callback(alert)


# ==================== 监控系统 ====================

class MonitoringSystem:
    """
    监控系统

    监控内容：
    1. 数据源指标（失败率、响应时间）
    2. 缓存指标（命中率）
    3. 数据质量指标（D级占比）
    4. 性能指标（批量/单股耗时）
    5. Tushare积分消耗
    """

    def __init__(self):
        self._lock = threading.Lock()

        # 指标存储
        self._data_source_metrics: Dict[str, DataSourceMetrics] = defaultdict(
            lambda: DataSourceMetrics(source="")
        )
        self._cache_metrics = CacheMetrics()
        self._data_quality_metrics = DataQualityMetrics()
        self._performance_metrics = PerformanceMetrics()
        self._tushare_metrics = TushareMetrics()

        # 告警处理器
        self._alert_handlers: List[AlertHandler] = [LogAlertHandler()]

        # 告警历史（最近100条）
        self._alert_history: List[Alert] = []
        self._max_history = 100

        # 统计锁
        self._stats_lock = threading.Lock()

        self.logger = get_logger()

    def add_alert_handler(self, handler: AlertHandler):
        """添加告警处理器"""
        with self._lock:
            self._alert_handlers.append(handler)

    def _emit_alert(self, alert: Alert):
        """发送告警"""
        with self._lock:
            self._alert_history.append(alert)
            if len(self._alert_history) > self._max_history:
                self._alert_history.pop(0)

            for handler in self._alert_handlers:
                handler.handle(alert)

    def _check_and_alert(
        self,
        category: str,
        metric: str,
        value: float,
        threshold: float,
        message: str,
        level: str = 'warning',
        trace_id: str = ""
    ):
        """检查阈值并发送告警"""
        if value > threshold:
            alert = Alert(
                timestamp=datetime.now(),
                level=level,
                category=category,
                metric=metric,
                value=value,
                threshold=threshold,
                message=message,
                trace_id=trace_id
            )
            self._emit_alert(alert)

    # ==================== 数据源监控 ====================

    def record_data_source_request(
        self,
        source: str,
        success: bool,
        response_time: float,
        trace_id: str = ""
    ):
        """记录数据源请求"""
        with self._stats_lock:
            metrics = self._data_source_metrics[source]
            metrics.total_requests += 1
            metrics.total_response_time += response_time
            metrics.last_request_time = datetime.now()

            if not success:
                metrics.failed_requests += 1

            # 检查阈值
            if metrics.total_requests >= 10:  # 至少10个样本才告警
                self._check_and_alert(
                    'data_source', 'failure_rate',
                    metrics.failure_rate,
                    ALERT_THRESHOLDS['data_source']['failure_rate'],
                    f"数据源{source}失败率过高: {metrics.failure_rate:.2%}",
                    'error', trace_id
                )

            if metrics.total_requests >= 5:
                self._check_and_alert(
                    'data_source', 'avg_response_time',
                    metrics.avg_response_time,
                    ALERT_THRESHOLDS['data_source']['response_time'],
                    f"数据源{source}响应时间过长: {metrics.avg_response_time:.2f}秒",
                    'warning', trace_id
                )

    def get_data_source_metrics(self, source: str = None) -> Dict:
        """获取数据源指标"""
        with self._stats_lock:
            if source:
                m = self._data_source_metrics.get(source)
                if m:
                    return {
                        'source': m.source,
                        'total_requests': m.total_requests,
                        'failed_requests': m.failed_requests,
                        'failure_rate': m.failure_rate,
                        'avg_response_time': m.avg_response_time,
                        'last_request_time': m.last_request_time.isoformat() if m.last_request_time else None,
                    }
                return {}
            else:
                return {
                    source: {
                        'total_requests': m.total_requests,
                        'failed_requests': m.failed_requests,
                        'failure_rate': m.failure_rate,
                        'avg_response_time': m.avg_response_time,
                        'last_request_time': m.last_request_time.isoformat() if m.last_request_time else None,
                    }
                    for source, m in self._data_source_metrics.items()
                }

    # ==================== 缓存监控 ====================

    def record_cache_hit(self):
        """记录缓存命中"""
        with self._stats_lock:
            self._cache_metrics.hits += 1

    def record_cache_miss(self):
        """记录缓存未命中"""
        with self._stats_lock:
            self._cache_metrics.misses += 1

    def update_cache_size(self, memory_entries: int, disk_entries: int):
        """更新缓存大小"""
        with self._stats_lock:
            self._cache_metrics.memory_entries = memory_entries
            self._cache_metrics.disk_entries = disk_entries

    def check_cache_health(self, trace_id: str = ""):
        """检查缓存健康状态"""
        with self._stats_lock:
            hit_rate = self._cache_metrics.hit_rate

        self._check_and_alert(
            'cache', 'hit_rate',
            1 - hit_rate,  # 用未命中率告警
            ALERT_THRESHOLDS['cache']['hit_rate'],
            f"缓存命中率过低: {hit_rate:.2%}",
            'warning', trace_id
        )

        return {
            'hit_rate': self._cache_metrics.hit_rate,
            'memory_entries': self._cache_metrics.memory_entries,
            'disk_entries': self._cache_metrics.disk_entries,
        }

    def get_cache_metrics(self) -> Dict:
        """获取缓存指标"""
        with self._stats_lock:
            return {
                'hits': self._cache_metrics.hits,
                'misses': self._cache_metrics.misses,
                'hit_rate': self._cache_metrics.hit_rate,
                'memory_entries': self._cache_metrics.memory_entries,
                'disk_entries': self._cache_metrics.disk_entries,
            }

    # ==================== 数据质量监控 ====================

    def record_data_quality(self, total: int, d_level: int, missing_required: int = 0):
        """记录数据质量"""
        with self._stats_lock:
            self._data_quality_metrics.total_records += total
            self._data_quality_metrics.d_level_records += d_level
            self._data_quality_metrics.missing_required_fields += missing_required

    def check_data_quality(self, trace_id: str = ""):
        """检查数据质量"""
        with self._stats_lock:
            d_level_ratio = self._data_quality_metrics.d_level_ratio

        self._check_and_alert(
            'data_quality', 'd_level_ratio',
            d_level_ratio,
            ALERT_THRESHOLDS['data_quality']['d_level_ratio'],
            f"数据D级占比过高: {d_level_ratio:.2%}",
            'error', trace_id
        )

    def get_data_quality_metrics(self) -> Dict:
        """获取数据质量指标"""
        with self._stats_lock:
            return {
                'total_records': self._data_quality_metrics.total_records,
                'd_level_records': self._data_quality_metrics.d_level_records,
                'd_level_ratio': self._data_quality_metrics.d_level_ratio,
                'missing_required_fields': self._data_quality_metrics.missing_required_fields,
                'missing_required_rate': self._data_quality_metrics.missing_required_rate,
            }

    # ==================== 性能监控 ====================

    def record_batch_operation(self, duration: float):
        """记录批量操作耗时"""
        with self._stats_lock:
            self._performance_metrics.batch_operations += 1
            self._performance_metrics.batch_total_time += duration

            self._check_and_alert(
                'performance', 'batch_time',
                duration,
                ALERT_THRESHOLDS['performance']['batch_time'],
                f"批量操作耗时过长: {duration:.2f}秒",
                'warning'
            )

    def record_single_operation(self, duration: float):
        """记录单股操作耗时"""
        with self._stats_lock:
            self._performance_metrics.single_operations += 1
            self._performance_metrics.single_total_time += duration

    def get_performance_metrics(self) -> Dict:
        """获取性能指标"""
        with self._stats_lock:
            return {
                'batch_operations': self._performance_metrics.batch_operations,
                'avg_batch_time': self._performance_metrics.avg_batch_time,
                'single_operations': self._performance_metrics.single_operations,
                'avg_single_time': self._performance_metrics.avg_single_time,
            }

    # ==================== Tushare监控 ====================

    def record_tushare_points(self, points: int, trace_id: str = ""):
        """记录Tushare积分消耗"""
        with self._stats_lock:
            # 检查日期是否需要重置
            today = date.today()
            if self._tushare_metrics.last_reset_date < today:
                self._tushare_metrics.daily_points_used = 0
                self._tushare_metrics.last_reset_date = today

            self._tushare_metrics.daily_points_used += points

            self._check_and_alert(
                'tushare', 'daily_budget',
                self._tushare_metrics.daily_usage_ratio,
                ALERT_THRESHOLDS['tushare']['daily_budget'],
                f"Tushare日积分消耗超预算: {self._tushare_metrics.daily_usage_ratio:.2%}",
                'warning', trace_id
            )

    def set_tushare_budget(self, budget: int):
        """设置Tushare每日预算"""
        with self._stats_lock:
            self._tushare_metrics.daily_budget = budget

    def get_tushare_metrics(self) -> Dict:
        """获取Tushare指标"""
        with self._stats_lock:
            return {
                'daily_points_used': self._tushare_metrics.daily_points_used,
                'daily_budget': self._tushare_metrics.daily_budget,
                'daily_usage_ratio': self._tushare_metrics.daily_usage_ratio,
                'last_reset_date': self._tushare_metrics.last_reset_date.isoformat(),
            }

    # ==================== 告警历史 ====================

    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """获取告警历史"""
        with self._lock:
            alerts = self._alert_history[-limit:]
            return [
                {
                    'timestamp': a.timestamp.isoformat(),
                    'level': a.level,
                    'category': a.category,
                    'metric': a.metric,
                    'value': a.value,
                    'threshold': a.threshold,
                    'message': a.message,
                }
                for a in alerts
            ]

    # ==================== 全部指标 ====================

    def get_all_metrics(self) -> Dict:
        """获取所有监控指标"""
        return {
            'data_source': self.get_data_source_metrics(),
            'cache': self.get_cache_metrics(),
            'data_quality': self.get_data_quality_metrics(),
            'performance': self.get_performance_metrics(),
            'tushare': self.get_tushare_metrics(),
        }

    def reset_stats(self):
        """重置统计数据（通常在每日开盘前）"""
        with self._stats_lock:
            self._data_source_metrics.clear()
            self._cache_metrics = CacheMetrics()
            self._data_quality_metrics = DataQualityMetrics()
            self._performance_metrics = PerformanceMetrics()
            self._tushare_metrics = TushareMetrics()
        self.logger.info("统计数据已重置")


# ==================== 全局单例 ====================

_monitoring_system = None


def get_monitoring_system() -> MonitoringSystem:
    """获取监控系统单例"""
    global _monitoring_system
    if _monitoring_system is None:
        _monitoring_system = MonitoringSystem()
    return _monitoring_system


# ==================== 便捷函数 ====================

def record_request(source: str, success: bool, response_time: float, trace_id: str = ""):
    """记录数据源请求"""
    get_monitoring_system().record_data_source_request(source, success, response_time, trace_id)


def record_cache_hit():
    """记录缓存命中"""
    get_monitoring_system().record_cache_hit()


def record_cache_miss():
    """记录缓存未命中"""
    get_monitoring_system().record_cache_miss()


def record_batch_time(duration: float):
    """记录批量操作耗时"""
    get_monitoring_system().record_batch_operation(duration)


def record_tushare_points(points: int, trace_id: str = ""):
    """记录Tushare积分消耗"""
    get_monitoring_system().record_tushare_points(points, trace_id)


def get_all_metrics() -> Dict:
    """获取所有监控指标"""
    return get_monitoring_system().get_all_metrics()
