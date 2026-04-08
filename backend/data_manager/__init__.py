"""
数据管理模块 - Data Manager v18.1.6
====================================
职责：数据获取、缓存、清洗、持久化

核心流程：数据获取 → 数据校验与清洗 → 数据存储

子模块：
- manager: 统一数据管理器（单一数据入口）
- fetcher: 综合数据获取器
- cache: 统一缓存（内存LRU + 磁盘JSON，原子写入）
- cleaner: 数据清洗器（8步清洗流程）
- circuit_breaker: 熔断与限流保护
- batcher: 异步批量获取
- adjuster: 复权因子管理
- monitor: 监控告警系统
- backup: 数据备份
- duckdb_store: DuckDB历史K线存储
- providers: 数据源提供者（Tushare）

数据分类：
- realtime: 实时行情 (5分钟TTL)
- financial: 财务数据 (24小时TTL)
- daily: 每日行情 (1天TTL)
- history: 历史数据 (永久)
- static: 静态数据 (7天TTL)

架构文档: ../BACKEND_ARCHITECTURE.md
"""

# 兼容旧接口
from .fetcher import StockDataFetcher, get_stock_data_api, get_single_stock_data
from .cache import CacheManager, get_cache_manager

# 新统一接口
from .manager import (
    DataManager,
    get_data_manager,
    get_market_data,
    get_financial_data,
    get_stock_list,
    get_tushare_data,
    UnifiedCache,
)

# 新增模块
from .cleaner import DataCleaner, get_cleaner, clean_data
from .circuit_breaker import (
    CircuitBreaker,
    RateLimiter,
    AdaptiveLimiter,
    DataSourceCircuitManager,
    get_circuit_manager,
    CircuitOpenError,
    RateLimitExceededError,
)
from .batcher import (
    AsyncBatcher,
    BatchResult,
    get_batcher,
    get_adaptive_concurrency,
)
from .adjuster import (
    AdjustmentManager,
    AdjustmentFactor,
    ExRightEvent,
    get_adjuster,
    get_adjusted_price,
    adjust_price_series,
)
from .monitor import (
    MonitoringSystem,
    Alert,
    AlertHandler,
    LogAlertHandler,
    CallbackAlertHandler,
    get_monitoring_system,
    record_request,
    record_cache_hit,
    record_cache_miss,
    record_batch_time,
    record_tushare_points,
    get_all_metrics,
)
from .backup import (
    BackupManager,
    BackupResult,
    CleanupResult,
    BackupScheduler,
    get_backup_manager,
    backup_sqlite,
    backup_cache,
    backup_all,
    cleanup_old_backups,
    get_backup_status,
)
from .duckdb_store import (
    DuckDBStore,
    KlineRecord,
    QueryResult,
    HistoryMigrator,
    get_duckdb_store,
    get_klines,
    get_latest_kline,
    insert_kline,
    get_ma,
    get_minute_klines,
    get_minute_ma,
)

# 数据源提供者
from .providers import (
    BaseDataProvider,
    ProviderConfig,
    TushareProvider,
    get_tushare_provider,
    INTERFACE_COSTS,
)

# 数据生命周期清理
from .cleanup import (
    LifecycleCleanupScheduler,
    SQLiteCleaner,
    SQLiteVacuumCleaner,
    DuckDBCleaner,
    CacheCleaner,
    CleanupState,
    CleanupAuditor,
    CleanupValidator,
    CPHistoryColdHotSeparator,
    check_storage_water_level,
    generate_cleanup_report,
    SQLITE_RETENTION,
    DUCKDB_RETENTION,
    CACHE_RETENTION,
)

__all__ = [
    # 兼容旧接口
    'StockDataFetcher',
    'get_stock_data_api',
    'get_single_stock_data',
    'CacheManager',
    'get_cache_manager',
    # 新统一接口
    'DataManager',
    'get_data_manager',
    'get_market_data',
    'get_financial_data',
    'get_stock_list',
    'get_tushare_data',
    'UnifiedCache',
    # 数据清洗
    'DataCleaner',
    'get_cleaner',
    'clean_data',
    # 熔断限流
    'CircuitBreaker',
    'RateLimiter',
    'AdaptiveLimiter',
    'DataSourceCircuitManager',
    'get_circuit_manager',
    'CircuitOpenError',
    'RateLimitExceededError',
    # 异步批量
    'AsyncBatcher',
    'BatchResult',
    'get_batcher',
    'get_adaptive_concurrency',
    # 复权因子
    'AdjustmentManager',
    'AdjustmentFactor',
    'ExRightEvent',
    'get_adjuster',
    'get_adjusted_price',
    'adjust_price_series',
    # 监控告警
    'MonitoringSystem',
    'Alert',
    'AlertHandler',
    'LogAlertHandler',
    'CallbackAlertHandler',
    'get_monitoring_system',
    'record_request',
    'record_cache_hit',
    'record_cache_miss',
    'record_batch_time',
    'record_tushare_points',
    'get_all_metrics',
    # 数据备份
    'BackupManager',
    'BackupResult',
    'CleanupResult',
    'BackupScheduler',
    'get_backup_manager',
    'backup_sqlite',
    'backup_cache',
    'backup_all',
    'cleanup_old_backups',
    'get_backup_status',
    # DuckDB历史存储
    'DuckDBStore',
    'KlineRecord',
    'QueryResult',
    'HistoryMigrator',
    'get_duckdb_store',
    'get_klines',
    'get_latest_kline',
    'insert_kline',
    'get_ma',
    'get_minute_klines',
    'get_minute_ma',
    # 数据源提供者
    'BaseDataProvider',
    'ProviderConfig',
    'TushareProvider',
    'get_tushare_provider',
    'INTERFACE_COSTS',
    # 数据生命周期清理
    'LifecycleCleanupScheduler',
    'SQLiteCleaner',
    'SQLiteVacuumCleaner',
    'DuckDBCleaner',
    'CacheCleaner',
    'CleanupState',
    'CleanupAuditor',
    'CleanupValidator',
    'CPHistoryColdHotSeparator',
    'check_storage_water_level',
    'generate_cleanup_report',
    'SQLITE_RETENTION',
    'DUCKDB_RETENTION',
    'CACHE_RETENTION',
]
