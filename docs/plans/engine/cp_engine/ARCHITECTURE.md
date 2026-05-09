# 战力引擎模块架构方案

> 本文档是 ENGINE_ARCHITECTURE.md 的补充，详细内容拆分到 CP_ENGINE.md 中。

## 概述

战力引擎是分析引擎的核心模块，负责计算股票综合战力评分（成长50% + 动量28% + 质量5% + 价值0% + 实时2%），为 recommender 提供选股依据。

**核心功能**：
- 多维度战力评分计算（成长、价值、质量、动量）
- 风险评估与仓位建议（Kelly公式）
- 换股决策分析（交易成本建模）
- 数据校验与清洗（拦截ST/*ST股）
- 技术指标集成（MA、MACD、RSI等）

**更新频率**：每日收盘后执行一次完整战力计算；仅核心池股票在盘中实时更新（每分钟）。

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| ARCHITECTURE.md | 本文件，索引 | ~40 |
| CP_ENGINE.md | 详细设计文档（v21权重、公式、算法） | ~349 |
| ISSUES.md | 问题追踪 | ~36 |
| CHECKLIST.md | 检查清单 | ~33 |

## 核心文件

```
backend/engine/cp_engine/
├── __init__.py
├── cp_engine.py              # 战力计算核心
├── constants.py               # 常量配置（v21 WEIGHTS）
├── indicators.py              # 技术指标（MA、MACD、RSI）
├── cache.py                   # 因子级缓存
├── parallel.py                # 并行计算
├── history.py                 # 战力历史记录
├── refresh_strategy.py        # 刷新策略
├── trading_time.py            # 交易时间判断
└── risk_analyzer.py           # 风险评估器
```

**关键数据结构**：`StockCP`（股票战力）、`CashCP`（现金战力）、`TradeDecision`（换股决策）、`DataValidator`（数据校验）、`RiskAnalyzer`（风险评估）、`KellyCalculator`（Kelly公式）。

## 快速链接

- 详细设计：[CP_ENGINE.md](./CP_ENGINE.md)
- 问题追踪：[ISSUES.md](./ISSUES.md)
- 检查清单：[CHECKLIST.md](./CHECKLIST.md)
- 引擎总览：[ENGINE_ARCHITECTURE.md](../ENGINE_ARCHITECTURE.md)
