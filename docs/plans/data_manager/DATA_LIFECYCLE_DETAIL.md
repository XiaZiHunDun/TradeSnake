# 数据生命周期管理方案 - 详细设计

> 本文档是数据生命周期管理方案的详细设计部分，对应 `DATA_LIFECYCLE_OVERVIEW.md` 的后续内容。

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
    date TEXT NOT NULL,             -- 日期（YYYY-MM-DD）
    total_cp REAL NOT NULL,         -- 战力总分
    growth_score REAL,              -- 成长分
    value_score REAL,               -- 价值分
    quality_score REAL,              -- 质量分
    momentum_score REAL,             -- 动量分
    risk_score REAL,                -- 风险分
    price REAL,                     -- 收盘价
    change_pct REAL,                -- 涨跌幅%
    volume REAL,                    -- 成交量
    amount REAL,                    -- 成交额
    pe REAL,                       -- 市盈率
    pb REAL,                        -- 市净率
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, date)               -- 唯一约束：每只股票每天一条
);

CREATE INDEX idx_cp_history_code ON cp_history(code);
CREATE INDEX idx_cp_history_date ON cp_history(date);
CREATE INDEX idx_cp_history_cp ON cp_history(total_cp);
```

### 6.4 清理策略

```python
# cp_history 清理
CP_HISTORY_RETENTION = 365 * 2  # 2年，足够计算动量因子

def cleanup_old_cp_history(retention_days: int = CP_HISTORY_RETENTION):
    """清理超过保留期的战力历史"""
    cutoff = datetime.now() - timedelta(days=retention_days)

    # 1. 先备份（保留365天）
    backup_cp_history(cutoff)

    # 2. 删除超过2年的数据
    deleted = db.execute("""
        DELETE FROM cp_history
        WHERE date < ?
    """, [cutoff.strftime("%Y-%m-%d")])

    return {'deleted': deleted, 'cutoff': cutoff}
```

---

## 七、清理审计日志

### 7.1 审计日志表设计

```sql
CREATE TABLE cleanup_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cleanup_type TEXT NOT NULL,         -- 'daily'/'weekly'/'monthly'/'manual'/'storage_limit'
    data_type TEXT NOT NULL,             -- 'duckdb_daily_kline'/'sqlite_cp_history'等
    cleanup_scope TEXT NOT NULL,         -- 'incremental'/'full'
    triggered_by TEXT NOT NULL,          -- 'scheduler'/'user'/'system'
    started_at TEXT NOT NULL,            -- 开始时间
    completed_at TEXT,                   -- 完成时间
    status TEXT NOT NULL,                -- 'running'/'completed'/'failed'/'cancelled'
    records_before INTEGER,              -- 清理前记录数
    records_after INTEGER,               -- 清理后记录数
    bytes_freed INTEGER,                 -- 释放空间（字节）
    error_message TEXT,                  # 错误信息
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cleanup_audit_type ON cleanup_audit(cleanup_type);
CREATE INDEX idx_cleanup_audit_status ON cleanup_audit(status);
CREATE INDEX idx_cleanup_audit_created ON cleanup_audit(created_at);
```

### 7.2 审计日志保留

```python
CLEANUP_AUDIT_RETENTION = 365  # 保留1年

def cleanup_old_audit_logs(retention_days: int = CLEANUP_AUDIT_RETENTION):
    """清理超过保留期的审计日志"""
    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted = db.execute("""
        DELETE FROM cleanup_audit
        WHERE created_at < ?
    """, [cutoff.strftime("%Y-%m-%d")])
    return {'deleted': deleted}
```

---

## 八、清理报告（用户通知）

### 8.1 报告内容

每次清理完成后，生成清理报告：

```python
class CleanupReport:
    """清理报告"""

    def __init__(self, cleanup_type: str, data_type: str):
        self.cleanup_type = cleanup_type      # 'daily'/'weekly'/'monthly'/'storage_limit'
        self.data_type = data_type            # 'duckdb_daily_kline'等
        self.started_at = datetime.now()
        self.completed_at = None
        self.status = 'running'
        self.records_before = 0
        self.records_after = 0
        self.bytes_freed = 0
        self.error_message = None

    def to_dict(self) -> dict:
        return {
            'cleanup_type': self.cleanup_type,
            'data_type': self.data_type,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'duration_seconds': (self.completed_at - self.started_at).total_seconds() if self.completed_at else None,
            'records_before': self.records_before,
            'records_after': self.records_after,
            'records_deleted': self.records_before - self.records_after,
            'bytes_freed': self.bytes_freed,
            'error_message': self.error_message,
        }
```

### 8.2 报告存储

```python
def save_cleanup_report(report: CleanupReport):
    """保存清理报告"""
    conn = sqlite3.connect(SQLITE_PATH)
    conn.execute("""
        INSERT INTO cleanup_audit (
            cleanup_type, data_type, started_at, completed_at,
            status, records_before, records_after, bytes_freed, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        report.cleanup_type, report.data_type,
        report.started_at.isoformat(),
        report.completed_at.isoformat() if report.completed_at else None,
        report.status, report.records_before, report.records_after,
        report.bytes_freed, report.error_message
    ])
    conn.commit()
    conn.close()

def notify_user_about_cleanup(report: CleanupReport):
    """通知用户清理结果"""
    if report.status == 'completed':
        message = (
            f"✅ 数据清理完成\n"
            f"- 类型：{report.cleanup_type}\n"
            f"- 释放空间：{report.bytes_freed / 1024 / 1024:.1f} MB\n"
            f"- 删除记录：{report.records_before - report.records_after} 条"
        )
    else:
        message = (
            f"❌ 数据清理失败\n"
            f"- 类型：{report.cleanup_type}\n"
            f"- 错误：{report.error_message}"
        )
    # 发送通知（WebSocket/Email等）
    send_notification(message)
```

---

## 九、用户可配置选项（v1.2）

### 9.1 可配置项

```python
# 用户可配置的保留期限
USER_CONFIGURABLE_RETENTION = {
    # DuckDB日K线保留期限（年）
    'duckdb_daily_kline_years': {
        'type': 'int',
        'default': 2,
        'min': 1,
        'max': 5,
        'description': '日K线保留期限（1-5年）'
    },

    # DuckDB分钟K线保留期限（天）
    'duckdb_minute_kline_days': {
        'type': 'int',
        'default': 14,
        'min': 7,
        'max': 30,
        'description': '分钟K线保留期限（7-30天）'
    },

    # 预测数据保留期限（天）
    'prediction_retention_days': {
        'type': 'int',
        'default': 90,
        'min': 30,
        'max': 180,
        'description': '预测数据保留期限（30-180天）'
    },

    # 是否启用自动清理
    'auto_cleanup_enabled': {
        'type': 'bool',
        'default': True,
        'description': '是否启用自动清理'
    },

    # 存储告警阈值
    'storage_warning_threshold': {
        'type': 'float',
        'default': 0.80,
        'min': 0.50,
        'max': 0.95,
        'description': '存储告警阈值（50%-95%）'
    },
}
```

### 9.2 用户界面

```python
# 用户配置页面路由
@router.get("/settings/cleanup")
async def get_cleanup_settings():
    """获取清理配置"""
    config = load_user_config('cleanup')
    return {
        'retention': config.get('retention', DEFAULT_RETENTION),
        'auto_cleanup': config.get('auto_cleanup', True),
        'thresholds': config.get('thresholds', DEFAULT_THRESHOLDS),
    }

@router.post("/settings/cleanup")
async def update_cleanup_settings(settings: CleanupSettings):
    """更新清理配置"""
    # 验证配置
    validate_settings(settings)

    # 保存配置
    save_user_config('cleanup', settings.dict())

    # 如果修改了保留期限，立即执行一次清理
    if settings.retention_changed:
        await trigger_cleanup(settings.retention)

    return {'status': 'ok'}
```

---

## 十、实施计划（v1.2）

### 10.1 实施阶段

```
v1.0: 基础方案设计
├── ✅ 设计原则
├── ✅ 分级存储架构
└── ✅ 保留策略

v1.1: 清理机制实现
├── ✅ 每日/每周/每月清理调度
├── ✅ 分批执行
├── ✅ 幂等性保证
└── ✅ 断点续跑

v1.2: 安全保护机制
├── ✅ 存储上限保护
├── ✅ 清理前备份
├── ✅ 审计日志
├── ✅ 清理报告
└── ✅ 用户可配置

v1.3: DuckDB K线清理
├── ✅ 周K归档表设计
├── ✅ 先归档后删除
├── ✅ 透明查询路由
└── ✅ 分批删除

v1.4: 回测报告存档
├── ✅ 独立SQLite存储
├── ✅ 1年/100条上限
└── ✅ 超限自动清理

v1.5: 历史数据填充
├── ⚠️ 首次部署填充
├── ⚠️ 增量更新
└── ⚠️ 断点续跑

v1.6: 预测数据存档
├── ✅ 涨幅预测保留
├── ✅ 上涨概率保留
└── ✅ 透明查询路由

v1.7: 与data_manager集成
└── ✅ 整合到数据管理模块
```

### 10.2 迁移指南

```python
# 从旧存储迁移到新架构
def migrate_to_new_cleanup():
    """迁移到新的清理架构"""

    # 1. 创建审计日志表
    db.execute(CREATE_CLEANUP_AUDIT_SQL)

    # 2. 创建周K归档表
    duckdb.execute(CREATE_WEEKLY_ARCHIVE_SQL)

    # 3. 迁移现有cp_history到新表
    migrate_cp_history()

    # 4. 配置清理任务
    setup_cleanup_scheduler()

    # 5. 验证数据完整性
    verify_data_integrity()

    return {'status': 'migrated'}
```

---

## 十一、专家评审意见落实（v1.2）

### 11.1 评审意见汇总

| 专家 | 意见 | 落实情况 |
|------|------|---------|
| 专家A | P0数据（持仓/交易）必须永不删除 | ✅ 已落实，P0优先级数据永不删除 |
| 专家B | 建议先备份后清理，防止误删 | ✅ 已落实，pre_cleanup_backup() |
| 专家C | 清理必须分批执行，避免IO阻塞 | ✅ 已落实，BATCH_SIZE控制 |
| 专家D | 周K归档透明查询，用户无感知 | ✅ 已落实，query_daily_kline()路由 |
| 专家E | 存储上限必须硬性保护 | ✅ 已落实，STORAGE_PROTECTION |
| 专家F | 审计日志必须保留至少1年 | ✅ 已落实，cleanup_audit保留365天 |
| 专家G | 用户必须有配置权 | ✅ 已落实，USER_CONFIGURABLE_RETENTION |
| 专家H | 清理任务必须幂等可重入 | ✅ 已落实，cleanup_with_idempotency() |
| 专家I | 建议分钟K线按股票池分级保留 | ✅ 已落实，核心池/活跃池分开保留期 |

---

## 十二、数据保留速查表（v1.4）

| 数据类型 | 存储位置 | 默认保留 | 最大保留 | 可配置 | 清理触发 |
|---------|---------|---------|---------|-------|---------|
| 持仓 | SQLite | **永久** | - | ❌ | 永不 |
| 交易历史 | SQLite | **永久** | - | ❌ | 永不 |
| 账户信息 | SQLite | **永久** | - | ❌ | 永不 |
| 战力历史 | SQLite | **2年** | 2年 | ❌ | 每年清理 |
| **回测报告** | SQLite | **1年/100条** | 1年/100条 | ❌ | **超限自动清理** |
| 日K线 | DuckDB | **2年** | 5年 | ✅ | 每日02:00 |
| 日K线归档 | DuckDB | **永久** | - | ❌ | 永不 |
| 分钟K线 | DuckDB | **14天** | 14天 | ✅ | 每日02:00 |
| 涨幅预测 | SQLite | 90天 | 180天（最大上限） | ✅ | 每日02:00 |
| 上涨概率预测 | SQLite | 90天 | 180天（最大上限） | ✅ | 每日02:00 |
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

TradeSnake数据生命周期管理核心（v1.7）：

1. **P0用户数据（持仓/交易/账户）**：**永不删除**
2. **战力历史(cp_history)**：保留**2年**（约44MB），足够日常动量计算
3. **回测报告(backtest_reports)**：保留**1年/100条**（超限自动清理最旧记录），用户手动分析
4. **日K线(DuckDB)**：保留**2年**（约200MB），超限降采样归档到周K表，**透明查询路由**
5. **分钟K线(DuckDB)**：保留**14天**（核心+活跃池约184MB，1分钟粒度），**分批删除**
6. **预测结果(SQLite)**：涨幅/上涨概率预测保留**90天**（约10MB），用于回测验证
7. **SQLite历史数据**：price_history保留2年（回测器使用，**计划迁移到DuckDB**），alerts保留90天
8. **缓存**：基于TTL自动清理（1-7天），用户配置跳过清理
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
        # 删除最旧记录
        cursor.execute("""
            DELETE FROM backtest_reports
            WHERE id = (SELECT MIN(id) FROM backtest_reports)
        """)
        logger.info("回测报告超限，删除最旧记录")

    # 检查日期是否超限
    cutoff = (datetime.now() - timedelta(days=BACKTEST_REPORT_RETENTION['max_age_days'])).strftime("%Y-%m-%d")
    cursor.execute("DELETE FROM backtest_reports WHERE created_at < ?", [cutoff])
    logger.info(f"回测报告清理：删除{cutoff}之前的记录")

    # 插入新记录
    report_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO backtest_reports (report_id, created_at, ...)
        VALUES (?, ?, ...)
    """, [report_id, datetime.now().isoformat(), ...])

    conn.commit()
    conn.close()

    return report_id
```

---

## 十五、待补充功能：历史数据填充

> **v1.5更新**：新增历史数据填充功能说明

### 15.1 功能缺失说明

当前方案（v1.4）只覆盖了数据**清理**生命周期，但缺少**数据初始化/填充**的完整方案。

**已知填充场景**：
- 新系统首次部署时，需要从Tushare填充历史K线数据
- DuckDB日K线表为空时，预测分析模块无法工作
- 股票池扩大后，需要为新增股票填充历史数据

### 15.2 现有填充脚本

已在 `scripts/fill_kline_data.py` 实现基础填充功能：

```python
# 用法示例
python scripts/fill_kline_data.py              # 填充所有股票
python scripts/fill_kline_data.py --limit 50   # 只填充前50只
python scripts/fill_kline_data.py --code 000001 # 只填充指定股票
python scripts/fill_kline_data.py --days 300   # 获取300天历史数据
```

**数据源**：`TushareProvider.get_daily_kline()`

**目标表**：`daily_kline` (DuckDB)

**转换逻辑**：将Tushare格式转换为DuckDB格式（列名映射：`vol` → `volume`，日期格式转换等）

### 15.3 填充策略建议

| 场景 | 建议方式 | 覆盖范围 |
|-----|---------|---------|
| 首次部署 | 批量填充 | 全市场/核心池 |
| 日常增量 | 增量更新 | 新增股票 + 近期数据 |
| 预测需求 | 按需填充 | 单只股票多日历史 |

### 15.4 待集成到数据管理模块

填充功能尚未作为正式模块集成到数据管理方案中，建议后续补充：

1. **配置化**：在 `data_manager/config.py` 中添加填充策略配置
2. **定时任务**：将 `fill_kline_data.py` 改造为可调度的增量更新
3. **状态追踪**：在 SQLite 中记录数据填充状态，支持断点续跑
4. **与清理配合**：确保填充的数据量在清理策略的保留范围内

---

## 十六、架构约束与边界

1. **数据来源单一**：所有外部数据必须经由 `data_manager/providers/` 接入
2. **存储边界清晰**：DuckDB 只存储K线数据，SQLite 存储业务数据
3. **清理优先于填充**：当存储满时，清理策略生效，填充功能应尊重清理结果
4. **预测模块独立**：预测引擎只依赖K线数据，不直接访问业务数据库
