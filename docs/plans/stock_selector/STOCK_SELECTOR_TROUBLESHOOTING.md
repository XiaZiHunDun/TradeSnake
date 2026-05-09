# 股票筛选模块 - 问题追踪与更新记录

> 本文档包含文件清单、待确认事项、v19.9 重大更新说明及专家评审依据。

---

## 九、文件清单

```
backend/stock_selector/
├── __init__.py
├── config.py               # 含动态调整配置+更新频率策略
├── stock_selector.py       # 主筛选器 (Facade)
├── pool_manager.py         # 股票池管理器（含挤出）
├── update_strategy.py      # ⚠️ 数据更新频率策略 🆕
├── filters/
│   ├── __init__.py
│   ├── blacklist.py        # 黑名单过滤
│   ├── manual_list.py      # 白名单/黑名单
│   └── admission.py         # 准入条件
├── rebalancer.py            # 动态再平衡（含冲突处理）
├── event_trigger.py         # 事件触发（含去重）
├── index_sync.py            # 指数同步（含动态日期）
├── financial_watcher.py     # 财务预警（含梯度+恢复）
├── history_keeper.py        # 历史保留
└── utils/
    ├── __init__.py
    ├── code_normalizer.py   # 代码标准化
    ├── rebalance_date.py    # 指数调整日计算
    └── pool_metrics.py      # 监控指标
```

---

## 十、待确认事项

| 事项 | v19.5.1建议 | v19.5.2专家建议 | 最终建议 |
|------|------------|-----------------|---------|
| 核心池数量 | 动态250-350 | 动态比例+上限300 | **动态比例(6%)+max=350** |
| 次新股保护期 | 主板90日 | 板块差异化 | **主板90/创业120/科创120/北交所180** |
| 晋级/降级阈值 | 当前合理 | 增加观察期+回撤保护 | **增加10日观察期** |
| 指数同步频率 | 每日+调整日前 | 平时每周，调整日每日 | **动态计算** |
| 手动白名单 | 持久化JSON | 持久化+30日过期 | **30日过期** |
| 历史数据保留 | 90日 | 核心池永久保留摘要 | **核心池永久** |
| 财务预警降级 | 分级处理 | High自动，Medium确认 | **High自动，Medium15日观察** |
| ST区分 | 统一排除 | 区分ST/*ST | **配置化** |
| 流动性阈值 | 固定2000万 | 自适应（可选） | **默认固定，启用时自适应** |

---

## 十一、v19.9 重大更新说明

### 11.1 DuckDB 跨进程稳定性 (v19.9)

DuckDB 历史行情存储 (`data_manager/duckdb_store.py`) 在 v19.9 进行了重大稳定性改进：

#### 文件锁机制

```python
# 使用 fcntl.flock 实现跨进程互斥
def _acquire_lock(self, exclusive: bool = True):
    """获取文件锁（跨进程互斥）"""
    lock_fd = open(self._lock_path, 'w')
    lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    fcntl.flock(lock_fd.fileno(), lock_type)
    return lock_fd

def _release_lock(self, lock_fd):
    """释放文件锁"""
    if lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()
```

| 特性 | 说明 |
|------|------|
| **锁文件路径** | `{db_path}.lock` |
| **写锁** | `fcntl.LOCK_EX`（排他锁） |
| **读锁** | `fcntl.LOCK_SH`（共享锁） |
| **适用范围** | 所有写操作（insert/checkpoint）和表创建DDL |

#### 单连接复用

```python
class DuckDBStore:
    def __init__(self, db_path: str = None):
        # 单连接复用（跨进程文件锁保护）
        self._write_conn = None
        self._read_conn = None
        self._conn_lock = threading.Lock()  # 保护连接创建

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        """获取写连接（单例，复用）"""
        if self._write_conn is None:
            with self._conn_lock:
                if self._write_conn is None:
                    self._write_conn = duckdb.connect(self.db_path, read_only=False)
        return self._write_conn
```

**关键设计**：
- 写连接和读连接分离（避免读写冲突）
- 线程锁保护连接创建（单例模式）
- 读连接设置 `SET threads=1`（限制并发避免竞争）

#### Checkpoint 机制

```python
def checkpoint(self):
    """强制checkpoint，确保所有写操作刷新到磁盘"""
    lock_fd = None
    try:
        lock_fd = self._acquire_lock(exclusive=True)
        conn = self._get_conn()
        conn.execute("CHECKPOINT")
    except Exception as e:
        print(f"Checkpoint warning: {e}")
    finally:
        self._release_lock(lock_fd)
```

### 11.2 池状态持久化 (v19.9.9)

`PoolManager` 在 v19.9.9 新增状态持久化方法，池状态保存到 SQLite：

#### 存储位置

- 数据库：`data/tradesnake.db`
- 表：`pool_state (pool_tier TEXT PRIMARY KEY, codes TEXT, updated_at TEXT)`

#### save_state()

```python
def save_state(self) -> bool:
    """
    保存池状态到 SQLite

    Returns:
        是否保存成功
    """
    from backend.data_manager.pool_state_store import get_pool_state_store
    store = get_pool_state_store()

    # 只保存核心池和活跃池（最重要）
    pools_to_save = {
        PoolTier.CORE.value: self.get_pool(PoolTier.CORE),
        PoolTier.ACTIVE.value: self.get_pool(PoolTier.ACTIVE),
        PoolTier.OBSERVE.value: self.get_pool(PoolTier.OBSERVE),
    }

    success = store.save_all_pools(pools_to_save)
```

#### load_state()

```python
def load_state(self) -> bool:
    """
    从 SQLite 加载池状态

    Returns:
        是否加载成功（有状态被加载）
    """
    from backend.data_manager.pool_state_store import get_pool_state_store
    store = get_pool_state_store()

    loaded_pools = store.load_all_pools()
    if not loaded_pools:
        return False

    # 检查状态是否新鲜（24小时内）
    if not store.is_pool_state_fresh(PoolTier.CORE.value, max_age_hours=24):
        return False

    # 恢复池状态...
```

**关键特性**：
- 24小时新鲜度检查（过期状态不加载）
- 只保存 CORE/ACTIVE/OBSERVE 三层（不含 TEMP）
- 使用单例模式的 `PoolStateStore`

### 11.3 分钟K线自动填充 (v19.9.8)

收盘后自动填充核心池+活跃池股票的分钟K线数据：

#### 填充策略

| 参数 | 值 |
|------|-----|
| 每日填充数量 | 50只 |
| 填充天数 | 最近1天 |
| 轮换周期 | 约4天完成全部 (~200只) |
| 触发时间 | 收盘后（16:30之后） |

#### 实现位置

`api/main.py` 的 `refresh_background_task` 中：

```python
# 收盘后（16:30之后）且当日尚未填充分钟K线时
if current_hour >= 16 and _refresh_state.last_minute_kline_fill_date != today_date_str:
    minute_filler = get_minute_kline_filler()
    # 获取核心池+活跃池股票
    all_pool_codes = list(set(core_codes + active_codes))
    # 根据日期选择不同的子集（每天约50只）
    day_index = datetime.now().timetuple().tm_yday
    subset_size = 50
    start_idx = (day_index * subset_size) % len(all_pool_codes)
    codes_to_fill = all_pool_codes[start_idx:start_idx + subset_size]
    result = minute_filler.fill_all(codes=codes_to_fill, days_back=1)
```

#### 保留周期

| 表 | 保留天数 |
|----|---------|
| `minute_kline_core` | 14天 |
| `minute_kline_active` | 14天 |

### 11.4 Tushare Revenue Fallback (v19.9)

当东方财富 (eastmoney) 的 revenue 数据为0时，自动从 Tushare 补充：

#### Fallback 逻辑

```python
# Tushare revenue fallback：当 eastmoney 的 revenue 为 0 时，从 Tushare 补充
if result and result.get('revenue', 0) == 0:
    try:
        from .providers.tushare import get_tushare_provider
        ts_provider = get_tushare_provider()
        ts_fin = ts_provider.get_financial_data(symbol)
        if ts_fin and ts_fin.get('revenue', 0) > 0:
            result['revenue'] = ts_fin['revenue']
            result['revenue_growth'] = ts_fin.get('revenue_growth', 0)
    except Exception:
        pass  # Tushare fallback 失败不影响主流程
```

#### 数据源优先级

1. **首选**：东方财富 (eastmoney)
2. **备选**：Tushare（仅当 revenue=0 时触发）
3. **再备选**：Baostock（财务数据查询）

---

## 附录A: 参考专家评审

| 文档 | 核心贡献 |
|------|---------|
| 评审1 | 次新股板块差异化、动态池容量、梯度处理、监控指标、插件化过滤 |
| 评审2 | 流动性陷阱风险、临时池并发去重、财务预警滞后性、循环依赖防护 |
| 评审3 | **准入倒挂修正、挤出机制、盘中盘后分离、ST实时扫描、指数日期动态计算** |
| 评审4 | **晋级/降级冲突处理（降级优先）、临时池TTL、行业均衡、恢复机制** |
| 评审5 | **财务预警缓释、动态核心池、白名单过期、循环依赖风险** |

## 附录B: 阈值量化依据

| 阈值 | 数值 | 来源依据 |
|------|------|---------|
| 次新股保护期(主板) | 90日 | 专家建议60-120日 |
| 次新股保护期(科创/创业) | 120日 | 专家建议120日 |
| 次新股保护期(北交所) | 180日 | 流动性差异大 |
| 流通市值门槛 | ≥5亿 | 规避"壳"价值 |
| 日均成交额(准入底线) | ≥1000万 | 专家建议1000-2000万 |
| 日均成交额(观察池) | ≥1000万 | 递进式分层 |
| 日均成交额(活跃池) | ≥2000万 | 专家建议 |
| 日均成交额(核心池) | ≥5000万 | 专家建议 |
| 资产负债率预警 | >80% | 专家建议70-80% |
| 营收下滑降级阈值 | >30% | 专家建议20-30% |
| 晋级观察期 | 10日 | 专家建议 |
| 临时池TTL | 7日 | 专家建议 |
| 去重窗口期 | 24小时 | 专家建议 |
