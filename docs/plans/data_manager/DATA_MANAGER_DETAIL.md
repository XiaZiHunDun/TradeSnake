# 数据管理模块方案 - 详细设计

> 本文档是数据管理模块的详细设计部分，对应 `DATA_MANAGER_OVERVIEW.md` 的后续内容。

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
| **观察池** | ~1000只 | 不更新 | 日频（盘后） |

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

`StockSelectorCallback`（`update_scheduler.py`）**实现 `stock_selector.SelectorCallback` 协议**，与 `register_callback` 一致；池变化时维护 `UpdateScheduler.last_update_time`（新入池置 0 以优先更新，移除则 `pop`）。

```python
class StockSelectorCallback:
    """实现 SelectorCallback，将池变动映射到 UpdateScheduler"""

    def on_pool_changed(self, tier, added: List[str], removed: List[str]) -> None:
        for code in added:
            self.scheduler.last_update_time[code] = 0
        for code in removed:
            self.scheduler.last_update_time.pop(code, None)

    def on_stock_upgraded(self, code: str, from_tier, to_tier) -> None:
        self.scheduler.last_update_time.pop(code, None)

    def on_stock_downgraded(self, code: str, from_tier, to_tier) -> None:
        pass

    # on_event_triggered / on_financial_warning：当前为空实现，占位协议
```

另：`on_pool_update_strategy_changed(tier, action, new_codes)` 仍保留在类上供扩展，**不由** `StockSelector` 标准路径调用。

**触发时机（与 stock_selector 对齐，2026-04-15）**：`StockSelector.initialize` 结束、`refresh_pools` 再平衡之后、财务降级路径会调用 `on_pool_changed`；`background_refresh_task` 在策略可用时会顺带调用 `trading_day_update` 小批量更新。

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
- 新增 `preload_cp_engine_from_history()`：从 SQLite **`stocks` 表**（完整财务字段）快速加载（<1秒）；**默认仅加载 `StockSelector.get_all_analysable_codes()`（核心池+活跃池）** 在表中的行，与战力计算范围一致；若无交集则回退为按 `total_cp` 取前 300 只
- 启动前用 `stock_selector/market_snapshot.py` + `StockDataFetcher.get_batch_market_data` 构建 `market_data`，再 `initialize`（避免对全市场逐只拉财务导致启动过慢）

**效果:**
- 启动时间：数分钟 → **秒级**（视 batch 行情请求而定）
- API 启动即有与池一致的预加载集合（通常少于 300 时以池为准）

**相关文件:**
- `backend/engine/cp_engine/cp_engine.py` - `StockCP.from_precalculated()`
- `backend/api/main.py` - `preload_cp_engine_from_history(allowed_codes=...)`
- `backend/stock_selector/market_snapshot.py` - 启动/再平衡用 `market_data` 构建
- `backend/data_manager/duckdb_store.py` - `get_avg_daily_amount_20d_bulk`（日均成交额批量查询，供 snapshot 使用）

### 8.5 数据源网络特性与可用性矩阵（v19.9.8）

#### 网络特性说明

| 数据源 | 域名/接口 | 需要代理 | 直连测试 | 说明 |
|--------|----------|---------|---------|------|
| **腾讯行情API** | `qt.gtimg.cn` | ❌ 不需要 | ✅ 正常 | 实时行情主力，响应快（<500ms） |
| **东方财富行情** | `datacenter-web.eastmoney.com` | ❌ 不需要 | ✅ 正常 | 财务数据来源 |
| **akshare `stock_zh_a_spot_em`** | eastmoney CDN | ❌ 不需要 | ⚠️ 不稳定 | 获取58页数据，连接常被拒，需30秒超时保护 |
| **新浪行情API** | `hq.sinajs.cn` | ❌ 不需要 | ✅ 正常 | 备用实时行情 |
| **baostock** | `api.baostock.com` | ❌ 不需要（主路径已移除） | N/A | v19.9.8前：子进程5秒超时备用；主路径已完全移除调用 |
| **Tushare Pro** | `api.tushare.pro` | ❌ **不需要**（SDK已禁用代理） | ⚠️ 部分可用 | 财务/K线，有积分限制（2000积分）；v19.9.6起SDK内部禁用代理 |

#### 各数据源使用情况

| 数据源 | 使用场景 | 超时/保护机制 | 降级策略 |
|--------|---------|-------------|----------|
| 腾讯行情API | 实时行情（主力） | 10秒，3次重试 | → 新浪行情API |
| 东方财富财务API | ROE/增长率（主力） | 10秒，3次重试 | → akshare补充字段 |
| akshare `stock_zh_a_spot_em` | 成交额排名（`get_market_cap_leaders`） | **子进程30秒硬超时**（v19.9.8新增） | → 随机抽样 |
| baostock | ~~财务数据~~ | 已移除调用（v19.9.8） | 依赖 eastmoney + akshare + tushare fallback |
| Tushare | revenue补充（fallback） | SDK内部 | revenue为0时补充 |
| akshare `stock_financial_analysis_indicator` | 流动比率/利息保障倍数 | 无超时，约0.7秒 | 失败则跳过 |

#### 数据获取流程（v19.9.8优化后）

```
get_stock_data_api(limit=1500)
  └─ get_market_cap_leaders()
       └─ akshare.stock_zh_a_spot_em()  ← 子进程30秒超时保护
  └─ get_batch_market_data()
       └─ MarketDataFetcher → 腾讯API（主力）→ 新浪API（备用）
  └─ 循环获取财务数据
       └─ FinancialDataFetcher.get_financial_data()
            ├─ eastmoney（主力，快速）
            ├─ akshare补充字段（流动比率等）
            └─ Tushare revenue fallback（仅当revenue=0时）
```

> ⚠️ **注意**：代理设置为 `http://192.168.13.218:10808` 时，baostock.com 返回502，腾讯/东方财富直连正常。

### 8.6 版本历史补充

| 版本 | 日期 | 更新 |
|------|------|------|
| v19.9.8 | 2026-04-23 | 修复数据刷新挂起问题：1）`get_market_cap_leaders` 加子进程30秒超时；2）移除每股票调用baostock（5秒超时×N只太慢），改为纯eastmoney+akshare+tushare；baostock改为子进程调用（5秒超时）仅作备用 |

---

## 九、版本历史

| 版本 | 日期 | 更新 |
|---|---|---|
| v19.9.3 | 2026-04-17 | 🐛 DuckDB删除改为分批+ LIMIT；修复backup缓存路径(data/*.json)；修复restore方向错误；添加cp_history_store/prediction_store清理调度 |
| v18.8 | 2026-04-15 | 概述补充「产品范围：仅沪深主板」及与全市场列表数据源的关系说明（与 `PROJECT_OVERVIEW` 对齐） |
| v18.7 | 2026-04-15 | 与实现对齐：`StockSelectorCallback` 按 `SelectorCallback` 协议；`preload_cp_engine_from_history` 说明改为 `stocks` 表 + 可选 `allowed_codes`（核心+活跃池）；补充 `market_snapshot` / DuckDB 批量日均额、`pool_rebalance` 与 `trading_day_update` 触发说明 |
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

- [项目概览](../PROJECT_OVERVIEW.md) - 项目整体介绍
- [实施方案](../../references/) - 外部参考资料
