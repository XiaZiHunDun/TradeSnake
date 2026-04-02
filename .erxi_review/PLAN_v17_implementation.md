# TradeSnake v17 实施计划

**计划时间**：2026-04-02
**计划内容**：风险预警 + 数据库迁移 + 回测模块
**评审状态**：待评审

---

## 一、风险预警通知系统

### 1.1 现状分析

当前系统只有文本警告提示（如"⚠️ 换股成本提醒"），没有真正的预警机制。

### 1.2 预警触发规则（初版）

```python
# 持仓风险预警规则
WARN_RULES = {
    # 战力下降预警
    'cp_drop': {
        'threshold': 10,      # 战力下降超过10分
        'level': 'warning',   # warning / danger
    },
    'cp_drop_danger': {
        'threshold': 20,      # 战力下降超过20分
        'level': 'danger',
    },

    # 持仓风险等级变化
    'risk_level_up': {
        'level': 'warning',   # 从较低 → 中等/高
    },

    # 换股建议变化
    'swap_signal': {
        'cp_diff_threshold': 10,  # 目标股战力比当前高10分以上
        'net_profit_threshold': 0,  # 换股净收益 > 0
    },

    # 新股推荐机会
    'new_opportunity': {
        'cp_threshold': 80,    # 新上榜且战力 > 80
        'rank_change': 10,     # 排名上升超过10位
    }
}
```

### 1.3 预警逻辑设计

```python
class RiskAlert:
    """风险预警引擎"""

    def __init__(self, rules: dict):
        self.rules = rules
        self.alerts = []  # 当前未处理的预警

    def check_holding(self, holding_code: str, historical_cp: float, current_cp: float) -> Alert:
        """检查持仓股票战力变化"""
        if current_cp < historical_cp:
            drop = historical_cp - current_cp
            if drop >= self.rules['cp_drop_danger']['threshold']:
                return Alert(level='danger', type='cp_drop', ...)
            elif drop >= self.rules['cp_drop']['threshold']:
                return Alert(level='warning', type='cp_drop', ...)
        return None

    def check_market_opportunity(self, top_stocks: List[StockCP]) -> List[Alert]:
        """检查市场新机会"""
        alerts = []
        for stock in top_stocks:
            if stock.total_cp >= 80 and stock.rank_change >= 10:
                alerts.append(Alert(type='opportunity', ...))
        return alerts
```

### 1.4 API 设计

```python
# 获取当前预警列表
GET /api/alerts
Response: {
    "alerts": [
        {"type": "cp_drop", "code": "600519", "level": "warning", "message": "...", "created_at": "..."},
        ...
    ],
    "unread_count": 3
}

# 标记预警为已读
POST /api/alerts/{alert_id}/read

# 获取持仓预警状态
GET /api/holdings/alerts
Response: {
    "holdings": [
        {"code": "600519", "name": "贵州茅台", "cp_drop": 8.5, "risk_level": "中等", "alerts": [...]},
        ...
    ]
}

# 预警配置
GET /api/alerts/config
POST /api/alerts/config
{
    "cp_drop_threshold": 10,
    "enabled": true,
    "sound_enabled": true
}
```

### 1.5 前端展示

```
┌─────────────────────────────────────┐
│ 🔔 预警通知 (3条未读)                 │
├─────────────────────────────────────┤
│ ⚠️ 贵州茅台战力下降 12.3分            │
│    战力: 95 → 82.7                  │
│    [查看详情] [忽略]                  │
├─────────────────────────────────────┤
│ 🔴 招商银行风险等级上升                │
│    较低 → 高风险                      │
│    [查看详情] [忽略]                  │
├─────────────────────────────────────┤
│ 💡 新机会：宁德时代战力突破85分        │
│    战力榜排名上升15位                 │
│    [查看详情] [加入自选]              │
└─────────────────────────────────────┘
```

### 1.6 后续优化方向

| 阶段 | 优化内容 |
|------|---------|
| v1.x | 优化预警触发阈值，根据实际使用调整 |
| v2.0 | 增加WebSocket实时推送 |
| v2.x | 支持Webhook/邮件/钉钉通知 |

---

## 二、数据库迁移

### 2.1 当前问题

| 问题 | 影响 |
|------|------|
| JSON文件存储 | 无法支持复杂查询 |
| 无事务支持 | 并发写入可能损坏 |
| 数据量增长 | 大文件导致性能下降 |
| 无法建索引 | 查询效率低 |

### 2.2 数据库选型

| 数据库 | 优点 | 缺点 | 推荐度 |
|--------|------|------|--------|
| **SQLite** | 零配置、单文件、跨平台、够用 | 并发写入弱 | ⭐⭐⭐⭐⭐ |
| PostgreSQL | 功能强大、并发好 | 需要独立服务 | ⭐⭐⭐⭐ |
| MySQL | 流行、生态好 | 需要独立服务 | ⭐⭐⭐ |
| MongoDB | 文档型、灵活 | 对于本项目过于灵活 | ⭐⭐ |

**推荐方案：SQLite**

理由：
1. **零运维**：单文件数据库，无需安装服务
2. **够用**：本项目数据量（< 100万行）SQLite完全能handle
3. **便携**：数据库就是一个文件，方便备份
4. **成熟稳定**：SQLite是世界上部署最广泛的数据库引擎
5. **支持Full-text搜索**：未来可以做股票名称/代码搜索

### 2.3 迁移方案

#### 阶段一：SQLite双写（兼容过渡）

```python
# 新增 db.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "tradesnake.db"

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                name TEXT,
                quantity INTEGER,
                cost_price REAL,
                updated_at TEXT
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                level TEXT,
                message TEXT,
                code TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                name TEXT,
                total_cp REAL,
                rank INTEGER,
                recorded_at TEXT
            )
        """)

        # 创建索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_stocks_code ON stocks(code)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_code ON cp_history(code)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cp_history_date ON cp_history(recorded_at)")

        self.conn.commit()
```

#### 阶段二：迁移历史数据

```python
def migrate_history_to_db():
    """将历史JSON数据迁移到SQLite"""
    db = Database()

    # 迁移战力历史
    history_file = Path("data/cp_history.json")
    if history_file.exists():
        with open(history_file) as f:
            history = json.load(f)

        for date, stocks in history.items():
            for stock in stocks:
                db.insert_cp_history(
                    code=stock['code'],
                    name=stock['name'],
                    total_cp=stock['total_cp'],
                    rank=stock.get('rank', 0),
                    recorded_at=date
                )

    print("历史数据迁移完成")
```

#### 阶段三：切换读请求到SQLite

```python
def get_stocks_from_db(limit: int = 200) -> List[StockCP]:
    """从SQLite获取股票数据"""
    db = Database()
    cursor = db.conn.execute("SELECT * FROM stocks ORDER BY total_cp DESC LIMIT ?", (limit,))

    stocks = []
    for row in cursor.fetchall():
        stocks.append(StockCP(...))

    return stocks
```

#### 阶段四：移除JSON依赖（可选）

保持JSON作为备份，双保险。

### 2.4 数据模型

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
    created_at TEXT
);

-- 战力历史表
CREATE TABLE cp_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    name TEXT,
    total_cp REAL,
    rank INTEGER,
    recorded_at TEXT
);

-- 自选股表
CREATE TABLE watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT,
    added_at TEXT
);
```

---

## 三、回测模块

### 3.1 目标

用历史战力数据验证"战力值是否能预测股票涨跌"。

### 3.2 回测逻辑

```python
class Backtest:
    """
    简单回测：验证战力公式有效性

    核心假设：如果战力值有效，
    那么高战力股票在未来应该表现更好
    """

    def run_simple_backtest(self,
                          start_date: str,
                          end_date: str,
                          holding_days: int = 30) -> dict:
        """
        简单回测：每月选择战力TOP10，持有30天后看表现

        返回：
        - 策略收益
        - 基准收益（同期沪深300）
        - 超额收益
        """
        results = []

        # 按月获取历史排名
        dates = self.get_monthly_dates(start_date, end_date)

        for i, date in enumerate(dates[:-1]):
            next_date = dates[i + 1]

            # 获取当日战力TOP10
            top10 = self.get_top_stocks(date, limit=10)

            # 计算30天后的收益
            returns = []
            for stock in top10:
                future_price = self.get_price(stock['code'], next_date)
                current_price = self.get_price(stock['code'], date)
                if future_price and current_price:
                    ret = (future_price - current_price) / current_price
                    returns.append(ret)

            avg_return = sum(returns) / len(returns) if returns else 0
            results.append({
                'date': date,
                'strategy_return': avg_return,
                'stocks': [s['code'] for s in top10]
            })

        # 计算总体表现
        total_return = 1
        for r in results:
            total_return *= (1 + r['strategy_return'])

        return {
            'total_return': (total_return - 1) * 100,  # 百分比
            'monthly_returns': [r['strategy_return'] * 100 for r in results],
            'win_rate': len([r for r in results if r['strategy_return'] > 0]) / len(results),
            'details': results
        }
```

### 3.3 回测指标

```python
class BacktestMetrics:
    """回测评估指标"""

    @staticmethod
    def calculate(returns: List[float]) -> dict:
        """计算各种评估指标"""
        import numpy as np

        returns_arr = np.array(returns)

        return {
            'total_return': (np.prod(1 + returns_arr) - 1) * 100,
            'annual_return': ((1 + np.mean(returns_arr)) ** 12 - 1) * 100,
            'volatility': np.std(returns_arr) * 100,
            'sharpe_ratio': np.mean(returns_arr) / np.std(returns_arr) if np.std(returns_arr) > 0 else 0,
            'max_drawdown': calculate_max_drawdown(returns_arr) * 100,
            'win_rate': len(returns_arr[returns_arr > 0]) / len(returns_arr) * 100,
        }
```

### 3.4 API 设计

```python
# 简单回测
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
    "win_rate": 72.5,
    "benchmark_return": 15.2,
    "excess_return": 10.1,
    "monthly_returns": [2.1, -1.5, 3.2, ...],
    "details": [
        {"date": "2025-01-31", "strategy_return": 2.1, "stocks": ["600519", "000858", ...]},
        ...
    ]
}

# 对比回测（不同战力阈值）
GET /api/backtest/compare
Query: start_date=2025-01-01&end_date=2025-12-31

Response: {
    "top20_return": 25.3,
    "top50_return": 22.1,
    "top100_return": 18.5,
    "conclusion": "战力越高，未来收益越好（验证公式有效）"
}

# 个股历史回测
GET /api/backtest/stock/{code}
Query: start_date=2025-01-01

Response: {
    "code": "600519",
    "name": "贵州茅台",
    "period": "2025-01-01 ~ 2025-12-31",
    "total_return": 35.2,
    "cp_vs_return_corr": 0.75,  # 战力与收益相关性
    "conclusion": "该股票战力与收益相关性较高(0.75)"
}
```

### 3.5 前端展示

```
┌─────────────────────────────────────────┐
│ 📊 回测报告：战力TOP10持有30天            │
├─────────────────────────────────────────┤
│ 周期：2024-01-01 ~ 2025-12-31           │
│                                         │
│ 总收益: +25.3%        年化: 25.3%       │
│ 基准收益: +15.2%       超额: +10.1%     │
│                                         │
│ 波动率: 12.5%       夏普比率: 1.52       │
│ 最大回撤: -8.2%      胜率: 72.5%        │
│                                         │
│ 📈 月收益分布                            │
│ ████████████░░░░ +2.1%                │
│ ██████████░░░░░░ -1.5%                │
│ ██████████████░░░ +3.2%                │
│ ...                                     │
├─────────────────────────────────────────┤
│ 结论：高战力股票未来表现优于低战力股票      │
│ ✅ 战力公式有效性：已验证                 │
└─────────────────────────────────────────┘
```

---

## 四、实施优先级

| 阶段 | 内容 | 优先级 | 预计工时 |
|------|------|--------|---------|
| v17.1 | SQLite数据库搭建 + 迁移脚本 | 🔴 高 | 4h |
| v17.2 | 预警API + 基础逻辑 | 🔴 高 | 3h |
| v17.3 | 回测API v1 | 🟠 中 | 4h |
| v17.4 | 前端预警展示 | 🟠 中 | 3h |
| v17.5 | 前端回测报告展示 | 🟡 低 | 2h |

---

## 五、风险与注意事项

| 风险 | 应对 |
|------|------|
| 数据迁移丢失 | 保留JSON作为备份 |
| 回测过拟合 | 限制参数数量，多用简单指标 |
| 预警误报 | 先用宽松阈值，后续迭代调整 |

---

*—— 计划制定者*
*计划时间：2026-04-02*
