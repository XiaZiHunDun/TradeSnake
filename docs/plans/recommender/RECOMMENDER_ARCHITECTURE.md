# 智能推荐模块方案

> 本文档是智能推荐模块的入口索引，实际内容拆分到以下两个文件中：

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| [RECOMMENDER_OVERVIEW.md](./RECOMMENDER_OVERVIEW.md) | 概述、输入输出、三大场景、模块结构、核心组件、风控清单 | ~520 |
| [RECOMMENDER_DETAIL.md](./RECOMMENDER_DETAIL.md) | 数据模型、接口契约、版本历史、相关文档 | ~320 |

## 内容速览

### RECOMMENDER_OVERVIEW.md
- **概述**：决策支持模块，基于战力评分给出买卖建议
- **输入输出**：输入（cp_engine/预测引擎/stock_selector/simulator），输出（换股/买入/卖出信号）
- **三大场景**：换股（战力差vs交易成本）、纯买入（Kelly仓位/时机）、纯卖出（止盈/止损/调仓）
- **预测融合**（v19.8）：归一化公式(cp/100, gain/50)、融合权重(保守/平衡/激进)
- **模块结构**：recommend_engine/swap_calculator/buy_analyzer/sell_analyzer/filters/fusion/prompts
- **核心组件**：RecommendEngine、SwapCalculator（五档决策矩阵）、BuyAnalyzer、SellAnalyzer、StockFilter、prompts
- **风控清单**：P0（ST/停牌/涨跌停/数据质量）、P1（流动性/财报季/大盘模式）

### RECOMMENDER_DETAIL.md
- **数据模型**：SwapSuggestion/BuySignal/SellSignal 完整字段定义
- **接口契约**：RecommenderCallback v18.5（池变化通知/优先候选/监控列表）、与stock_selector联动代码
- **版本历史**：v18.2~v18.6 共5个版本
- **相关文档**：PROJECT_OVERVIEW/ENGINE/DATA_MANAGER/专家评审

## 原文档拆分说明

原 `RECOMMENDER_ARCHITECTURE.md`（719行）拆分为两个文件以降低单文件大小，改进文档加载性能和可维护性。
