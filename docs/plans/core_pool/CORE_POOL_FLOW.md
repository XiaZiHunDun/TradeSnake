# 核心池流程状态文档 v19.9.5

> 核心池是 TradeSnake 分析系统的核心，涵盖股票池管理、战力计算、预测分析、推荐决策等关键功能。
> 本文档记录核心池的整体流程、模块对接、数据流转和问题追踪。

---

## 一、核心池概述

### 1.1 什么是核心池

核心池（Core Pool）是系统中战力分析的核心范围，包含：
- **核心池（Core）**: 沪深主板中流动性最好、质地最优的股票（约100-300只）
- **活跃池（Active）**: 有交易机会的活跃股票（约500只）

### 1.2 产品边界

与全项目一致，战力主算与 `stock_selector` 协同的分析集合以 **沪深主板** 为边界。

---

## 二、核心池数据流

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              核心池整体流程                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐        │
│  │  stock_selector  │────▶│   data_manager   │────▶│    cp_engine     │        │
│  │   (股票池管理)    │     │    (数据供给)     │     │    (战力计算)     │        │
│  └──────────────────┘     └──────────────────┘     └──────────────────┘        │
│           │                                                 │                   │
│           │                                                 ▼                   │
│           │                                        ┌──────────────────┐        │
│           │                                        │   recommender    │        │
│           │                                        │   (融合决策)      │        │
│           │                                        └──────────────────┘        │
│           │                                                 │                   │
│           ▼                                                 ▼                   │
│  ┌──────────────────┐                            ┌──────────────────┐        │
│  │ market_snapshot   │                            │   simulator       │        │
│  │  (市场快照)       │                            │   (模拟交易)       │        │
│  └──────────────────┘                            └──────────────────┘        │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐         │
│  │                           本地存储                                  │         │
│  │  DuckDB (日K线/分钟K线)  │  SQLite (stocks/cp_history/prediction) │         │
│  └──────────────────────────────────────────────────────────────────┘         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、模块详解

### 3.1 stock_selector (股票池管理)

**文件**: `backend/stock_selector/`

**职责**:
- 确定哪些股票属于核心池/活跃池/观察池
- 根据指数成分股（HS300/ZZ500/ZZ1000）和成交量排名划分

**入池标准**:
| 条件 | 股票池 |
|------|--------|
| HS300 成分股 | 核心池 |
| ZZ500 成分股 | 核心池 |
| Top 300 日均成交额 | 核心池 |
| ZZ1000 成分股 | 活跃池 |
| Top 500 日均成交额 | 活跃池 |

**关键文件**:
- `stock_selector.py`: 主类，管理股票池
- `pool_manager.py`: 池管理逻辑
- `rebalancer.py`: 池再平衡逻辑
- `market_snapshot.py`: 市场快照，计算成交量排名

**输出**:
```python
{
    'core_stocks': Set[str],   # 核心池代码集合
    'active_stocks': Set[str], # 活跃池代码集合
    'analysable_codes': Set[str],  # 可分析股票 (core + active)
}
```

### 3.2 data_manager (数据供给)

**文件**: `backend/data_manager/`

**职责**:
- 从多个数据源获取市场数据和财务数据
- 管理本地存储（Redis/DuckDB/SQLite）

**数据源**:
| 数据源 | 用途 |
|--------|------|
| akshare | 实时行情 |
| 腾讯API | 实时价格 |
| 东方财富 | 财务数据 |
| Tushare | 日K线、历史数据 |

**关键文件**:
- `manager.py`: 统一数据访问接口
- `fetcher.py`: 数据获取器
- `duckdb_store.py`: DuckDB 存储（日K线、分钟K线）
- `prediction_store.py`: 预测结果存储（SQLite）
- `cp_history_store.py`: 战力历史存储（SQLite）

**输出给 cp_engine**:
```python
{
    'code': '000001',
    'name': '平安银行',
    'price': 12.34,
    'pe': 5.2,
    'roe': 12.5,
    'net_profit_growth': 15.3,
    'revenue_growth': 8.2,
    'change_pct': 1.23,
    'pb': 0.85,
    'gross_margin': 35.2,
    # ... 更多字段
}
```

### 3.3 cp_engine (战力计算)

**文件**: `backend/engine/cp_engine/`

**职责**:
- 计算股票综合战力评分
- 各维度评分：成长(30%)、价值(25%)、质量(20%)、动量(15%)

**战力公式**:
```
总战力 = (成长分×30% + 价值分×25% + 质量分×20% + 动量分×15%) × 风险调整
```

**各因子说明**:
| 因子 | 权重 | 数据来源 |
|------|------|----------|
| 成长分 | 30% | 净利润增速(60%) + 营收增速(40%) |
| 价值分 | 25% | ROE + PE评分 + PEG + PB |
| 质量分 | 20% | 现金流 + 毛利率 + 资产负债率 |
| 动量分 | 15% | 多日动量(60%) + 当日涨跌幅(40%) |

**关键文件**:
- `cp_engine.py`: 战力计算核心
- `indicators.py`: 技术指标
- `risk_analyzer.py`: 风险评估

**输出**: `List[StockCP]`

### 3.4 recommender (融合决策)

**文件**: `backend/recommender/`

**职责**:
- 融合战力评分、涨幅预测、上涨概率
- 生成买入/卖出/换股建议

**融合公式**:
```
融合得分 = 战力分 × 权重 + 涨幅预测 × 权重 + 上涨概率 × 权重
```

**关键文件**:
- `recommend_engine.py`: 推荐引擎
- `fusion.py`: 预测融合逻辑
- `buy_analyzer.py`: 买入分析
- `swap_calculator.py`: 换股计算

### 3.5 simulator (模拟交易)

**文件**: `backend/simulator/`

**职责**:
- 执行模拟交易
- 记录持仓、资金变化

---

## 四、数据存储

### 4.1 DuckDB

**用途**: 历史K线数据存储

**表结构**:
```sql
-- 日K线
daily_kline (
    code VARCHAR(6) NOT NULL,      -- 6位代码 (000001)
    trade_date DATE NOT NULL,       -- YYYY-MM-DD
    open, high, low, close,         -- 价格
    volume, amount,                  -- 成交量/额
    change_pct,                      -- 涨跌幅
    adj_close, adj_factor            -- 复权
)

-- 分钟K线
minute_kline (
    code, trade_time, open, high, low, close, volume, amount
)
```

**数据量**:
- daily_kline: ~2.4M 行
- minute_kline: ~2.4M 行

### 4.2 SQLite

**用途**: 运行时数据存储

**表结构**:
```sql
-- 当前股票数据
stocks (
    code, name, price, pe, roe,
    net_profit_growth, revenue_growth,
    growth_score, value_score, quality_score, momentum_score, total_cp
)

-- 战力历史
cp_history (
    code, name, price, total_cp,
    growth_score, value_score, quality_score, momentum_score,
    rank, recorded_at
)

-- 涨幅预测
gain_predictions (
    code, name, predicted_gain_3d/5d, confidence, recorded_at
)

-- 上涨概率预测
probability_predictions (
    code, name, up_probability_3d/5d, confidence, risk_level, recorded_at
)
```

---

## 五、API 端点

### 5.1 核心池相关 API

| API | 方法 | 说明 |
|-----|------|------|
| `/api/cp/top` | GET | 获取战力榜TOP N |
| `/api/cp/recommend` | GET | 获取推荐股票 |
| `/api/cp/swap` | GET | 获取换股建议 |
| `/api/prediction/gain/top` | GET | 涨幅预测TOP |
| `/api/prediction/probability/top` | GET | 上涨概率TOP |

### 5.2 推荐融合参数

```bash
# 纯战力排序（原有逻辑）
GET /api/cp/recommend?category=growth&risk_preference=balanced

# 战力+预测融合推荐 (v19.9.5)
GET /api/cp/recommend?fusion=true&risk_preference=balanced
```

---

## 六、代码格式规范

### 6.1 股票代码格式

**标准格式**: 6位无前缀数字 (如 `000001`)

**处理流程**:
```python
def _normalize_code(raw_code: str) -> str:
    """标准化股票代码为6位格式"""
    code = raw_code
    if code.startswith('sh'):
        code = code[2:]
    elif code.startswith('sz'):
        code = code[2:]
    if '.' in code:  # 处理 .SH/.SZ 后缀
        code = code.split('.')[0]
    return code
```

### 6.2 日期格式

**DuckDB**: `YYYY-MM-DD` (如 `2026-04-17`)
**SQLite**: `YYYY-MM-DD` (字符串)
**Tushare API**: `YYYYMMDD` (如 `20260417`)

---

## 七、问题追踪

### 7.1 已解决问题

| 问题 | 严重性 | 修复版本 | 状态 |
|------|--------|----------|------|
| `/api/cp/recommend` 未使用预测融合 | HIGH | v19.9.5 | ✅ 已修复 |
| `SingleStockResponse` 缺少融合字段 | MEDIUM | v19.9.5 | ✅ 已修复 |
| `_normalize_code` 未处理 `.SH/.SZ` 后缀 | MEDIUM | v19.9.5 | ✅ 已修复 |
| `PredictionFusion` 只查询 1 天预测 | MEDIUM | v19.9.5 | ✅ 已修复 |
| `BacktestCompatibilityLayer` SQLite fallback | MEDIUM | v19.9.5 | ✅ 已修复 |
| DuckDB `get_klines` 异常未记录 | MEDIUM | v19.9.5 | ✅ 已修复 |
| DuckDB trade_cal 空 | MEDIUM | v19.9.4 | ✅ 懒加载修复 |

### 7.2 已知问题

| 问题 | 严重性 | 说明 | 解决方案 |
|------|--------|------|----------|
| adj_factor 全为 1.0 | LOW | 复权因子未回填 | 调用 `duckdb.backfill_adj_factor()` |
| DuckDB minute_kline 仅约5天 | LOW | 应保留14天 | 需数据源持续补充 |

---

## 八、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v19.9.5 | 2026-04-17 | 修复预测融合接入、添加融合字段 |
| v19.9.4 | 2026-04-17 | 懒加载修复、adj_factor 回填方法 |
| v19.9.3 | 2026-04-17 | asyncio.Lock、JSON持久化 |
| v19.8 | 2026-04-08 | 预测融合模块上线 |

---

## 九、相关文档

- [战力引擎详细方案](../engine/cp_engine/CP_ENGINE.md)
- [涨幅预测引擎方案](../engine/gain_predictor/GAIN_PREDICTOR.md)
- [上涨概率预测引擎方案](../engine/probability_predictor/PROBABILITY_PREDICTOR.md)
- [数据管理模块方案](../data_manager/DATA_MANAGER_ARCHITECTURE.md)
- [股票池模块方案](../stock_selector/STOCK_SELECTOR_ARCHITECTURE.md)
- [智能推荐模块方案](../recommender/RECOMMENDER_ARCHITECTURE.md)
