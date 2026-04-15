# 数据管理模块方案 v18.5

> **v18.5更新**：补充 alerts 表到数据存储现状（cleanup.py 管理90天保留）
> **v18.4更新**：完善数据存储说明，补充历史数据填充模块、价格历史表定位、预测引擎数据来源
> **v18.3更新**：新增 `cp_history_store.py`（战力历史统一存储）；新增 `cleanup.py` 数据生命周期清理模块

## 概述

数据管理模块负责 TradeSnake 系统的所有数据访问，包括获取、缓存、清洗、持久化。

**版本**: v18.5 | **测试**: 106 个单元测试全部通过

**核心流程**: `数据获取 → 数据校验与清洗 → 数据存储`

**⚠️ 重要更新 v18.2**: 支持与 `stock_selector` 联动，实现基于股票池分层的差异化更新策略

---

## 输入输出

### 输入
| 来源 | 数据内容 |
|------|----------|
| Tushare API | 财务数据（营收、净利润、ROE等）、日线行情 |
| 腾讯行情API | 实时行情（价格、涨跌幅、成交量） |
| 东方财富 | 财务分析指标（流动比率、利息保障倍数、扣非净利润） |
| akshare | 指数成分、板块信息 |
| stock_selector | 股票池分层（core/active/observe，每日变更） |
| engine | 战力计算结果（写入cp_history） |

### 输出
| 输出内容 | 使用者 |
|----------|--------|
| 股票综合数据（行情+财务） | engine（战力计算） |
| 历史日K线数据 | engine（多日动量计算）、backtester（回测） |
| 分钟K线数据（核心池，1分钟粒度） | engine（real_time_score计算） |
| cp_history（战力历史，2年保留） | engine（读取）、recommender（读取）、backtester（读取） |
| prediction_store（预测结果，90天保留） | recommender（融合决策）、backtester（回测验证） |
| 缓存数据 | 各模块按需读取 |
| 数据更新策略订阅 | stock_selector（接收更新间隔变化通知） |

### 数据存储现状

**DuckDB (historical.duckdb)**：

| 表名 | 行数 | 状态 | 说明 |
|-----|------|------|------|
| `daily_kline` | 18,927 | 部分填充 | 日K线，**需要 SystemFiller 填充** |
| `minute_kline` | 0 | **空** | 分钟K线，**需要先填充** |

**SQLite (tradesnake.db)**：

| 表名 | 行数 | 状态 | 说明 |
|-----|------|------|------|
| `stocks` | 6,552 | 已有 | 股票列表 |
| `ex_right_factor` | **0** | **空！** | 除权因子，**紧急需要填充** |
| `cp_history` | 3,162 | 部分填充 | 战力历史，由引擎计算写入 |
| `price_history` | 11,343 | 历史遗留 | 回测器使用，**计划迁移到DuckDB** |
| `alerts` | 0 | 已有 | 告警记录，cleanup.py 管理90天保留 |

**SQLite (tradesnake_prediction.db)**：

| 表名 | 行数 | 状态 | 说明 |
|-----|------|------|------|
| `gain_predictions` | 0 | 空 | 涨幅预测，由引擎计算写入 |
| `probability_predictions` | 0 | 空 | 上涨概率，由引擎计算写入 |

> **重要**：历史数据填充详见 [DATA_FILLER_ARCHITECTURE.md](./DATA_FILLER_ARCHITECTURE.md)

> **说明**：data_manager 从 stock_selector 获取池分层（每日变更），自行制定外部数据获取的频率策略（如核心池5分钟、活跃池30分钟）。分析行为的频率由 engine 自己向 stock_selector 查询池分层后自行制定。

---

## 数据分类总结

| 分类 | 数据类型 | 更新触发 | 与池分层关系 |
|------|---------|---------|-------------|
| **1. 独立外部数据** | 实时行情、财务数据、日K线、股票列表 | 固定规则（盘后批量、盘中轮询等） | 无关 |
| **2. 关联外部数据** | 分钟K线 | 基于核心池信息 | 核心池专用 |
| **3. 引擎写入数据** | cp_history | 由 engine 触发写入，data_manager统一存储 | 无关，engine写入 |

### 各类数据说明

**1. 独立外部数据**：与池分层无关，按固定规则更新
- 实时行情：盘中轮询获取
- 财务数据：盘后批量获取
- 日K线：DuckDB 存储，2年保留
- 股票列表：akshare 获取，7天缓存

**2. 关联外部数据**：与池分层相关，只针对核心池
- 分钟K线：核心池专用，**每分钟更新**（1分钟K线粒度），DuckDB 存储，14天保留

**3. 引擎写入数据**：由 engine 触发写入
- cp_history：engine 计算完成后写入，SQLite 存储，2年保留
- prediction_store：涨幅/概率预测结果写入，SQLite 存储，90天保留（v19.8新增）

### data_manager 职责边界

```
data_manager
    │
    ├── 获取外部数据
    │   ├── 独立数据（固定规则）→ 缓存/DuckDB
    │   └── 关联数据（根据核心池）→ DuckDB分钟K线
    │
    └── 清理过期数据（生命周期管理）
        ├── cp_history 清理
        ├── prediction_store 清理（v19.8新增）
        ├── DuckDB 清理（日K线、分钟K线）
        └── JSON缓存清理
```

---

## 一、模块结构

```
backend/data_manager/
├── __init__.py              # 统一导出 (191个公开接口)
├── manager.py              # 统一数据管理器（单一入口）
├── fetcher.py              # 综合数据获取器
├── cache.py                # 统一缓存管理
├── cleaner.py              # 数据清洗器
├── circuit_breaker.py       # 熔断与限流
├── batcher.py              # 异步批量获取
├── adjuster.py             # 复权因子管理
├── monitor.py              # 监控告警系统
├── backup.py               # 数据备份
├── cleanup.py              # 数据生命周期清理 🆕
├── duckdb_store.py         # DuckDB历史K线存储
├── cp_history_store.py     # 战力历史存储（SQLite WAL模式，v19.7新增）
├── prediction_store.py     # 预测结果存储（SQLite，v19.8新增）🆕
├── update_scheduler.py     # ⚠️ 基于池分层的更新调度器（依赖stock_selector的UpdateStrategyProvider）
├── providers/              # 数据源提供者
│   ├── base.py           # BaseDataProvider 抽象基类
│   └── tushare.py        # Tushare Pro API 实现
└── tests/                # 单元测试 (8个测试文件)
    ├── test_adjuster.py
    ├── test_backup.py
    ├── test_batcher.py
    ├── test_circuit_breaker.py
    ├── test_cleaner.py
    ├── test_duckdb_store.py
    ├── test_monitor.py
    └── test_tushare_provider.py
```

---

## 二、核心组件详解

### 2.1 DataManager（统一入口）

**文件**: `manager.py`

**职责**: 单一数据访问入口，统一管理所有数据获取、缓存、验证。

**主要接口**:
```python
from data_manager.manager import get_data_manager

dm = get_data_manager()

# 股票数据
dm.get_stock_data(limit=200)           # 获取完整股票数据
dm.get_single_stock(code)              # 获取单只股票

# 行情数据
dm.get_market_data(codes)              # 实时行情
dm.get_history_price(code, days=30)    # 历史价格

# 财务数据
dm.get_financial_data(code)            # 财务数据
dm.get_stock_list()                    # 股票列表

# Tushare数据
dm.get_tushare_data(code, 'daily')     # Tushare K线
dm.sync_klines_to_duckdb(codes, days)  # 同步到DuckDB
```

### 2.2 Fetcher（数据获取器）

**文件**: `fetcher.py`

**组件**:
| 类 | 职责 | 数据源 |
|---|---|---|
| `StockListFetcher` | 股票列表 | akshare |
| `MarketDataFetcher` | 实时行情 | 腾讯/新浪 |
| `FinancialDataFetcher` | 财务数据 | 东方财富/baostock/akshare |
| `StockDataFetcher` | 综合获取器 | 组合以上 |

**便捷函数**:
```python
from data_manager.fetcher import (
    get_stock_data_api,          # 获取股票数据
    get_single_stock_data,       # 获取单只股票
    sync_klines_from_tushare,    # Tushare→DuckDB同步
    get_klines_from_duckdb,      # 从DuckDB读取K线
)
```

### 2.3 Cache（统一缓存）

**文件**: `cache.py`

**特性**:
- 内存LRU缓存（500项，30秒TTL）
- 磁盘JSON持久化
- TTL自动过期
- 原子写入保证一致性

**数据分类TTL**:
| 类型 | TTL | 说明 |
|---|---|---|
| realtime | 5分钟 | 实时行情 |
| financial | 24小时 | 财务数据 |
| daily | 1天 | 每日行情 |
| history | 永久 | 历史数据 |
| static | 7天 | 静态数据 |

### 2.4 Cleaner（数据清洗器）

**文件**: `cleaner.py`

**8步清洗流程**:
1. 格式标准化
2. 缺失值检测与填充
3. 异常值检测与标记
4. 数据类型转换
5. 数值范围校验
6. 交叉字段一致性检查
7. 数据质量评分（A/B/C/D级）
8. 输出格式适配

### 2.5 Circuit Breaker（熔断限流）

**文件**: `circuit_breaker.py`

**组件**:
| 类 | 功能 |
|---|---|
| `CircuitBreaker` | 熔断器（连续失败N次后暂停） |
| `RateLimiter` | 令牌桶限流器 |
| `AdaptiveLimiter` | 自适应限流（动态调整并发） |
| `TushareBudget` | Tushare积分预算管理 |
| `DataSourceCircuitManager` | 统一熔断管理 |

**熔断状态**: CLOSED → OPEN → HALF_OPEN → CLOSED

### 2.6 Batcher（异步批量）

**文件**: `batcher.py`

**功能**:
- ThreadPoolExecutor并发执行
- 批量获取市场/财务数据
- 自适应并发控制
- 错误收集与统计

```python
from data_manager.batcher import get_batcher

batcher = get_batcher()
result = batcher.batch_get_financial(codes, fetch_func)
```

### 2.7 Adjuster（复权因子管理）

**文件**: `adjuster.py`

**功能**:
- 复权因子获取与管理
- 前复权/后复权价格计算
- 除权事件检测

### 2.8 Monitor（监控告警）

**文件**: `monitor.py`

**监控指标**:
- 数据源请求（成功/失败/响应时间）
- 缓存命中率
- Tushare积分消耗
- 批量操作耗时
- 失败率告警

### 2.9 Backup（数据备份）

**文件**: `backup.py`

**功能**:
- SQLite数据库备份
- 缓存文件备份
- 自动清理旧备份
- 定时备份调度

### 2.10 DuckDB Store（历史K线）

**文件**: `duckdb_store.py`

**功能**:
- 历史K线持久化存储
- 高效OLAP查询
- 均线计算（日线/分钟线）
- 成交量历史
- 分钟K线存储与查询（v19.6，用于real_time_score）

```python
from data_manager.duckdb_store import get_duckdb_store

store = get_duckdb_store()

# 日K线
result = store.get_klines('000001', start_date='20240101', limit=30)
ma5 = store.get_ma('000001', days=5)

# 分钟K线（v19.6）
minute_klines = store.get_minute_klines('000001', days=1, limit=500)
minute_ma5 = store.get_minute_ma('000001', minutes=5, days=1)
```

### 2.11 Cleanup（数据生命周期清理）🆕

**文件**: `cleanup.py`

**功能**:
- SQLite数据清理（cp_history保留2年，price_history保留2年，alerts保留90天）
- DuckDB K线清理（日K线保留2年，分钟K线保留14天）
- JSON缓存清理（基于TTL，用户配置文件跳过）
- 周K归档（超过2年的日K线降采样为周K）
- 清理前核心数据校验
- 幂等性保护（防止重复清理）
- 审计日志记录

**保留策略**:

| 数据类型 | 存储位置 | 保留期 |
|---------|---------|-------|
| 战力历史 | SQLite | 2年 |
| 预测结果 | SQLite | 90天 |
| 日K线 | DuckDB | 2年 |
| 分钟K线 | DuckDB | 14天 |
| 财务缓存 | JSON | 7天 |
| 行情缓存 | JSON | 1天 |

```python
from data_manager import LifecycleCleanupScheduler, check_storage_water_level

# 执行每日清理
scheduler = LifecycleCleanupScheduler()
results = scheduler.daily_cleanup()

# 检查存储水位
storage = check_storage_water_level()
print(f"使用率: {storage['usage_percent']}%")
```

### 2.11 Providers（数据源提供者）

**目录**: `providers/`

```
providers/
├── base.py      # BaseDataProvider 抽象基类
└── tushare.py   # Tushare Pro API 实现
```

#### TushareProvider

**Token**: `0c754ce86eb55d62047cb390339cb33231e57fda7c8093b146264ce0`

| 方法 | 说明 | 积分/次 |
|---|---|---|
| `get_stock_list()` | 股票列表(5497只) | 0 |
| `get_daily_kline(code, start, end)` | 日K线 | 5 |
| `get_weekly_kline(code, start, end)` | 周K线 | 5 |
| `get_monthly_kline(code, start, end)` | 月K线 | 5 |
| `get_market_data(codes)` | 每日指标(PE/PB等) | 100 |
| `get_financial_data(code)` | 财务数据 | 300 |
| `get_income_statement(code)` | 利润表 | 300 |
| `get_balance_sheet(code)` | 资产负债表 | 300 |
| `get_cash_flow(code)` | 现金流量表 | 300 |

**使用示例**:
```python
from data_manager.providers import get_tushare_provider

provider = get_tushare_provider()
stock_list = provider.get_stock_list()  # 5497只
klines = provider.get_daily_kline('000001', '20240101', '20240301')
```

---

## 三、数据流

### 3.1 实时行情获取

```
请求 → DataManager.get_market_data()
         ↓
    CacheManager (检查缓存)
         ↓
    MarketDataFetcher
         ↓
    腾讯API ──失败──→ 新浪API
         ↓
    DataCleaner (清洗校验)
         ↓
    CacheManager (写入缓存)
         ↓
    返回数据
```

### 3.2 财务数据获取

```
请求 → DataManager.get_financial_data()
         ↓
    CacheManager (检查缓存)
         ↓
    FinancialDataFetcher
         ↓
    东方财富API ──失败──→ BaostockAPI ──失败──→ AkShareAPI
         ↓
    DataCleaner (清洗校验)
         ↓
    CacheManager (写入缓存)
         ↓
    返回数据
```

### 3.3 Tushare K线同步到DuckDB

```
请求 → DataManager.sync_klines_to_duckdb()
              或 fetcher.sync_klines_from_tushare()
         ↓
    TushareProvider.get_daily_kline()
         ↓
    DuckDBStore.insert_daily_klines_batch()
         ↓
    存储完成
```

### 3.4 回测数据读取

```
回测请求 → DataManager.get_history_price()
              或 fetcher.get_klines_from_duckdb()
         ↓
    DuckDBStore.get_klines()
         ↓
    返回K线数据 → 回测引擎
```

### 3.5 ⚠️ 与 stock_selector 联动（基于池分层的更新策略）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    双向数据流：data_manager ↔ stock_selector              │
│                                                                      │
│  stock_selector              data_manager                               │
│       │                         │                                      │
│       │  维护池状态             │  根据池状态决定更新频率               │
│       │  (core/active/observe) │                                      │
│       │                         │                                      │
│       │  ┌─────────────────┐   │   ┌─────────────────────────────┐   │
│       └─▶│ 通知更新频率策略  │──▶│   │  核心池 (~300只)            │   │
│           └─────────────────┘   │   │  高频更新：5-15分钟         │   │
│                                 │   ├─────────────────────────────┤   │
│                                 │   │  活跃池 (~500只)            │   │
│                                 │   │  中频更新：30-60分钟        │   │
│                                 │   ├─────────────────────────────┤   │
│                                 │   │  观察池 (~1000只)           │   │
│                                 │   │  低频更新：每日/每周        │   │
│                                 │   └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 更新频率配置

| 池 | 数量 | 盘中更新间隔 | 盘前更新间隔 |
|----|------|-------------|-------------|
| **核心池** | ~300只 | 5分钟 | 15分钟 |
| **活跃池** | ~500只 | 30分钟 | 60分钟 |
| **观察池** | ~1000只 | 不更新 | 不更新 |

#### UpdateScheduler（更新调度器）

**文件**: `update_scheduler.py`

**职责说明**：
- **策略定义**（`stock_selector/update_strategy.py`）：由 stock_selector 提供池分层更新频率策略
- **策略执行**（`data_manager/update_scheduler.py`）：调度器根据策略执行具体更新任务

```python
class UpdateScheduler:
    """⚠️ 基于股票池分层的更新调度器

    订阅 stock_selector 的池状态变化，
    根据各池优先级调度 data_manager 的更新任务
    """

    def __init__(self, data_manager, update_strategy_provider):
        self.dm = data_manager
        self.strategy = update_strategy_provider
        self.last_update_time: Dict[str, float] = {}

    def trading_day_update(self):
        """盘中按优先级更新"""
        priority_codes = self.strategy.get_batch_priority()

        for code in priority_codes:
            tier = self.strategy.get_stock_tier(code)
            interval = self.strategy.get_update_interval(tier, "trading")

            if interval > 0 and self._should_update(code, interval):
                self.dm.update_single_stock(code)
                self.last_update_time[code] = time.time()

            time.sleep(0.1)  # 避免请求过快

    def _should_update(self, code: str, interval: int) -> bool:
        """检查是否需要更新"""
        last = self.last_update_time.get(code, 0)
        return (time.time() - last) >= interval
```

#### 订阅 stock_selector 回调

```python
class StockSelectorCallback:
    """接收 stock_selector 的池状态变化通知"""

    def on_pool_update_strategy_changed(
        self, tier: PoolTier, action: str, new_codes: List[str]
    ):
        """池变化时更新调度策略"""
        if action == "upgrade":
            # 晋级的股票提高更新频率
            for code in new_codes:
                self.scheduler.set_priority(code, tier)
        elif action == "downgrade":
            # 降级的股票降低更新频率
            for code in new_codes:
                self.scheduler.set_priority(code, tier)
```

---

## 四、便捷函数

### 4.1 快速获取股票数据

```python
from data_manager import get_stock_data_api, get_single_stock_data

# 获取多只股票数据
stocks = get_stock_data_api(limit=100)

# 获取单只股票
stock = get_single_stock_data('000001')
```

### 4.2 Tushare数据

```python
from data_manager import get_tushare_provider

provider = get_tushare_provider()
klines = provider.get_daily_kline('000001', '20240101', '20240301')
```

### 4.3 DuckDB历史数据

```python
from data_manager import get_klines, get_latest_kline, get_ma
from data_manager import get_minute_klines, get_minute_ma

# 获取K线
klines = get_klines('000001', limit=30)

# 最新K线
latest = get_latest_kline('000001')

# 计算均线
ma5 = get_ma('000001', days=5)

# 获取分钟K线（v19.6，用于real_time_score计算）
minute_klines = get_minute_klines('000001', days=1, limit=500)

# 计算分钟级均线（v19.6）
minute_ma5 = get_minute_ma('000001', minutes=5, days=1)
```

### 4.4 监控指标

```python
from data_manager import get_monitoring_system, get_all_metrics

monitor = get_monitoring_system()
metrics = get_all_metrics()

# 记录请求
from data_manager import record_request, record_cache_hit, record_tushare_points
record_request('tushare', success=True, response_time=0.5)
record_cache_hit()
record_tushare_points(10)
```

---

## 五、数据分类

| 类型 | TTL | 存储 | 说明 |
|---|---|---|---|
| realtime | 5分钟 | 内存+磁盘 | 实时行情 |
| financial | 24小时 | 内存+磁盘 | 财务数据 |
| daily | 1天 | 磁盘 | 每日行情 |
| history | 永久 | DuckDB | 历史K线 |
| static | 7天 | 内存+磁盘 | 静态配置 |

---

## 六、测试覆盖

| 测试文件 | 测试数 | 内容 |
|---|---|---|
| test_adjuster.py | 15 | 复权因子测试 |
| test_backup.py | 11 | 备份功能测试 |
| test_batcher.py | 11 | 批量获取测试 |
| test_circuit_breaker.py | 20 | 熔断限流测试 |
| test_cleaner.py | 6 | 数据清洗测试 |
| test_duckdb_store.py | 12 | DuckDB存储测试 |
| test_monitor.py | 16 | 监控告警测试 |
| test_tushare_provider.py | 12 | Tushare测试 |

**总计**: 106 个测试，全部通过

---

## 七、已实现功能清单

| 模块 | 功能 | 状态 |
|---|---|---|
| **manager** | 统一数据入口 | ✅ |
| **fetcher** | 多数据源获取 | ✅ |
| **cache** | 统一缓存(内存LRU+磁盘JSON) | ✅ |
| **cleaner** | 8步数据清洗 | ✅ |
| **circuit_breaker** | 熔断+限流+积分预算 | ✅ |
| **batcher** | 异步批量获取 | ✅ |
| **adjuster** | 复权因子管理 | ✅ |
| **monitor** | 监控告警体系 | ✅ |
| **backup** | 数据备份 | ✅ |
| **cleanup** | 数据生命周期清理 | ✅ |
| **duckdb_store** | 历史K线存储 | ✅ |
| **providers/tushare** | Tushare API | ✅ |

---

## 八、数据源问题排查 (v1.0)

> 记录实际遇到的数据源获取问题及解决方案

### 8.1 东方财富API不稳定

**问题描述:**
```
获取市值排名失败: HTTPSConnectionPool(host='82.push2.eastmoney.com', port=443):
Max retries exceeded with url: /api/qt/clist/get?...
(Caused by ProxyError('Unable to connect to proxy', RemoteDisconnected(...)))
```

**根本原因:**
1. 东方财富行情API域名有多个CDN节点（如 `push2.eastmoney.com`、`82.push2.eastmoney.com`）
2. 部分CDN节点通过代理访问时存在SSL兼容性问题（`unexpected eof while reading`）
3. 直连无法访问（需要代理）

**影响范围:**
- `StockListFetcher.get_market_cap_leaders()` - 获取成交额排名
- `akshare.stock_zh_a_spot_em()` - akshare东方财富实时行情

**当前处理:**
- `fetcher.py` 中 `get_market_cap_leaders()` 已添加3次重试 + 2/4秒指数退避
- 失败时返回空列表，背景刷新降级为随机抽样模式

**代理配置:**
```python
# 优先使用环境变量，否则用默认值
_PROXY = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY') or 'http://192.168.13.218:10808'
os.environ['http_proxy'] = _PROXY
os.environ['https_proxy'] = _PROXY
```

**相关文件:**
- `backend/data_manager/providers/tushare.py` - 代理配置
- `backend/data/tushare_provider.py` - 代理配置
- `backend/data/data_provider.py` - 代理配置
- `backend/data/data_enhancer.py` - 代理配置
- `backend/data_manager/fetcher.py` - 重试逻辑

### 8.2 Baostock连接频繁login/logout

**问题描述:**
1500只股票刷新时，日志中产生大量 `login success! / logout success!` 输出（3000+次），拖慢整体刷新速度（50+分钟）。

**根本原因:**
`_fetch_from_baostock()` 对每只股票执行独立的 `bs.login()` → `query_xxx()` → `bs.logout()` 对。

**解决方案:**
- 新增 `BaoStockSession` 类：封装单次会话，支持自动重连
- 新增 `BaoStockPool` 类：5连接池，每连接最大复用500次
- 改用单例 `get_financial_fetcher()` 确保连接池复用

**效果:**
- 1500只股票：3000+次 login/logout → **仅5次**
- 日志输出大幅减少
- 刷新时间显著缩短

**相关文件:**
- `backend/data_manager/fetcher.py` - `BaoStockSession`、`BaoStockPool` 类

### 8.3 SQLite数据库损坏

**问题描述:**
```
sqlite3.OperationalError: database disk image is malformed
```

**根本原因:**
数据库文件在写入过程中被中断（如进程崩溃、磁盘满）。

**解决方案:**
```bash
# 1. 备份损坏的数据库
cp tradesnake.db tradesnake.db.corrupted

# 2. 使用.recover提取数据
sqlite3 tradesnake.db ".recover" > /tmp/tradesnake_recover.sql

# 3. 重建数据库
sqlite3 tradesnake_new.db < /tmp/tradesnake_recover.sql

# 4. 替换损坏的数据库
mv tradesnake_new.db tradesnake.db
```

**预防措施:**
- 所有SQLite数据库使用 **WAL模式**（`PRAGMA journal_mode=WAL`）
- 定期执行 `VACUUM` 清理碎片

### 8.4 cp_engine启动时为空

**问题描述:**
服务启动后，`cp_engine.stocks` 为空，需要等待8分钟背景刷新完成。

**根本原因:**
`preload_cp_engine_from_cache()` 加载2855个JSON文件太慢被禁用，背景刷新需串行获取1500只股票财务数据。

**解决方案:**
- 新增 `StockCP.from_precalculated()` 方法：从预计算分数创建StockCP，跳过 `calculate_scores()`
- 新增 `preload_cp_engine_from_history()` 从SQLite cp_history快速加载（<1秒）
- 启动时加载300只股票的预计算CP分数

**效果:**
- 启动时间：数分钟 → **<1秒**
- API立即返回300只股票

**相关文件:**
- `backend/engine/cp_engine/cp_engine.py` - `StockCP.from_precalculated()`
- `backend/api/main.py` - `preload_cp_engine_from_history()`

### 8.5 数据源可用性矩阵

| 数据源 | 用途 | 稳定性 | 依赖 | 失败降级 |
|--------|------|--------|------|----------|
| 东方财富(akshare) | 成交额排名 | ⚠️ 不稳定 | 代理 | 随机抽样 |
| 腾讯行情API | 实时行情 | ✅ 稳定 | 无 | 返回空 |
| baostock | 财务数据 | ✅ 稳定 | 无 | 返回空 |
| Tushare Pro | K线/财务 | ✅ 稳定 | 代理/积分 | 返回空 |
| 新浪行情API | 备用实时行情 | ⚠️ 不稳定 | 无 | 返回空 |

---

## 九、版本历史

| 版本 | 日期 | 更新 |
|---|---|---|
| v18.6 | 2026-04-15 | 新增"数据源问题排查"章节：东方财富API不稳定、Baostock连接池、SQLite损坏、cp_engine预加载 |
| v18.5 | 2026-04-09 | 补充 alerts 表到数据存储现状（cleanup.py 管理90天保留） |
| v18.4 | 2026-04-09 | 完善数据存储说明，补充历史数据填充模块、价格历史表定位、预测引擎数据来源 |
| v18.3 | 2026-04-08 | 新增 `cp_history_store.py`（战力历史统一存储）；新增 `cleanup.py` 数据生命周期清理模块（Phase 1 + Phase 2） |
| v18.2 | 2026-04-07 | 新增 `UpdateScheduler`，支持与 stock_selector 联动实现分层更新策略 |
| v18.1.6 | 2026-04-06 | Tushare Provider 集成完成 |
| v18.1.5 | 2026-04-06 | 统一缓存设计 |
| v18.1.4 | 2026-04-06 | 数据校验与清洗模块 |
| v18.1.3 | 2026-04-06 | 评审意见整改 |
| v18.1.2 | 2026-04-06 | 异步批量、复权因子、监控告警 |
| v18.1.1 | 2026-04-06 | 数据重复处理、一致性保障 |
| v18.1 | 2026-04-05 | 初始版本 |

---

## 十、相关文档

- [项目概览](./PROJECT_OVERVIEW.md) - 项目整体介绍
- [实施方案](../references/) - 外部参考资料
