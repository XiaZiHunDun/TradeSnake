# TradeSnake 数据生命周期管理方案 v1.4

> **v1.4更新**：新增回测报告存档规范（backtest_reports）
> **v1.3更新**：根据股票池规划（核心300/活跃500/观察1000/全市场5000）调整保留期限：
> - 战力历史：永久 → **2年**（约44MB）
> - 日K线：5年 → **3年**（全市场5000只，约200MB）
> - 分钟K线：核心池+活跃池均保留14天（**1分钟K线**，约184MB）

## 一、设计原则

基于5位专家设计方案 + 5份专家评审意见：

1. **分级存储**：按时效性分层，越久远的数据保留粒度越粗
2. **用户数据永不删除**：持仓、交易记录、战力历史等核心业务数据严格保护
3. **渐进式清理**：分批删除，避免IO阻塞，不影响服务
4. **可配置化**：保留周期、清理阈值支持用户自定义
5. **安全兜底**：清理前校验，存储上限保护
6. **先备份后清理**：确保数据安全，备份优先于清理
7. **幂等性与断点续跑**：清理任务可重复执行，中断后可继续

---

## 二、项目数据存储现状（v18.4）

### 2.1 完整数据存储架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SQLite (tradesnake.db)                      │
│  ┌─────────────┬──────────────────────────────────────────────────┐  │
│  │   表名      │  说明                                             │  │
│  ├─────────────┼──────────────────────────────────────────────────┤  │
│  │ stocks      │ 股票当前数据（每日刷新）                          │  │
│  │ cp_history  │ 战力历史（每日新增，可追溯分析）← P1重要业务数据 │  │
│  │ holdings    │ 当前持仓 ← P0用户资产数据，绝不能丢               │  │
│  │ trades      │ 历史交易记录 ← P0用户资产数据，绝不能丢           │  │
│  │ orders      │ 订单记录                                          │  │
│  │ account_flow│ 账户流水                                          │  │
│  │ holding_batch│ 持仓批次（T+1追踪）                             │  │
│  │ trade_cooldown│ 交易冷却期                                      │  │
│  │ price_history│ 价格历史（用户查看过的）                         │  │
│  │ alert_config│ 告警配置                                          │  │
│  │ alerts      │ 告警记录                                          │  │
│  │ user_profile│ 用户配置                                          │  │
│  │ config      │ 系统配置                                          │  │
│  │ cleanup_audit│ 清理审计日志 ← 新增                             │  │
│  └─────────────┴──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     SQLite (backtest_reports.db)                    │
│  ┌─────────────────┬─────────────────────────────────────────────┐   │
│  │   表名          │  说明                                         │   │
│  ├─────────────────┼─────────────────────────────────────────────┤   │
│  │ backtest_reports│ 回测报告存档（P2重要参考，用户手动分析）     │   │
│  └─────────────────┴─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                           DuckDB                                     │
│  ┌─────────────────┬─────────────────────────────────────────────┐   │
│  │   表名          │  说明                                         │   │
│  ├─────────────────┼─────────────────────────────────────────────┤   │
│  │ daily_kline     │ 日K线（INSERT OR REPLACE，需清理）           │   │
│  │ minute_kline    │ 分钟K线（核心+活跃池14天，1分钟粒度）     │   │
│  │ weekly_kline_archive │ 周K归档表（降采样后存储）← 新增         │   │
│  └─────────────────┴─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         JSON缓存文件 (data/)                           │
│  ┌────────────────────────┬─────────────────────────────────────────┐   │
│  │   文件                 │  说明                                    │   │
│  ├────────────────────────┼─────────────────────────────────────────┤   │
│  │ fin_*.json             │ 东方财富财务数据缓存（TTL 7天）        │   │
│  │ market_*.json          │ 市场行情缓存（TTL 1天）                 │   │
│  │ stock_list_cache.json  │ 股票列表缓存（TTL 7天）                 │   │
│  │ stock_pool.json        │ 股票池配置（用户修改，更新时覆盖）       │   │
│  │ stock_list.json        │ Tushare完整股票列表（TTL 7天）          │   │
│  │ market_trends.json     │ 市场趋势数据（TTL 7天）                 │   │
│  │ enhancer_status.json   │ 增强器运行状态（TTL 30天）              │   │
│  │ cp_history.json        │ 战力历史JSON（已被SQLite替代，兼容用）  │   │
│  │ tushare_ts_*.json     │ Tushare原始数据（TTL 7天）             │   │
│  └────────────────────────┴─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         备份文件 (data/backup/)                       │
│  ┌─────────────────┬──────────────────────────────────────────────┐   │
│  │   目录          │  说明                                         │   │
│  ├─────────────────┼──────────────────────────────────────────────┤   │
│  │ backup/sqlite/  │ SQLite备份（每日，保留7天）                  │   │
│  │ backup/cache/   │ 缓存备份（每日，保留3天）                    │   │
│  │ backup/history/ │ 战力历史备份（每周，保留365天）← 改为1年    │   │
│  │ backup/protected│ 清理保护备份（清理前自动创建，保留7天）← 新增│   │
│  └─────────────────┴──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据分类（按重要性）

| 等级 | 数据类型 | 存储位置 | 保留策略 | 说明 |
|-----|---------|---------|---------|------|
| **P0 绝不能删** | 持仓、交易历史、账户信息 | SQLite | **永久** | 用户资产数据 |
| **P1 核心业务** | 战力历史(cp_history) | SQLite | **2年** | 约44MB，核心+活跃+观察池 |
| **P2 重要参考** | 日K线历史 | DuckDB | **3年**(可配置) | 约200MB，超限降采样归档 |
| **P3 一般缓存** | 分钟K线(核心+活跃) | DuckDB | **14天** | 约184MB，1分钟粒度 |
| **P4 临时缓存** | 财务/市场/列表缓存 | JSON | 1-7天 | 自动清理 |
| **P5 备份** | SQLite/缓存/历史备份 | 文件 | 3-365天 | 定期轮转 |

---

## 三、保留策略（v1.2）

### 3.1 SQLite数据保留

```python
# 存储量估算（基于股票池规划）
# 战力历史：每条~134bytes，核心+活跃+观察池约1800只，1年≈22MB，2年≈44MB
# 日K线：每条~54bytes，全市场5000只×250天，3年≈200MB
# 分钟K线：每条~60bytes，核心池300只×240分×7天，≈30MB

SQLITE_RETENTION = {
    # P0: 用户资产数据 - 永不删除
    'holdings': None,           # 持仓记录
    'trades': None,             # 交易历史
    'orders': None,             # 订单记录
    'account': None,            # 账户信息
    'account_flow': None,       # 账户流水
    'holding_batches': None,    # 持仓批次（T+1）
    'trade_cooldown': None,     # 交易冷却

    # P1: 核心业务数据 - 保留2年（约10MB）
    'cp_history': 365 * 2,     # 战力历史，2年足够动量计算

    # P2: 价格历史 - 保留2年
    'price_history': 365 * 2,   # 用户查看过的价格（2年）

    # P3: 告警记录 - 保留90天
    'alerts': 90,               # 告警记录
    'alert_config': None,       # 告警配置（保留）

    # P4: 系统数据 - 保留
    'stocks': None,             # 股票列表（每日刷新）
    'user_profile': None,       # 用户配置
    'config': None,             # 系统配置
    'ex_right_factor': None,    # 除权因子

    # P5: 审计日志 - 保留365天
    'cleanup_audit': 365,       # 清理审计日志
}
```

### 3.2 DuckDB数据保留

```python
# 存储量估算（基于股票池规划）
# 数据源：akshare.stock_zh_a_hist_min_em (东方财富1分钟K线)
# 日K线：每条~54bytes，5000只×250天×3年=375万条 ≈ 200MB
# 分钟K线：每条~60bytes，核心池300只+活跃池500只×273条×14天 ≈ 184MB

DUCKDB_RETENTION = {
    # 日K线：保留3年（可配置1-5年），超过降采样为周K归档
    'daily_kline': 365 * 3,     # 全市场5000只，约200MB

    # 分钟K线：核心池+活跃池均保留14天（1分钟K线）
    'minute_kline_core': 14,         # 核心池(300只)：14天 ≈ 69MB
    'minute_kline_active': 14,       # 活跃池(500只)：14天 ≈ 115MB
}

# DuckDB日K保留模式（用户可选）
DAILY_KLINE_MODE = {
    'standard': {'keep_years': 3, 'archive_weekly': True},   # 默认：3年+周K归档
    'premium': {'keep_years': 5, 'archive_weekly': False},  # 高配：5年全保留
    'minimal': {'keep_years': 1, 'archive_weekly': True},   # 低配：1年+周K归档
}
```

### 3.3 JSON缓存保留

```python
CACHE_RETENTION = {
    # 实时行情：1天
    'realtime_cache': 1,         # data/market_*.json

    # 财务数据：7天
    'financial_cache': 7,         # data/fin_*.json

    # 股票列表缓存：7天
    'stock_list_cache': 7,        # data/stock_list_cache.json

    # 股票池配置：用户修改则跳过TTL清理
    'stock_pool': 7,              # data/stock_pool.json

    # Tushare完整列表：7天
    'stock_list': 7,              # data/stock_list.json

    # 市场趋势数据：7天
    'market_trends': 7,          # data/market_trends.json

    # 增强器状态：30天
    'enhancer_status': 30,        # data/enhancer_status.json

    # Tushare原始数据：7天
    'tushare_raw': 7,             # data/tushare_ts_*.json

    # 战力历史JSON：30天
    'cp_history_json': 30,        # data/cp_history.json
}
```

### 3.4 备份保留

```python
# 战力历史保留2年，备份覆盖即可
BACKUP_RETENTION = {
    'sqlite_backup': 7,           # SQLite备份（天）
    'cache_backup': 3,            # 缓存备份（天）
    'cp_history_backup': 365,     # 战力历史备份（1年，覆盖2年保留期）
    'protected_backup': 7,        # 清理保护备份（7天不可删除）
}
```

---

## 四、清理机制

### 4.1 清理任务调度

| 任务 | 触发时间 | 说明 |
|-----|---------|------|
| 缓存清理 | 每日凌晨 02:00 | 随备份一起执行 |
| DuckDB清理 | 每日凌晨 02:00 | 清理旧K线 |
| 备份轮转 | 每日凌晨 02:00 | 先备份后清理 |
| SQLite历史清理 | 每周日凌晨 03:00 | 清理旧price_history/alerts |

### 4.2 清理优先级（安全顺序）

```
1. 临时文件（temp/）              → 超过24小时即删
2. 市场行情缓存（market_*.json）  → 超过1天即删
3. 财务数据缓存（fin_*.json）     → 超过7天即删
4. 股票列表缓存                   → 超过7天即删
5. 股票池配置（stock_pool.json）  → 超过7天即删（用户修改跳过）
6. 市场趋势（market_trends.json） → 超过7天即删
7. Tushare原始数据               → 超过7天即删
8. 增强器状态                     → 超过30天即删
9. 过期备份文件                   → 按类型保留期删除
10. DuckDB分钟K线                → 核心池+活跃池14天（分批）
11. DuckDB旧日K线                → 超过3年降采样归档（分批）
12. SQLite旧cp_history           → 超过2年归档
13. SQLite旧price_history        → 超过2年归档
14. SQLite旧alerts               → 超过90天归档
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ 绝不触碰：holdings、trades、orders、account、stock_pool(用户配置)
```

### 4.3 核心原则：先备份后清理

```python
def daily_cleanup():
    """每日凌晨执行 - 严格遵循先备份后清理"""

    # Step 0: 检查是否已执行（幂等性）
    if is_already_cleaned_today():
        log("今日已清理，跳过")
        return

    # Step 1: 清理前核心数据校验
    pre_cleanup_check()

    # Step 2: 创建清理保护备份（7天）
    create_protected_backup()

    # Step 3: 执行备份（先于任何清理）
    backup_manager.backup_all()

    # Step 4: 清理JSON缓存
    cleanup_cache_by_ttl()

    # Step 5: DuckDB清理（分批）
    cleanup_old_minute_klines_tiered(batch_size=10000)  # 核心+活跃池14天，1分钟K线
    cleanup_old_daily_klines(keep_years=3, batch_size=5000)

    # Step 6: 检查存储水位
    check_storage_water_level()

    # Step 7: 记录清理审计日志
    log_cleanup_audit()

    # Step 8: 标记完成
    mark_cleanup_done()
```

### 4.4 渐进式清理流程（分批删除）

```python
def batch_cleanup_daily_kline(keep_years: int = 5, batch_size: int = 5000):
    """分批清理日K线，避免长时间锁表"""
    store = get_duckdb_store()
    cutoff = datetime.now() - timedelta(days=keep_years * 365)

    total_deleted = 0
    while True:
        # 每批只删5000条
        deleted = store.delete_old_klines_batch(
            cutoff=cutoff,
            batch_size=batch_size
        )
        if deleted == 0:
            break

        total_deleted += deleted
        time.sleep(0.1)  # 每批之间短暂休眠，避免阻塞

        log(f"已清理 {total_deleted} 条日K线记录")

    return {'total_deleted': total_deleted}
```

### 4.5 清理前核心数据校验

```python
def pre_cleanup_check():
    """清理前核心数据校验 - 防止误删"""

    # 1. 校验P0/P1表记录数是否正常（无异常减少）
    core_tables = ['holdings', 'trades', 'cp_history']
    for table in core_tables:
        count = sqlite_db.query(f"SELECT COUNT(*) FROM {table}").scalar()
        last_count = get_last_recorded_count(table)

        if last_count and count < last_count * 0.9:  # 记录数骤降10%告警
            raise Exception(f"核心表{table}记录数异常（当前{count}，上次{last_count}），终止清理")

        update_recorded_count(table, count)

    # 2. 记录清理前的数据快照
    log(f"清理前校验完成: holdings={get_count('holdings')}, "
        f"trades={get_count('trades')}, cp_history={get_count('cp_history')}")
```

### 4.6 幂等性与断点续跑

```python
def is_already_cleaned_today() -> bool:
    """检查今日是否已执行清理（幂等性）"""
    state_file = Path("data/.cleanup_state")
    if not state_file.exists():
        return False

    try:
        state = json.loads(state_file.read_text())
        today = datetime.now().strftime("%Y-%m-%d")
        return state.get('date') == today
    except Exception:
        return False


def mark_cleanup_done():
    """标记清理完成"""
    state_file = Path("data/.cleanup_state")
    state_file.write_text(json.dumps({
        'date': datetime.now().strftime("%Y-%m-%d"),
        'completed_at': datetime.now().isoformat()
    }))
```

### 4.7 存储空间保护

```
┌──────────────────────────────────────────────────────────────┐
│  存储使用率    │  行为                                        │
├──────────────────────────────────────────────────────────────┤
│  < 70%        │  正常保留策略                                 │
│  70% - 80%    │  警告提示用户                                 │
│  80% - 95%    │  缩短保留期50%，执行深度清理                 │
│  > 95%        │  触发用户确认，让用户选择清理策略             │
│               │  （不自动强制清理，防止用户不满）              │
└──────────────────────────────────────────────────────────────┘

注意：强制清理至80%可能导致将5年日K直接砍到1年，用户可能无法接受。
建议：>95%时弹窗让用户选择清理策略。
```

---

## 五、DuckDB K线清理

### 5.1 问题分析

当前使用 `INSERT OR REPLACE`，同一股票同一日期只会有一条记录，数据只增不减。

**数据增长估算（基于股票池规划）：**
- 日K线：5000只股票（全市场）× 250交易日 × 3年 = **375万条** ≈ 200MB
- 分钟K线：核心池300只 × 240分钟 × 7天 ≈ 50万条 ≈ 30MB

### 5.2 DuckDB周K归档表结构

```sql
-- 周K归档表（降采样后存储）
CREATE TABLE IF NOT EXISTS weekly_kline_archive (
    code TEXT NOT NULL,
    trade_week TEXT NOT NULL,  -- 格式：YYYY-WW（如2026-01表示2026年第1周）
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume BIGINT NOT NULL,
    archived_at TEXT DEFAULT CURRENT_TIMESTAMP,  -- 归档时间
    PRIMARY KEY (code, trade_week)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_weekly_archive_code ON weekly_kline_archive(code);
```

### 5.3 日K线清理策略（先归档后删除）

```sql
-- Step 1: 降采样归档到周K表（3年前的日K聚合为周K）
INSERT OR REPLACE INTO weekly_kline_archive
SELECT
    code,
    strftime('%Y-%W', trade_date) as trade_week,
    MIN(open) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close) as close,
    SUM(volume) as volume,
    CURRENT_TIMESTAMP as archived_at
FROM daily_kline
WHERE trade_date < date('now', '-3 years')
GROUP BY code, strftime('%Y-%W', trade_date);

-- Step 2: 删除原数据
DELETE FROM daily_kline
WHERE trade_date < date('now', '-3 years');
```

### 5.4 查询透明路由（用户无感知）

```python
def query_daily_kline(code: str, start_date: str, end_date: str) -> List[Dict]:
    """透明查询日K线，自动跨表路由"""

    three_years_ago = (datetime.now() - timedelta(days=365*3)).strftime("%Y-%m-%d")

    results = []

    # 3年内数据：直接从日K表查询
    if start_date < three_years_ago:
        results.extend(query_from_duckdb(
            "SELECT * FROM daily_kline WHERE code=? AND trade_date BETWEEN ? AND ?",
            [code, start_date, min(end_date, three_years_ago)]
        ))
        start_date = three_years_ago

    # 3年前数据：查询周K归档表（自动转换）
    if end_date > three_years_ago:
        weekly_data = query_from_duckdb(
            """SELECT
                code,
                trade_week as trade_date,
                open, high, low, close, volume
            FROM weekly_kline_archive
            WHERE code=? AND trade_week BETWEEN ? AND ?
            """,
            [code, start_date[:7], end_date[:7]]
        )
        results.extend(weekly_data)

    return results
```

### 5.5 DuckDB清理代码（分批）

```python
def cleanup_old_daily_klines(keep_years: int = 3, batch_size: int = 5000) -> Dict:
    """清理超过指定年数的日K线数据（分批执行）"""
    store = get_duckdb_store()
    cutoff = datetime.now() - timedelta(days=keep_years * 365)

    total_deleted = 0
    total_archived = 0

    while True:
        # 1. 降采样归档到周K表（批量）
        archived = store.archive_to_weekly_batch(cutoff, batch_size=1000)
        total_archived += archived

        if archived == 0:
            break

        time.sleep(0.1)

    # 2. 删除原数据（分批）
    while True:
        deleted = store.delete_old_klines_batch(cutoff, batch_size=batch_size)
        if deleted == 0:
            break

        total_deleted += deleted
        time.sleep(0.1)

    return {
        'total_archived': total_archived,
        'total_deleted': total_deleted,
        'keep_years': keep_years
    }
```

---

## 六、战力历史数据（cp_history）保留策略

### 6.1 当前状态

- **主存储**：SQLite `cp_history` 表（v18.2+）
- **降级存储**：`data/cp_history.json`（只保留30天）
- **备份**：`data/backup/history/`（保留90天）

### 6.2 保留策略

| 存储 | 保留期 | 说明 |
|-----|-------|------|
| SQLite cp_history | **2年** | 约44MB，核心+活跃+观察池 |
| JSON cp_history | 30天 | 兼容旧版本 |
| 备份 cp_history | 365天 | 覆盖2年保留期 |

### 6.3 cp_history表结构

```sql
CREATE TABLE cp_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    total_cp REAL DEFAULT 0,
    growth_score REAL DEFAULT 0,
    value_score REAL DEFAULT 0,
    quality_score REAL DEFAULT 0,
    momentum_score REAL DEFAULT 0,
    risk_score REAL DEFAULT 0,
    rank INTEGER DEFAULT 0,
    recorded_at TEXT NOT NULL,     -- 记录日期（每日一条）
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_cp_history_recorded_at ON cp_history(recorded_at);
CREATE INDEX idx_cp_history_code ON cp_history(code);
```

### 6.4 为什么不永久保留

战力历史数据量估算（股票池约1800只/天）：
- 每条约134bytes
- 2年 ≈ **44MB**（可控）
- 足够支持：5日、20日、60日、半年等常见动量计算
- 超过2年的历史对日常交易分析意义有限

---

## 七、清理审计日志

### 7.1 审计日志表结构

```sql
CREATE TABLE IF NOT EXISTS cleanup_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    operation TEXT NOT NULL,      -- 'daily_kline_cleanup', 'cache_cleanup'
    details TEXT NOT NULL,         -- JSON格式的详细信息
    records_deleted INTEGER DEFAULT 0,
    space_freed_bytes INTEGER DEFAULT 0,
    status TEXT NOT NULL,          -- 'success', 'failed', 'partial'
    error_message TEXT,
    operator TEXT DEFAULT 'system' -- 'system' or 'user'
);
```

### 7.2 清理审计日志记录

```python
def log_cleanup_audit(operation: str, details: dict, records_deleted: int,
                      space_freed: int, status: str, error: str = None):
    """记录清理审计日志"""
    audit_entry = {
        'timestamp': datetime.now().isoformat(),
        'operation': operation,
        'details': details,
        'records_deleted': records_deleted,
        'space_freed_bytes': space_freed,
        'status': status,
        'error_message': error,
        'operator': 'system'
    }

    db.execute("""
        INSERT INTO cleanup_audit (timestamp, operation, details, records_deleted, space_freed, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        audit_entry['timestamp'],
        audit_entry['operation'],
        json.dumps(audit_entry['details']),
        records_deleted,
        space_freed,
        status,
        error
    ))
```

---

## 八、清理报告（用户通知）

### 8.1 清理报告生成

```python
def generate_cleanup_report(results: Dict) -> str:
    """生成清理报告

    Args:
        results: 清理操作结果，包含以下结构:
            - timestamp: 清理执行时间
            - operations: 操作列表，每项包含:
                - operation: 操作名称
                - status: success/failed
                - deleted_count: 删除数量
                - freed_bytes: 释放字节数
    """
    report = f"""
📊 数据清理报告 ({results.get('timestamp', datetime.now().isoformat())})

✅ 执行结果：
"""
    for op in results.get("operations", []):
        status_icon = "✅" if op.get("status") == "success" else "❌"
        report += f"{status_icon} {op.get('operation')}: 删除 {op.get('deleted_count', 0)} 条，释放 {op.get('freed_bytes', 0) / 1024:.1f} KB\n"

    storage = check_storage_water_level()
    report += f"""
📦 当前存储状态：
├── 使用率: {storage['usage_percent']}%
├── 状态: {storage['status']}
└── 可用空间: {storage['free_bytes'] / 1024 / 1024 / 1024:.2f} GB
"""
    return report
```

---

## 九、用户可配置选项（v1.2）

### 9.1 配置项约束

```python
# 配置项合法值约束
CONFIG_CONSTRAINTS = {
    'daily_kline_years': {'min': 1, 'max': 5, 'default': 3},
    'minute_kline_days': {'min': 7, 'max': 14, 'default': 7},
    'cp_history_days': {'min': 365, 'max': 730, 'default': 730},  # 1-2年
    'cache_ttl_days': {'min': 1, 'max': 30, 'default': 7},
    'alert_retention_days': {'min': 30, 'max': 365, 'default': 90},
    'price_history_years': {'min': 1, 'max': 3, 'default': 2},
    'storage_limit_gb': {'min': 5, 'max': 50, 'default': 10},
    'auto_cleanup': {'type': 'bool', 'default': True},
    'cleanup_warning_threshold': {'min': 0.5, 'max': 0.9, 'default': 0.8},
}

def validate_config(config: dict) -> bool:
    """验证配置项是否合法"""
    for key, value in config.items():
        if key in CONFIG_CONSTRAINTS:
            constraint = CONFIG_CONSTRAINTS[key]
            if 'min' in constraint and value < constraint['min']:
                raise ValueError(f"{key} 不能小于 {constraint['min']}")
            if 'max' in constraint and value > constraint['max']:
                raise ValueError(f"{key} 不能大于 {constraint['max']}")
    return True
```

### 9.2 建议的设置界面

| 配置项 | 默认值 | 可选范围 | 说明 |
|-------|-------|---------|------|
| 日K保留年数 | 3年 | 1/2/3/5年 | DuckDB |
| 分钟K保留天数 | 7天 | 7/14天 | DuckDB（上限14天） |
| 战力历史保留 | 2年 | 1/2年 | SQLite |
| 缓存保留天数 | 7天 | 1/3/7/14/30天 | JSON缓存 |
| 告警保留天数 | 90天 | 30/60/90天 | SQLite |
| 价格历史保留 | 2年 | 1/2/3年 | SQLite |
| 自动清理 | 开启 | 开启/关闭 | 全局开关 |
| 存储上限警告 | 80% | 50%/70%/80% | 告警阈值 |
| 存储上限 | 10GB | 5/10/20GB | 总存储上限 |

---

## 十、实施计划（v1.2）

### Phase 1: 核心安全（v18.5）- P0必做
- [x] **先备份后清理** - 调整清理时序
- [x] **清理前核心数据校验** - pre_cleanup_check
- [x] **分批删除** - DuckDB日K分批删除（每批5000条）
- [x] **幂等性保护** - 防止重复清理
- [x] **DuckDB周K归档表** - weekly_kline_archive结构
- [x] **DuckDB降采样归档代码** - archive_to_weekly

### Phase 2: 监控告警（v18.6）- P1建议做
- [x] **VACUUM条件触发** - 碎片超过100MB才执行
- [x] **清理审计日志** - cleanup_audit表
- [x] **清理报告生成** - 用户通知
- [x] **增强JSON缓存TTL** - 区分用户配置vs可下载缓存
- [x] **cp_history冷热分离** - is_hot字段

### Phase 3: 增强优化（v18.7）- P2可选
- [ ] **查询透明路由** - 自动跨表查询
- [ ] **存储增长预测** - days_to_threshold预警
- [ ] **95%存储时用户确认** - 弹窗选择
- [ ] **用户配置界面** - 保留期限可调

### Phase 4: 长期架构（v19.0+）- P3规划
- [ ] **cp_history按年分表** - cp_history_2025
- [ ] **DuckDB滑动窗口表** - 按月分表
- [ ] **云端同步接口** - 多设备支持

---

## 十一、专家评审意见落实（v1.2）

### 5份评审核心意见对照

| 评审 | 核心意见 | 落实情况 |
|-----|---------|---------|
| 评审1 | DuckDB降采样需冷数据懒加载机制 | ✅ 透明查询路由 |
| 评审1 | SQLite VACUUM需条件触发 | ✅ 碎片超过100MB触发 |
| 评审1 | cp_history需预留分区字段 | ✅ is_hot字段 |
| 评审1 | JSON缓存区分用户配置 | ✅ user_modified跳过清理 |
| 评审1 | **先备份后清理** | ✅ 严格执行 |
| 评审2 | 清理事务一致性+回滚机制 | ✅ 清理前校验+快照 |
| 评审2 | 大批量删除需分批 | ✅ 每批5000条 |
| 评审2 | 清理审计日志 | ✅ cleanup_audit表 |
| 评审2 | 用户通知机制 | ✅ 清理报告 |
| 评审3 | P0/P1备份冗余性 | ✅ 改为1年备份+保护备份 |
| 评审3 | 清理前完整性校验 | ✅ pre_cleanup_check |
| 评审3 | 月K归档表结构定义 | ✅ monthly_kline_archive |
| 评审3 | 可配置化边界约束 | ✅ CONFIG_CONSTRAINTS |
| 评审4 | price_history冗余问题 | ⚠️ 保留（用户查看历史） |
| 评审4 | 战力历史备份改为长期 | ✅ 改为365天 |
| 评审5 | DuckDB透明访问层 | ✅ query_daily_kline路由 |
| 评审5 | 95%强制清理过于激进 | ✅ 改为用户确认 |
| 评审5 | 清理调度改凌晨 | ✅ 改为02:00执行 |

---

## 十二、数据保留速查表（v1.4）

| 数据类型 | 存储位置 | 默认保留 | 最大保留 | 可配置 | 清理触发 |
|---------|---------|---------|---------|-------|---------|
| 持仓 | SQLite | **永久** | - | ❌ | 永不 |
| 交易历史 | SQLite | **永久** | - | ❌ | 永不 |
| 账户信息 | SQLite | **永久** | - | ❌ | 永不 |
| 战力历史 | SQLite | **2年** | 2年 | ❌ | 每年清理 |
| **回测报告** | SQLite | **1年/100条** | 1年/100条 | ❌ | **超限自动清理** |
| 日K线 | DuckDB | **3年** | 5年 | ✅ | 每日02:00 |
| 日K线归档 | DuckDB | **永久** | - | ❌ | 永不 |
| 分钟K线 | DuckDB | **7天** | 14天 | ✅ | 每日02:00 |
| 价格历史 | SQLite | 2年 | 3年 | ✅ | 每周03:00 |
| 告警记录 | SQLite | 90天 | 365天 | ✅ | 每周03:00 |
| 财务缓存 | JSON | 7天 | 30天 | ✅ | 每日02:00 |
| 行情缓存 | JSON | 1天 | 7天 | ✅ | 每日02:00 |
| 股票列表缓存 | JSON | 7天 | 30天 | ✅ | 每日02:00 |
| 股票池配置 | JSON | **用户控制** | - | ❌ | 永不 |
| SQLite备份 | 文件 | 7天 | - | ✅ | 每日 |
| 缓存备份 | 文件 | 3天 | - | ✅ | 每日 |
| 战力历史备份 | 文件 | 365天 | - | ✅ | 每周 |
| 清理保护备份 | 文件 | 7天 | - | ❌ | 自动 |

---

## 总结

TradeSnake数据生命周期管理核心（v1.4）：

1. **P0用户数据（持仓/交易/账户）**：**永不删除**
2. **战力历史(cp_history)**：保留**2年**（约44MB），足够日常动量计算
3. **回测报告(backtest_reports)**：保留**1年/100条**（超限自动清理最旧记录），用户手动分析
4. **日K线(DuckDB)**：保留**3年**（约200MB），超限降采样归档到周K表，**透明查询路由**
5. **分钟K线(DuckDB)**：保留**14天**（核心+活跃池约184MB，1分钟粒度），**分批删除**
6. **SQLite历史数据**：price_history保留2年，alerts保留90天
7. **缓存**：基于TTL自动清理（1-7天），用户配置跳过清理
8. **备份**：**先备份后清理**，战力历史备份365天
9. **安全机制**：清理前核心数据校验、幂等性保护、审计日志
10. **存储保护**：80%阈值警告，95%用户确认（不强制）
11. **用户可控**：保留期限、清理开关均可配置，带边界约束

**总数据量估算**：~428MB（不含备份）

---

## 十三、架构一致性说明

### 13.1 cp_history 存储位置差异

**设计意图**：根据本方案，cp_history 应由 data_manager 模块统一管理（存储、备份、清理）。

**迁移状态**：✅ v19.7 已完成迁移

**迁移后文件对应**：
| 文件 | 角色 |
|------|------|
| `data_manager/cp_history_store.py` | ✅ cp_history 存储和管理（SQLite WAL模式） |
| `engine/history.py` | ✅ 调用 data_manager.cp_history_store |
| `backtester/verification.py` | ✅ 从 data_manager.cp_history_store 读取 |
| `simulator/database.py` | ⚠️ 暂保留 cp_history 表（向后兼容），待后续清理 |

**迁移状态**：✅ 已完成（v19.7）

> cp_history 的存储和管理已迁移到 `data_manager/cp_history_store.py`（SQLite WAL模式）。
> `simulator/database.py` 暂保留 cp_history 表以保持向后兼容，待后续清理。

---

## 十四、回测报告存档（backtest_reports）

### 14.1 存储设计

回测报告用于用户手动分析和优化策略参数，存储在独立SQLite文件中：

| 项目 | 设计 |
|-----|------|
| 存储位置 | `data/backtest_reports.db` |
| 保留期限 | **1年** |
| 记录数上限 | **100条**（超限自动删除最旧记录） |
| 数据性质 | 用户手动读取分析，**无需反馈闭环** |

### 14.2 表结构

```sql
CREATE TABLE backtest_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT NOT NULL UNIQUE,           -- UUID
    created_at TEXT NOT NULL,                  -- 创建时间
    period_start TEXT NOT NULL,                -- 回测开始日期
    period_end TEXT NOT NULL,                  -- 回测结束日期
    initial_capital REAL NOT NULL,             -- 初始资金
    final_capital REAL NOT NULL,               -- 最终资金
    total_return_pct REAL NOT NULL,            -- 总收益率%
    annual_return_pct REAL NOT NULL,           -- 年化收益率%
    sharpe_ratio REAL,                         -- 夏普比率
    max_drawdown_pct REAL,                     -- 最大回撤%
    win_rate_pct REAL,                         -- 胜率%
    total_trades INTEGER,                       -- 总交易次数
    profitable_trades INTEGER,                  -- 盈利次数
    losing_trades INTEGER,                      -- 亏损次数

    -- 战力预测验证
    cp_accuracy_pct REAL,                     -- 战力预测准确率%
    high_cp_avg_profit_pct REAL,               -- 高战力组平均收益%
    low_cp_avg_profit_pct REAL,                -- 低战力组平均收益%

    -- 换股验证
    swap_total_count INTEGER,                   -- 换股总次数
    swap_win_rate_pct REAL,                    -- 换股胜率%
    swap_avg_profit_pct REAL,                  -- 换股平均收益%

    -- 回测参数
    strategy_params TEXT,                       -- 策略参数(JSON)
    top_n INTEGER,                             -- 持仓数量
    benchmark TEXT,                            -- 基准
    notes TEXT                                 -- 用户备注
);

CREATE INDEX idx_backtest_reports_created ON backtest_reports(created_at);
CREATE INDEX idx_backtest_reports_period ON backtest_reports(period_start, period_end);
```

### 14.3 生命周期管理

```python
BACKTEST_REPORT_RETENTION = {
    'max_records': 100,           # 最多保留100条
    'max_age_days': 365,          # 保留1年
}

def save_backtest_report(report: BacktestReport) -> str:
    """保存回测报告，超限时自动删除最旧记录"""
    db_path = "data/backtest_reports.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查记录数是否超限
    cursor.execute("SELECT COUNT(*) FROM backtest_reports")
    count = cursor.fetchone()[0]

    if count >= BACKTEST_REPORT_RETENTION['max_records']:
        # 删除最旧的记录
        cursor.execute("""
            DELETE FROM backtest_reports
            WHERE id = (SELECT id FROM backtest_reports ORDER BY created_at ASC LIMIT 1)
        """)

    # 插入新记录
    cursor.execute("""
        INSERT INTO backtest_reports (...)
        VALUES (...)
    """, (...))

    conn.commit()
    conn.close()
```

### 14.4 数据分类更新

| 等级 | 数据类型 | 存储位置 | 保留策略 |
|-----|---------|---------|---------|
| P0 绝不能删 | 持仓、交易历史 | SQLite | **永久** |
| P1 核心业务 | 战力历史 | SQLite | **2年** |
| P2 重要参考 | 回测报告 | SQLite | **1年/100条** |
| P2 重要参考 | 日K线 | DuckDB | **3年** |

### 14.5 与其他模块的关系

```
backtester/verification.py → 写入 → backtest_reports.db
                                    ↓
                              用户手动读取
                                    ↓
                           优化策略参数（手动闭环）
```
