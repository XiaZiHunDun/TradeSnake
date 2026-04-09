# 分析引擎模块方案 v19.8

## 概述

分析引擎模块是 TradeSnake 系统的核心计算模块，负责股票战力计算、风险评估、历史追踪，以及新增的预测分析。

**版本**: v19.8 | **状态**: 🔨 完善中

---

## 一、输入输出

### 1.1 战力引擎（cp_engine）

**输入**：

| 来源 | 数据内容 | 说明 |
|------|----------|------|
| data_manager | 股票综合数据（行情+财务） | `get_stock_data_api()` 获取 |
| └─ 行情 | code, name, price, open, high, low, volume, pe, pb, change_pct, market_cap | 实时行情 |
| └─ 财务 | roe, net_profit_growth, revenue_growth, gross_margin, revenue, cashflow, debt_ratio | 财务报表 |
| └─ 增强 | current_ratio, interest_coverage, deducted_net_profit, sector, dividend_yield | 增强指标 |
| data_manager | 历史日K线 | `get_klines_from_duckdb()`，用于计算技术指标（波动率、MA、MACD等） |
| data_manager | 分钟级数据 | `get_minute_ma()`、`get_minute_klines()`，仅核心池盘中使用（实时因子） |
| cp_engine/indicators | 技术指标 | MA、MACD、RSI、波动率等，引擎内部计算 |
| **simulator** | 持仓、资金数据 | 风险评估用（`holdings`, `capital`, `db`） |
| **stock_selector** | 股票池分层 | 核心池+活跃池股票列表，用于确定战力计算范围 |

**输出**：

| 输出内容 | 使用者 |
|----------|--------|
| `List[StockCP]` 战力列表 | recommender（选股依据） |
| 风险评估报告 | recommender/simulator（风险控制） |
| Kelly仓位计算 | recommender（仓位建议） |
| 战力历史记录 | data_manager（持久化存储） |

### 1.2 涨幅预测引擎（gain_predictor）

**输入**：

| 来源 | 数据内容 | 说明 |
|------|----------|------|
| data_manager | 历史日K线 | `get_klines_from_duckdb()` 获取 |
| gain_predictor/features | 特征计算 | 复用 indicators.py |

**输出**：

| 输出内容 | 使用者 |
|----------|--------|
| `GainPrediction` 涨幅预测 | recommender（融合决策） |
| 预测结果持久化 | data_manager/prediction_store（写入90天历史） |

### 1.3 上涨概率预测引擎（probability_predictor）

**输入**：

| 来源 | 数据内容 | 说明 |
|------|----------|------|
| data_manager | 历史日K线 | `get_klines_from_duckdb()` 获取 |
| probability_predictor/features | 特征计算 | 复用 indicators.py |

**输出**：

| 输出内容 | 使用者 |
|----------|--------|
| `ProbabilityPrediction` 上涨概率 | recommender（融合决策） |
| 预测结果持久化 | data_manager/prediction_store（写入90天历史） |

### 1.4 各引擎输出汇总

| 引擎 | 输出数据结构 | 使用者 |
|------|-------------|--------|
| cp_engine | `List[StockCP]` | recommender、simulator |
| cp_engine | 战力历史记录 | data_manager（cp_history，backtester间接读取） |
| gain_predictor | `GainPrediction` | recommender |
| gain_predictor | 预测结果持久化 | prediction_store（90天历史） |
| probability_predictor | `ProbabilityPrediction` | recommender |
| probability_predictor | 预测结果持久化 | prediction_store（90天历史） |

---

## 二、模块结构

```
backend/engine/
├── __init__.py                    # 统一导出
│
├── cp_engine/                     # 战力引擎
│   ├── __init__.py
│   ├── cp_engine.py              # 战力计算核心
│   ├── constants.py               # 常量配置
│   ├── indicators.py              # 技术指标
│   ├── cache.py                   # 因子级缓存
│   ├── parallel.py                # 并行计算
│   ├── history.py                 # 战力历史记录
│   ├── refresh_strategy.py        # 刷新策略
│   ├── trading_time.py            # 交易时间判断
│   └── risk_analyzer.py           # 风险评估器
│
├── gain_predictor/                # 涨幅预测引擎
│   ├── __init__.py
│   ├── predictor.py               # 预测器
│   └── features.py                # 特征计算
│
└── probability_predictor/          # 上涨概率预测引擎
    ├── __init__.py
    ├── predictor.py               # 预测器
    └── features.py                # 特征计算
```

---

## 三、引擎概览

| 引擎 | 职责 | 数据需求 | 更新频率 |
|------|------|----------|----------|
| **cp_engine** | 战力分析 | 实时行情 + 财务数据 | 每日收盘后 |
| **gain_predictor** | 涨幅预测 | K线技术指标 | 每日一次 |
| **probability_predictor** | 上涨概率 | K线技术指标 | 每日一次 |

---

## 四、架构图

```
                          DataManager
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌─────────────────────┐
│  cp_engine    │     │gain_predictor   │     │probability_predictor│
│  (战力引擎)    │     │  (涨幅预测)     │     │   (上涨概率)        │
│               │     │                 │     │                     │
│ - 实时行情    │     │ - 历史日K线    │     │ - 历史日K线        │
│ - 财务数据    │     │ - 技术指标     │     │ - 技术指标         │
│ - 技术指标    │     │ - 规则预测     │     │ - 规则预测         │
└───────┬───────┘     └────────┬────────┘     └──────────┬──────────┘
        │                       │                        │
        └───────────────────────┼────────────────────────┘
                                │
                       ┌────────▼─────────┐
                       │   recommender    │
                       │   （融合决策）    │
                       └──────────────────┘
```

---

## 五、每日执行流程

### 5.1 收盘后执行顺序（T日 ~15:30）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         T日收盘后（约15:30-16:00）                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. stock_selector                                                      │
│     └── 执行盘后批处理：池再平衡、晋级/降级、ST扫描                      │
│         └── 触发回调：通知 engine/recommender 池状态变化                  │
│                                                                         │
│  2. cp_engine（战力计算）                                               │
│     ├── 接收：stock_selector 池状态变化回调                              │
│     ├── 获取：stock_selector 核心池+活跃池列表                           │
│     ├── 获取：data_manager 股票综合数据 + 历史K线                        │
│     ├── 计算：多维度战力评分（成长/价值/质量/动量/实时）                  │
│     ├── 输出：StockCP 列表 → recommender                                 │
│     └── 持久化：战力历史 → data_manager/cp_history（2年）               │
│                                                                         │
│  3. gain_predictor（涨幅预测）                                          │
│     ├── 获取：data_manager 历史日K线                                    │
│     ├── 计算：基于技术指标的规则模型预测                                 │
│     ├── 输出：GainPrediction → recommender                              │
│     └── 持久化：预测结果 → data_manager/prediction_store（90天）        │
│                                                                         │
│  4. probability_predictor（上涨概率预测）                                │
│     ├── 获取：data_manager 历史日K线                                    │
│     ├── 计算：基于技术指标的概率预测                                     │
│     ├── 输出：ProbabilityPrediction → recommender                        │
│     └── 持久化：预测结果 → data_manager/prediction_store（90天）        │
│                                                                         │
│  5. recommender（融合决策）                                             │
│     ├── 获取：cp_engine 战力 + gain_predictor 涨幅 + probability 概率   │
│     ├── 融合：战力×权重 + 涨幅预测×权重 + 上涨概率×权重                 │
│     └── 输出：换股/买入/卖出建议 → simulator                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 盘中执行流程（交易日 9:30-15:00）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         盘中（每分钟/每隔N分钟）                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. stock_selector                                                      │
│     └── 事件触发：涨停/跌停/成交量异常 → 临时池观察                      │
│                                                                         │
│  2. cp_engine（实时因子）                                               │
│     └── 仅核心池股票：每分钟计算 real_time_score（MA5/MA15变化率）       │
│                                                                         │
│  3. data_manager                                                        │
│     └── 按池分层策略更新：核心池5分钟、活跃池30分钟、观察池日频          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 回测验证流程（手动/每周定时）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         回测验证（手动/每周）                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. backtester                                                          │
│     ├── 读取：cp_history（战力历史）                                    │
│     ├── 读取：prediction_store（预测历史）                               │
│     ├── 读取：历史行情数据                                              │
│     └── 验证：                                                          │
│         ├── 战力选股策略有效性（高战力组是否跑赢市场）                    │
│         ├── 涨幅预测准确性（预测偏差、TopK准确率）                       │
│         └── 概率预测校准度（预测概率 vs 实际上涨比例）                   │
│                                                                         │
│  2. 输出：回测报告 → 用户/前端展示 → 文件系统存档                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 六、战力引擎（cp_engine/）

### 6.1 引擎职责

战力引擎是分析引擎的核心模块，负责计算股票综合战力评分，为 recommender 提供选股依据。

**核心功能**：
- 多维度战力评分计算（成长、价值、质量、动量）
- 风险评估与仓位建议（Kelly公式）
- 换股决策分析（交易成本建模）
- 数据校验与清洗（拦截ST/*ST股）
- 技术指标集成（MA、MACD、RSI等）

### 5.2 战力公式

```
总战力 = (成长分×30% + 价值分×25% + 质量分×20% + 动量分×8% + 实时分×2%) × 风险调整
```

**各因子说明**：

| 因子 | 权重 | 数据来源 | 计算方式 |
|------|------|----------|----------|
| 成长分 | 30% | 财务数据 | 净利润增速(60%) + 营收增速(40%) |
| 价值分 | 25% | 行情+财务 | ROE + PE评分 + PEG + PB |
| 质量分 | 20% | 财务数据 | 现金流 + 毛利率 + 资产负债率 |
| 动量分 | 8% | 行情数据 | 多日动量(60%) + 当日涨跌幅(40%) |
| 实时分 | 2% | 分钟级数据 | MA5变化(50%) + MA15变化(30%) + 成交量(20%) |
| 风险惩罚 | 10% | 综合评估 | 根据PE、ROE、波动率等调整 |

### 5.3 关键数据结构

| 数据结构 | 说明 |
|----------|------|
| `StockCP` | 单只股票战力数据（含各维度分数和风险评估） |
| `CashCP` | 现金战力计算（持有现金的机会成本） |
| `TradeDecision` | 换股决策引擎（交易成本建模） |
| `DataValidator` | 数据校验器（拦截ST/*ST股） |
| `RiskAnalyzer` | 风险评估器（集中度、行业、流动性等） |
| `KellyCalculator` | Kelly公式仓位计算器 |

### 5.4 更新频率

- **日常计算**：每日收盘后执行一次完整战力计算
- **实时因子**：仅核心池股票在盘中实时更新（每分钟）
- **风险评估**：与战力计算同步更新

**详细文档**：[CP_ENGINE.md](./cp_engine/CP_ENGINE.md)

---

## 七、涨幅预测引擎（gain_predictor/）

### 7.1 引擎职责

预测股票未来N日涨幅，为 recommender 提供融合决策依据。

### 7.2 目录结构

```
gain_predictor/
├── __init__.py
├── predictor.py               # 预测器
└── features.py                # 特征计算
```

**详细文档**：[GAIN_PREDICTOR.md](./gain_predictor/GAIN_PREDICTOR.md)

---

## 八、上涨概率预测引擎（probability_predictor/）

### 8.1 引擎职责

预测股票未来N日上涨概率，为 recommender 提供融合决策依据。

### 8.2 目录结构

```
probability_predictor/
├── __init__.py
├── predictor.py               # 预测器
└── features.py                # 特征计算
```

**详细文档**：[PROBABILITY_PREDICTOR.md](./probability_predictor/PROBABILITY_PREDICTOR.md)

---

## 九、与 Recommender 模块的关系

```
引擎输出：
├── cp_engine ───────────────┐
├── gain_predictor ──────────┼──▶ recommender（融合决策）
└── probability_predictor ───┘
```

融合逻辑在 recommender 模块实现，各引擎只负责纯预测。

---

## 十、文件清单

### 新建目录

| 目录 | 操作 |
|------|------|
| `engine/gain_predictor/` | 新建 |
| `engine/probability_predictor/` | 新建 |

### 新建文件

| 文件 | 操作 |
|------|------|
| `engine/gain_predictor/__init__.py` | 新建 |
| `engine/gain_predictor/predictor.py` | 新建 |
| `engine/gain_predictor/features.py` | 新建 |
| `engine/probability_predictor/__init__.py` | 新建 |
| `engine/probability_predictor/predictor.py` | 新建 |
| `engine/probability_predictor/features.py` | 新建 |

### 现有文件改动

| 文件 | 操作 |
|------|------|
| `engine/__init__.py` | 修改：添加预测引擎导出 |
| `engine/cp_engine/` | 重组：文件移入 cp_engine/ 子目录 |

### 需删除

| 文件/目录 | 原因 |
|-----------|------|
| `engine/pipelines/` | 已废弃，改用引擎目录 |
| `engine/shared/` | 已废弃 |

---

## 十一、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v19.8 | 2026-04-08 | 🔨 重组为引擎目录结构，新增预测引擎 |
| v19.7 | 2026-04-08 | cp_history迁移到data_manager |
| v18.2 | 2026-04-07 | 技术指标集成、稳健归一化 |

---

## 十二、相关文档

- [战力引擎详细方案](./cp_engine/CP_ENGINE.md)
- [涨幅预测引擎详细方案](./gain_predictor/GAIN_PREDICTOR.md)
- [上涨概率预测引擎详细方案](./probability_predictor/PROBABILITY_PREDICTOR.md)
- [数据管理模块方案](../data_manager/DATA_MANAGER_ARCHITECTURE.md)
- [智能推荐模块方案](../recommender/RECOMMENDER_ARCHITECTURE.md)
