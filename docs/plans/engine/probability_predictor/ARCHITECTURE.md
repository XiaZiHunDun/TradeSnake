# 上涨概率预测引擎模块架构方案

> 本文档是 ENGINE_ARCHITECTURE.md 的补充，详细内容拆分到 PROBABILITY_PREDICTOR.md 中。

## 概述

上涨概率预测引擎预测股票未来N日上涨概率（3日/5日），基于K线技术指标（动量、趋势、RSI、KDJ）使用规则模型计算，为 recommender 提供融合决策依据。

**核心功能**：
- 多特征计算（gain_Nd、volatility_Nd、ma_position、rsi、kdj）
- 涨跌停处理（涨停+0.15，跌停-0.15）
- 置信度计算（基于综合得分）
- 风险等级评估（high/medium/low）
- 预测结果持久化（90天）

**设计原则**：完全独立，不依赖战力评分，只使用K线数据；每日收盘后执行一次预测。

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| ARCHITECTURE.md | 本文件，索引 | ~40 |
| PROBABILITY_PREDICTOR.md | 详细设计文档（特征计算、预测算法） | ~268 |
| ISSUES.md | 问题追踪 | ~20 |
| CHECKLIST.md | 检查清单 | ~30 |

## 核心文件

```
backend/engine/probability_predictor/
├── __init__.py
├── predictor.py               # 预测器（ProbabilityPredictor）
└── features.py                # 特征计算
```

**关键数据结构**：`ProbabilityPrediction`（单只股票上涨概率）、`ProbabilityPredictionResult`（批量结果）。

## 快速链接

- 详细设计：[PROBABILITY_PREDICTOR.md](./PROBABILITY_PREDICTOR.md)
- 问题追踪：[ISSUES.md](./ISSUES.md)
- 检查清单：[CHECKLIST.md](./CHECKLIST.md)
- 引擎总览：[ENGINE_ARCHITECTURE.md](../ENGINE_ARCHITECTURE.md)
