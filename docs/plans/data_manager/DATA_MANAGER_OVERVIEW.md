# 数据管理模块方案 v18.5

> **v18.5更新**：补充 alerts 表到数据存储现状（cleanup.py 管理90天保留）
> **v18.4更新**：完善数据存储说明，补充历史数据填充模块、价格历史表定位、预测引擎数据来源
> **v18.3更新**：新增 `cp_history_store.py`（战力历史统一存储）；新增 `cleanup.py` 数据生命周期清理模块

---

## 概述

数据管理模块负责 TradeSnake 系统的所有数据访问，包括获取、缓存、清洗、持久化。

**产品范围（与 `PROJECT_OVERVIEW` 一致）**：批量实时行情抽样（如 `StockDataFetcher.get_batch_market_data`）以 **沪深主板** 为边界，不含创业板、科创板、北交所；全市场股票列表、指数成分等仍可获取，用于列表或标志位，**不等于**对上述非主板标的按主板主流程承担同等批量行情义务。

**版本**: v19.9.9 | **测试**: 106 个单元测试全部通过

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
| `daily_kline` | 2,440,666 | ✅ 已填充 | 日K线，2024-04-10~2026-04-13，每日~5000只 |
| `minute_kline` | 2,393,152 | ⚠️ 覆盖不足 | 分钟K线，仅4天数据（应保留14天） |
| `trade_cal` | **0** | ❌ 为空 | 交易日历，需要调用 `TradeCalendar.fetch_from_tushare()` 填充 |

**SQLite (tradesnake.db)**：

| 表名 | 行数 | 状态 | 说明 |
|-----|------|------|------|
| `stocks` | 3,432 | ⚠️ 部分缺失 | 股票列表，PE有效78%，ROE有效47%，sector缺失32% |
| `ex_right_factor` | 5,346,230 | ✅ 已填充 | 除权因子 |
| `cp_history` | 36,370 | ✅ 已填充 | 战力历史，由引擎计算写入 |
| `price_history` | 11,343 | 历史遗留 | 回测器使用，**计划迁移到DuckDB** |
| `alerts` | 0 | 已有 | 告警记录，cleanup.py 管理90天保留 |

**SQLite (tradesnake_prediction.db)**：

| 表名 | 行数 | 状态 | 说明 |
|-----|------|------|------|
| `gain_predictions` | 32,568 | ✅ 已填充 | 涨幅预测 |
| `probability_predictions` | 32,568 | ✅ 已填充 | 上涨概率 |

**数据初始化命令**：

```bash
# 填充交易日历（Tushare需要积分权限）
cd backend && python -m data_manager.filler trade_cal fetch

# 补充分钟K线数据（14天）
cd backend && python -m data_manager.filler minute_klines fill

# 批量更新财务数据（PE/ROE等）
curl -X POST http://localhost:8001/api/refresh/financials
```

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

### 2.12 Providers（数据源提供者）

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
