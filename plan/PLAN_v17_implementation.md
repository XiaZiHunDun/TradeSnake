# TradeSnake v17 实施计划（修订版）

**计划时间**：2026-04-02
**计划内容**：风险预警 + 数据库迁移 + 回测模块
**评审状态**：✅ 已采纳专家意见

---

## 修订说明

根据五位专家评审意见，主要调整：

| 模块 | 原方案 | 修订后 | 原因 |
|------|--------|--------|------|
| 回测优先级 | 🟠 中 | 🟡 低 | 存在前视偏差/幸存者偏差，需先修复 |
| 预警机制 | 基础版 | **增加去重+冷却期** | 防止预警风暴 |
| 数据库 | SQLite | **启用WAL模式** | 显著提升并发性能 |
| 回测 | 简单回测 | **修复前视偏差+免责声明** | 避免误导决策 |
| 实施顺序 | 回测→预警 | **预警→回测** | 先让预警可用 |

---

## 一、风险预警通知系统

### 1.1 现状分析

当前系统只有文本警告提示（如"⚠️ 换股成本提醒"），没有真正的预警机制。

### 1.2 预警触发规则（初版）

```python
# 持仓风险预警规则
WARN_RULES = {
    # 战力下降预警（单日）
    'cp_drop': {
        'threshold': 15,      # 战力单日下降超过15分（保守阈值）
        'level': 'warning',
        'cooldown_hours': 24,  # 冷却期：24小时内不重复预警
    },
    'cp_drop_danger': {
        'threshold': 25,      # 战力单日下降超过25分
        'level': 'danger',
        'cooldown_hours': 24,
    },

    # 连续下跌趋势预警（新增）
    'cp_trend_drop': {
        'threshold_days': 5,    # 连续5天
        'threshold_drop': 10,    # 累计下降10分
        'level': 'warning',
        'cooldown_hours': 48,   # 冷却期更长
    },

    # 持仓风险等级变化
    'risk_level_up': {
        'level': 'warning',
        'cooldown_hours': 24,
    },

    # 换股建议变化（更保守）
    'swap_signal': {
        'cp_diff_threshold': 15,  # 目标股战力比当前高15分以上（原来10分太敏感）
        'net_profit_threshold': 0,
        'cooldown_hours': 24,
    },

    # 新股推荐机会
    'new_opportunity': {
        'cp_threshold': 80,
        'rank_change': 10,
        'cooldown_hours': 12,  # 机会类预警冷却期可以短一些
    }
}
```

### 1.3 预警去重机制（核心改进）

```python
class AlertDeduplicator:
    """预警去重器：防止预警风暴"""

    def __init__(self):
        self.recent_alerts = {}  # {alert_key: timestamp}

    def should_generate(self, alert_type: str, code: str, level: str) -> bool:
        """检查是否应该生成预警"""
        key = f"{alert_type}:{code}:{level}"

        if key in self.recent_alerts:
            last_time = self.recent_alerts[key]
            cooldown = self._get_cooldown(alert_type)

            if time.time() - last_time < cooldown:
                return False  # 还在冷却期

        self.recent_alerts[key] = time.time()
        return True

    def _get_cooldown(self, alert_type: str) -> int:
        """获取各类型预警的冷却时间（秒）"""
        cooldowns = {
            'cp_drop': 24 * 3600,      # 24小时
            'cp_drop_danger': 24 * 3600,
            'cp_trend_drop': 48 * 3600,  # 48小时
            'swap_signal': 24 * 3600,
            'new_opportunity': 12 * 3600,
        }
        return cooldowns.get(alert_type, 24 * 3600)
```

### 1.4 预警过期策略

```python
# 预警自动过期配置
ALERT_CONFIG = {
    'auto_expire_days': 7,   # 7天后自动过期
    'keep_max': 100,          # 最多保留100条
    'read_expire_days': 3,    # 已读预警3天后删除
}
```

### 1.5 API 设计

```python
# 获取当前预警列表
GET /api/alerts
Response: {
    "alerts": [
        {
            "id": 1,
            "type": "cp_drop",
            "code": "600519",
            "name": "贵州茅台",
            "level": "warning",
            "message": "战力下降15.3分，当前战力82.5",
            "detail": "较前一交易日下降18.5%",
            "suggestion": "建议关注，若持续下跌考虑换股",
            "is_read": false,
            "created_at": "2026-04-02T15:30:00",
            "expires_at": "2026-04-09T15:30:00"
        },
        ...
    ],
    "unread_count": 3,
    "total_count": 15
}

# 预警聚合摘要（新增）
GET /api/alerts/summary
Response: {
    "total": 5,
    "unread": 2,
    "by_level": {"danger": 1, "warning": 3, "info": 1},
    "by_type": {"cp_drop": 2, "swap_signal": 1, "new_opportunity": 2},
    "latest_time": "2026-04-02T15:30:00"
}

# 标记预警为已读（支持批量）
POST /api/alerts/read
Body: {"alert_ids": [1, 2, 3]}  # 批量
Body: {"all": true}  # 全部已读

# 获取持仓预警状态
GET /api/holdings/alerts
Response: {
    "holdings": [
        {
            "code": "600519",
            "name": "贵州茅台",
            "current_cp": 82.5,
            "previous_cp": 97.8,
            "cp_drop": 15.3,
            "drop_rate": 15.6,
            "risk_level": "中等",
            "alerts": [
                {"type": "cp_drop", "level": "warning", "created_at": "2026-04-02T15:30:00"}
            ]
        },
        ...
    ]
}

# 预警配置
GET /api/alerts/config
POST /api/alerts/config
{
    "enabled": true,
    "sound_enabled": true,
    "rules": {
        "cp_drop_threshold": 15,
        "new_opportunity_enabled": true,
        "swap_signal_enabled": true
    }
}
```

### 1.6 前端展示

```
┌─────────────────────────────────────┐
│ 🔔 预警通知 (2条未读)                 │
├─────────────────────────────────────┤
│ ⚠️ 贵州茅台战力下降 15.3分            │
│    当前战力: 82.5 (昨日: 97.8)       │
│    建议: 关注，若持续下跌考虑换股      │
│    [查看详情] [忽略] [24h后再提醒]      │
├─────────────────────────────────────┤
│ 💡 新机会：宁德时代战力突破85分        │
│    战力榜排名上升15位                 │
│    [查看详情] [加入自选]              │
└─────────────────────────────────────┘
```

---

## 二、数据库迁移

### 2.1 数据库选型

**SQLite + WAL模式**（已采纳专家建议）

| 配置项 | 值 | 说明 |
|--------|-----|------|
| journal_mode | WAL | Write-Ahead Logging，提升并发性能 |
| synchronous | NORMAL | 平衡安全与性能 |
| timeout | 10.0 | 写入超时10秒 |

```python
class Database:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(
            db_path,
            timeout=10.0,
            check_same_thread=False
        )
        # 启用WAL模式（必须！）
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_tables()

    def _init_tables(self):
        """初始化表结构"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                code TEXT PRIMARY KEY,
                name TEXT,
                price REAL,
                pe REAL,
                roe REAL,
                ...
                updated_at TEXT
            )
        """)

        # ... 其他表
```

### 2.2 数据模型

```sql
-- 股票表
CREATE TABLE stocks (
    code TEXT PRIMARY KEY,
    name TEXT,
    price REAL,
    pe REAL,
    roe REAL,
    net_profit_growth REAL,
    revenue_growth REAL,
    change_pct REAL,
    total_cp REAL,
    risk_score REAL,
    data_quality TEXT,
    updated_at TEXT
);

-- 持仓表
CREATE TABLE holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT,
    quantity INTEGER,
    cost_price REAL,
    created_at TEXT,
    updated_at TEXT
);

-- 预警表
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    level TEXT,
    message TEXT,
    code TEXT,
    is_read INTEGER DEFAULT 0,
    created_at TEXT,
    expires_at TEXT
);

-- 战力历史表
CREATE TABLE cp_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    name TEXT,
    total_cp REAL,
    rank INTEGER,
    recorded_at TEXT,
    UNIQUE(code, recorded_at)
);

-- 自选股表
CREATE TABLE watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT,
    added_at TEXT
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_alerts_unread ON alerts(is_read, created_at);
CREATE INDEX IF NOT EXISTS idx_cp_history_date_code ON cp_history(recorded_at, code);
CREATE INDEX IF NOT EXISTS idx_cp_history_code ON cp_history(code);
```

### 2.3 迁移方案（四阶段）

| 阶段 | 内容 | 状态 |
|------|------|------|
| 1 | SQLite搭建 + 启用WAL | 待实施 |
| 2 | 历史数据迁移 + 校验 | 待实施 |
| 3 | 双写验证 | 待实施 |
| 4 | 切换读 + 保留JSON备份 | 待实施 |

```python
def migrate_with_validation():
    """带校验的迁移"""
    db = Database()

    # 迁移前检查
    json_count = count_json_records()
    print(f"JSON记录数: {json_count}")

    # 迁移
    migrated = 0
    errors = []
    for record in json_records:
        try:
            db.insert_cp_history(record)
            migrated += 1
        except Exception as e:
            errors.append(f"{record['code']}: {e}")

    # 迁移后校验
    db_count = db.count_cp_history()
    print(f"迁移成功: {migrated}, 失败: {len(errors)}")
    print(f"数据库记录数: {db_count}")

    if migrated != json_count:
        print(f"⚠️ 记录数不一致！差异: {abs(migrated - json_count)}")
        # 自动回滚
        rollback()

    return migrated, errors
```

---

## 三、回测模块（优先级降低）

### 3.1 重要声明

> ⚠️ **回测模块存在已知局限性，需谨慎解读结果**

- 本系统为个人工具，回测结果仅供参考
- 过去表现不代表未来收益
- 回测未考虑滑点、冲击成本、分红再投资
- 建议结合预警系统综合决策

### 3.2 回测设计原则

| 原则 | 说明 |
|------|------|
| **避免前视偏差** | 只用当时可获得的数据（财报发布日期对齐） |
| **避免幸存者偏差** | 纳入历史退市股票 |
| **明确免责声明** | 回测报告必须包含风险提示 |
| **保守阈值** | 战力差阈值提高到15分（原10分太敏感） |

### 3.3 数据对齐方案

```python
class Backtest:
    def get_stocks_with_available_data(self, as_of_date: str) -> List[StockCP]:
        """
        获取as_of_date时点可获得的战力数据

        关键：只能用该日期之前已发布的财报数据
        - 年报：次年4月底前发布
        - 季报：次季度首月前发布
        """
        # 获取财报发布日期
        financial_reports = self.get_financial_report_dates(as_of_date)

        # 筛选可用数据
        available = []
        for stock in self.all_stocks:
            latest_report = self.get_latest_report_before(stock.code, as_of_date)
            if latest_report and self.is_report_released(latest_report, as_of_date):
                # 使用该财报数据重新计算战力
                stock_cp = self.recalculate_cp(stock, latest_report)
                available.append(stock_cp)

        return available
```

### 3.4 回测指标

```python
class BacktestMetrics:
    @staticmethod
    def calculate(returns: List[float], days: int) -> dict:
        """计算回测评估指标"""
        import numpy as np

        returns_arr = np.array(returns)
        total_return = (np.prod(1 + returns_arr) - 1) * 100

        # 年化收益（修正：基于实际天数）
        if days >= 365:
            annual_return = ((1 + np.mean(returns_arr)) ** (365 / days) - 1) * 100
        else:
            annual_return = None  # 不足一年不显示年化

        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': np.std(returns_arr) * 100,
            'sharpe_ratio': np.mean(returns_arr) / np.std(returns_arr) if np.std(returns_arr) > 0 else 0,
            'max_drawdown': calculate_max_drawdown(returns_arr) * 100,
            'calmar_ratio': annual_return / abs(calculate_max_drawdown(returns_arr)) if annual_return and calculate_max_drawdown(returns_arr) != 0 else 0,
            'win_rate': len(returns_arr[returns_arr > 0]) / len(returns_arr) * 100,
        }
```

### 3.5 API 设计

```python
# 简单回测（修复版）
GET /api/backtest/simple
Query: start_date=2025-01-01&end_date=2025-12-31&holding_days=30

Response: {
    "strategy": "战力TOP10持有30天",
    "period": "2025-01-01 ~ 2025-12-31",
    "total_return": 25.3,
    "annual_return": 25.3,
    "volatility": 12.5,
    "sharpe_ratio": 1.5,
    "max_drawdown": -8.2,
    "calmar_ratio": 3.1,
    "win_rate": 72.5,
    "benchmark_return": 15.2,
    "excess_return": 10.1,
    "survivorship_note": "约5%股票已退市，收益可能被高估",
    "disclaimer": "⚠️ 回测结果仅供参考，不构成投资建议。过去表现不代表未来收益。",
    "monthly_returns": [2.1, -1.5, 3.2, ...],
    "details": [...]
}

# 对比回测
GET /api/backtest/compare
Query: start_date=2025-01-01&end_date=2025-12-31

Response: {
    "top20_return": 25.3,
    "top50_return": 22.1,
    "top100_return": 18.5,
    "conclusion": "战力越高，未来收益越好（验证公式有效）",
    "disclaimer": "⚠️ 注意：约5%股票已退市，实际收益可能偏低"
}
```

---

## 四、实施优先级（调整后）

| 阶段 | 内容 | 优先级 | 预计工时 |
|------|------|--------|---------|
| v17.1 | SQLite数据库 + WAL模式 + 迁移脚本 | 🔴 最高 | 4h |
| v17.2 | 预警API + 去重/冷却机制 | 🔴 高 | 4h |
| v17.3 | 前端预警展示 | 🟠 中 | 3h |
| v17.4 | 回测API v1（修复前视偏差后） | 🟡 低 | 5h |
| v17.5 | 前端回测报告 | 🟡 低 | 2h |

**调整说明**：
1. 回测优先级从🟠降到🟡，因为存在前视偏差问题需先修复
2. 数据库启用WAL是必须项
3. 预警增加去重/冷却机制

---

## 五、风险与应对

| 风险 | 应对措施 |
|------|----------|
| 预警风暴 | ✅ 去重机制 + 冷却期 |
| 回测误导 | ✅ 免责声明 + 幸存者偏差说明 |
| 数据迁移丢失 | ✅ 保留JSON备份 + 迁移校验 |
| SQLite并发 | ✅ WAL模式 + timeout=10s |

---

## 六、后续优化方向

| 版本 | 内容 |
|------|------|
| v17.x | 根据实际使用调整预警阈值 |
| v18.0 | 回测增加多基准对比（中证500、行业指数） |
| v18.x | WebSocket实时预警推送 |
| v19.0 | 支持Webhook/邮件通知 |

---

*—— 计划制定者*
*计划时间：2026-04-02*
*修订版本：采纳五位专家评审意见*
