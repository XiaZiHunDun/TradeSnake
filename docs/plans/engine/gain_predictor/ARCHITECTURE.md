# 涨幅预测引擎模块架构方案

> 本文档是 ENGINE_ARCHITECTURE.md 的补充，详细内容拆分到 GAIN_PREDICTOR.md 中。

## 概述

涨幅预测引擎预测股票未来N日涨幅（3日/5日），基于K线技术指标（动量、波动率、趋势、RSI、MACD）使用规则模型计算，为 recommender 提供融合决策依据。

**核心功能**：
- 多特征计算（gain_Nd、volatility_Nd、ma_position、rsi、macd）
- 涨跌停处理（根据板块限制自动调整）
- 置信度与置信区间计算
- 预测结果持久化（90天）

**设计原则**：完全独立，不依赖战力评分，只使用K线数据；每日收盘后执行一次预测。

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| ARCHITECTURE.md | 本文件，索引 | ~40 |
| GAIN_PREDICTOR.md | 详细设计文档（特征计算、预测算法） | ~275 |
| ISSUES.md | 问题追踪 | ~18 |
| CHECKLIST.md | 检查清单 | ~30 |

## 核心文件

```
backend/engine/gain_predictor/
├── __init__.py
├── predictor.py               # 预测器（GainPredictor）
└── features.py                # 特征计算
```

**关键数据结构**：`GainPrediction`（单只股票涨幅预测）、`GainPredictionResult`（批量结果）。

## 快速链接

- 详细设计：[GAIN_PREDICTOR.md](./GAIN_PREDICTOR.md)
- 问题追踪：[ISSUES.md](./ISSUES.md)
- 检查清单：[CHECKLIST.md](./CHECKLIST.md)
- 引擎总览：[ENGINE_ARCHITECTURE.md](../ENGINE_ARCHITECTURE.md)
