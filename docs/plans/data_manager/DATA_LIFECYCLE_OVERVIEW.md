# 数据生命周期管理方案 v1.7

> 本文档是数据生命周期管理方案的入口索引，实际内容拆分到以下两个文件中：

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| **本文档** | 设计原则、存储现状、保留策略、清理机制、DuckDB K线清理 | ~527 |
| [DATA_LIFECYCLE_DETAIL.md](./DATA_LIFECYCLE_DETAIL.md) | 战力历史保留、审计日志、报告、配置、实施计划、回测存档、补充功能、约束边界 | ~480 |

## 内容速览

### DATA_LIFECYCLE_OVERVIEW.md（本文档）
- **设计原则**：7条（分级存储/用户数据保护/渐进清理/可配置/安全兜底/先备份后清理/幂等断点续跑）
- **存储现状**（v18.4）：DuckDB（K线）+ SQLite（业务）+ JSON（缓存）+ 文件（备份）
- **保留策略**：P0永久(P0持仓/交易/账户)~P5审计(365天)，SQLite/DuckDB/JSON/备份四类保留规则
- **清理机制**：触发条件（每日02:00/每周03:00）、分批执行（5000条/批）、安全阈值（80%警告/95%确认）
- **DuckDB K线清理**：先归档到周K表（降采样）、透明查询路由、分批删除

### DATA_LIFECYCLE_DETAIL.md
- **战力历史保留**：cp_history保留2年（~44MB）、表结构、清理逻辑
- **审计日志**：操作记录表设计、保留365天
- **清理报告**：触发原因/影响/操作人/备份状态
- **用户可配置**：保留期限/清理阈值/禁用开关
- **实施计划**：v1.2~v1.7各阶段任务
- **专家评审**：5位专家9条意见的落实情况
- **数据保留速查表**：所有数据类型汇总
- **回测报告存档**：独立SQLite（1年/100条）、超限自动清理
- **补充功能**：历史数据填充（待集成到data_manager）
- **架构约束**：4条边界约束

---

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
TradeSnake 数据存储分层架构
├── P0: 用户资产（永不删除）
│   ├── SQLite: holdings, trades, orders, account, account_flow, holding_batches, trade_cooldown
│   └── 备份: 7天滚动
│
├── P1: 核心业务数据（保留2年）
│   ├── SQLite: cp_history（战力历史）
│   └── 备份: 365天
│
├── P2: 价格历史数据（保留2年）
│   ├── DuckDB: daily_kline（日K线，全市场5000只）
│   ├── DuckDB: minute_kline（分钟K线，核心池+活跃池）
│   ├── DuckDB: weekly_kline_archive（周K归档，降采样）
│   └── SQLite: price_history（用户查看过的价格，回测器使用）
│
├── P3: 预测结果（保留90天）
│   ├── SQLite: gain_predictions（涨幅预测）
│   ├── SQLite: probability_predictions（上涨概率）
│   └── 备份: 90天
│
├── P4: 一般缓存（1-7天自动清理）
│   ├── JSON: data/market_*.json（实时行情）
│   ├── JSON: data/fin_*.json（财务数据）
│   └── JSON: data/stock_list*.json（股票列表）
│
└── P5: 备份（3-365天轮转）
    ├── 文件: data/backup/（SQLite备份）
    └── 文件: data/backup/history/（战力历史备份）
```

### 2.2 数据存储位置

| 数据类型 | 存储 | 位置 | 备注 |
|---------|------|------|------|
| **持仓/交易/账户** | SQLite | `data/simulator.db` | P0，永不删除 |
| **战力历史** | SQLite | `data/simulator.db` | P1，2年，约44MB |
| **回测报告** | SQLite | `data/backtest_reports.db` | P1，1年/100条 |
| **日K线** | DuckDB | `data/kline_zh_a_daily.db` | P2，2年，约200MB |
| **分钟K线** | DuckDB | `data/kline_zh_a_minute.db` | P2，14天 |
| **周K归档** | DuckDB | `data/kline_zh_a_daily.db` | 降采样，透明查询 |
| **价格历史** | SQLite | `data/simulator.db` | P2，2年 |
| **涨幅预测** | SQLite | `data/predictions.db` | P3，90天 |
| **上涨概率** | SQLite | `data/predictions.db` | P3，90天 |
| **实时行情缓存** | JSON | `data/market_*.json` | P4，1天 |
| **财务数据缓存** | JSON | `data/fin_*.json` | P4，7天 |
| **股票列表缓存** | JSON | `data/stock_list*.json` | P4，7天 |
| **指数成分缓存** | JSON | `data/index_*.json` | P4，7天 |
| **SQLite备份** | 文件 | `data/backup/*.db` | P5，7天 |
| **战力历史备份** | 文件 | `data/backup/history/*.json` | P5，365天 |

### 2.3 优先级分类

| 优先级 | 数据类型 | 默认保留 | 清理触发 |
|--------|---------|---------|---------|
| **P0** | 持仓、交易、账户、订单、流水、批次、冷却 | **永久** | 永不 |
| **P1** | 战力历史、回测报告 | **2年** | 每年清理 |
| **P2** | 日K线、分钟K线、价格历史 | **2年/14天** | 每日02:00 |
| **P3** | 涨幅预测、上涨概率 | **90天** | 每日02:00 |
| **P4** | 财务/市场/列表缓存 | **1-7天** | 每日02:00 |
| **P5** | SQLite备份、缓存备份 | **3-7天** | 每日 |

### 2.4 存储量估算（基于股票池规划）

| 优先级 | 数据类型 | 保留期 | 估算大小 | 备注 |
|--------|---------|--------|---------|------|
| **P0** | 持仓/交易/账户 | 永久 | ~5MB | 用户数据，极小 |
| **P1** | 战力历史 | 2年 | ~44MB | 核心+活跃+观察池 |
| **P1** | 回测报告 | 1年/100条 | <1MB | 用户分析数据 |
| **P2** | 日K线 | 2年 | ~200MB | 全市场5000只 |
| **P2** | 分钟K线 | 14天 | ~184MB | 核心池+活跃池 |
| **P2** | 周K归档 | 永久 | ~30MB | 降采样后极小 |
| **P2** | 价格历史 | 2年 | ~30MB | 回测器使用 |
| **P3** | 涨幅/概率预测 | 90天 | ~10MB | 5000只×90天 |
| **P4** | 各类缓存 | 1-7天 | <50MB | TTL自动清理 |
| **P5** | 备份文件 | 3-365天 | <200MB | 轮转覆盖 |

**总计：~754MB**（含备份）

### 2.5 快速清理项（用户数据不受影响）

以下数据可以快速清理，不影响用户资产记录：

| 优先级 | 数据类型 | 清理方式 | 预计释放 |
|--------|---------|---------|---------|
| P4 | 各类缓存 | TTL自动清理 | <50MB |
| P2 | 分钟K线 | 14天后自动清理 | ~184MB |
| P5 | 过期备份 | 7天后自动覆盖 | <200MB |
| P3 | 过期预测 | 90天后自动清理 | ~10MB |

---

## 三、保留策略（v1.2）

### 3.1 SQLite数据保留

```python
# 存储量估算（基于股票池规划）
# 战力历史：每条~134bytes，核心+活跃+观察池约1800只，1年≈22MB，2年≈44MB
# 日K线：每条~54bytes，全市场5000只×250天，2年≈200MB
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
# 日K线：每条~54bytes，5000只×250天×2年=250万条 ≈ 200MB
# 分钟K线：每条~60bytes，核心池300只+活跃池500只×273条×14天 ≈ 184MB

DUCKDB_RETENTION = {
    # 日K线：保留2年（可配置1-5年），超过降采样为周K归档
    'daily_kline': 365 * 2,     # 全市场5000只，约200MB

    # 分钟K线：核心池+活跃池均保留14天（1分钟K线）
    'minute_kline_core': 14,         # 核心池(300只)：14天 ≈ 69MB
    'minute_kline_active': 14,       # 活跃池(500只)：14天 ≈ 115MB
}

# DuckDB日K保留模式（用户可选）
DAILY_KLINE_MODE = {
    'standard': {'keep_years': 2, 'archive_weekly': True},   # 默认：2年+周K归档
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

### 4.1 清理触发条件

| 触发条件 | 执行时间 | 清理内容 |
|---------|---------|---------|
| **每日02:00** | 每日凌晨 | P4缓存、DuckDB K线、预测数据 |
| **每周03:00** | 周日凌晨 | P2/P3全部数据、告警记录 |
| **每月1日02:00** | 每月1号凌晨 | P1核心数据（战力历史） |
| **存储超限80%** | 实时监控 | 所有可清理数据（按优先级） |
| **存储超限95%** | 实时监控 | **强制清理**（用户确认后执行） |

### 4.2 清理执行策略

```python
class CleanupStrategy:
    """清理策略"""

    # 执行时间
    SCHEDULE = {
        'daily': '02:00',      # 每日清理P4缓存
        'weekly': '03:00',     # 每周清理P2/P3数据
        'monthly': '02:00',    # 每月1号清理P1数据
    }

    # 分批大小（避免IO阻塞）
    BATCH_SIZE = {
        'duckdb': 5000,        # DuckDB每批5000条
        'sqlite': 1000,        # SQLite每批1000条
        'file': 100,           # 文件每批100个
    }

    # 安全阈值
    THRESHOLD = {
        'warning': 0.80,       # 80%告警
        'critical': 0.95,     # 95%强制清理
    }

    # 并发控制
    MAX_WORKERS = 2           # 最多2个并发清理任务
```

### 4.3 清理执行流程

```
清理任务调度
│
├─[每日 02:00] ──────────────────────────────────────
│  ├─ P4缓存清理
│  │  ├─ 实时行情缓存（1天前）
│  │  ├─ 财务数据缓存（7天前）
│  │  ├─ 股票列表缓存（7天前）
│  │  └─ Tushare原始数据（7天前）
│  │
│  ├─ DuckDB K线清理（按保留期）
│  │  ├─ 日K线（超过2年 → 先归档后删除）
│  │  ├─ 分钟K线（超过14天）
│  │  └─ 周K归档表（永久保留，不清理）
│  │
│  └─ 预测数据清理（超过90天）
│     ├─ 涨幅预测
│     └─ 上涨概率预测
│
├─[每周 03:00] ─────────────────────────────────────
│  ├─ P2全部数据巡检
│  ├─ P3全部数据巡检
│  └─ 告警记录清理（90天前）
│
├─[每月1号 02:00] ──────────────────────────────────
│  └─ P1核心数据清理
│     └─ 战力历史（超过2年 → 删除）
│
└─[存储超限] ───────────────────────────────────────
   ├─ >80%: 发送告警通知用户
   └─ >95%: 用户确认后强制清理
```

### 4.4 清理安全保护

```python
class CleanupProtection:
    """清理安全保护"""

    # 1. 清理前备份（幂等性保证）
    def pre_cleanup_backup(self, data_type: str) -> str:
        """清理前先备份，返回备份路径"""
        backup_path = f"data/backup/{data_type}/{timestamp}.bak"
        # 备份最近7天数据（覆盖2年保留期）
        return backup_path

    # 2. 存储上限保护
    def check_storage_limit(self, db_path: str) -> bool:
        """检查是否超过存储上限"""
        usage = get_disk_usage(db_path)
        return usage < self.THRESHOLD['warning']

    # 3. 数据完整性校验
    def verify_before_cleanup(self, data_type: str) -> bool:
        """清理前数据完整性校验"""
        if data_type == 'duckdb_daily_kline':
            return self.verify_kline_integrity()
        elif data_type == 'sqlite_cp_history':
            return self.verify_cp_history_integrity()
        return True

    # 4. 幂等性保证（断点续跑）
    def cleanup_with_idempotency(self, data_type: str, batch_size: int):
        """带幂等性保证的清理"""
        state_key = f"cleanup_state_{data_type}"
        state = self.load_state(state_key)

        if state and state['last_batch_id'] > 0:
            # 从上次中断的位置继续
            start_from = state['last_batch_id']
            logger.info(f"断点续跑：从第{start_from}批继续")
        else:
            start_from = 0

        for batch_id in range(start_from, total_batches):
            # 执行清理
            self.cleanup_batch(data_type, batch_id)
            # 更新状态
            self.save_state(state_key, {'last_batch_id': batch_id})

    # 5. 清理后验证
    def verify_after_cleanup(self, data_type: str) -> bool:
        """清理后数据验证"""
        return True
```

### 4.5 存储上限保护

```python
# 存储监控与保护
STORAGE_PROTECTION = {
    'duckdb': {
        'max_size_gb': 50,          # DuckDB最大50GB
        'warning_threshold': 0.80,  # 80%告警
        'critical_threshold': 0.95,  # 95%强制清理
    },
    'sqlite': {
        'max_size_gb': 10,           # SQLite最大10GB
        'warning_threshold': 0.80,
        'critical_threshold': 0.95,
    },
    'json_cache': {
        'max_size_mb': 500,          # JSON缓存最大500MB
        'warning_threshold': 0.70,
        'critical_threshold': 0.90,
    },
    'backup': {
        'max_size_gb': 5,            # 备份最大5GB
        'warning_threshold': 0.80,
        'critical_threshold': 0.95,
    },
}

def enforce_storage_limit(db_type: str):
    """强制执行存储上限保护"""
    config = STORAGE_PROTECTION[db_type]
    current_usage = get_current_usage(db_type)

    if current_usage >= config['critical_threshold']:
        # 强制清理到70%
        target_usage = config['critical_threshold'] * 0.7
        force_cleanup(db_type, target_usage)
        notify_user(f"[{db_type}] 存储超过95%，已强制清理")

    elif current_usage >= config['warning_threshold']:
        # 发送告警
        notify_user(f"[{db_type}] 存储超过80%，建议清理")
```

**注意**：强制清理至80%可能导致将5年日K直接砍到1年，用户可能无法接受。
**建议**：>95%时弹窗让用户选择清理策略。

---

## 五、DuckDB K线清理

### 5.1 问题分析

当前使用 `INSERT OR REPLACE`，同一股票同一日期只会有一条记录，数据只增不减。

**数据增长估算（基于股票池规划）：**
- 日K线：5000只股票（全市场）× 250交易日 × 2年 = **250万条** ≈ 200MB
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
-- Step 1: 降采样归档到周K表（2年前的日K聚合为周K）
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

    two_years_ago = (datetime.now() - timedelta(days=365*2)).strftime("%Y-%m-%d")

    results = []

    # 2年内数据：直接从日K表查询
    if start_date < two_years_ago:
        results.extend(query_from_duckdb(
            "SELECT * FROM daily_kline WHERE code=? AND trade_date BETWEEN ? AND ?",
            [code, start_date, min(end_date, two_years_ago)]
        ))
        start_date = two_years_ago

    # 2年前数据：查询周K归档表（自动转换）
    if end_date > two_years_ago:
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
