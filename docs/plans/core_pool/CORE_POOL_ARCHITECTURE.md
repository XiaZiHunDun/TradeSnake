# 核心池流程架构方案 v19.9.6

> 本文档是核心池流程的入口索引，记录核心池的整体流程、模块对接、数据流转和问题追踪。

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| [CORE_POOL_FLOW.md](./CORE_POOL_FLOW.md) | 概述、数据流、模块详解（stock_selector/data_manager/cp_engine/recommender/simulator）、存储、API、代码规范、问题追踪、版本历史 | ~356 |
| [ISSUES.md](./ISSUES.md) | 问题追踪（P3: total_cp计算问题及解决方案） | ~439 |
| [CHECKLIST.md](./CHECKLIST.md) | 数据流验证检查清单 | ~196 |

## 内容速览

### CORE_POOL_FLOW.md
- **核心池概述**：核心池（沪深主板100-300只）+ 活跃池（约500只）
- **数据流**：stock_selector → data_manager → cp_engine → recommender → simulator 的完整流水线
- **模块详解**：5个核心模块的职责、关键文件、API
- **存储**：DuckDB（日K线/分钟K线）+ SQLite（stocks/cp_history/prediction）
- **API端点**：核心池相关API、推荐融合参数
- **代码规范**：股票代码格式、日期格式
- **问题追踪**：已解决/已知问题
- **版本历史**：v19.9.1~v19.9.6

### ISSUES.md
- **P3问题**：部分股票 total_cp 未计算（1484只revenue=0且total_cp=0）
- **根因**：东方财富/baostock的revenue数据缺失
- **状态**：✅ 已从Tushare income API获取revenue作为fallback

### CHECKLIST.md
- **数据流验证**：stock_selector → data_manager → cp_engine → recommender → API 各环节检查点

## 模块定位

核心池不是独立代码模块，而是描述以下模块如何协同工作的**流程文档**：

| 模块 | 文档位置 |
|------|---------|
| stock_selector | [STOCK_SELECTOR_ARCHITECTURE.md](../stock_selector/STOCK_SELECTOR_ARCHITECTURE.md) |
| data_manager | [DATA_MANAGER_ARCHITECTURE.md](../data_manager/DATA_MANAGER_ARCHITECTURE.md) |
| cp_engine | [ENGINE_ARCHITECTURE.md](../engine/ENGINE_ARCHITECTURE.md) |
| recommender | [RECOMMENDER_ARCHITECTURE.md](../recommender/RECOMMENDER_ARCHITECTURE.md) |
| simulator | [SIMULATOR_ARCHITECTURE.md](../simulator/SIMULATOR_ARCHITECTURE.md) |

## 版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v19.9.6 | 2026-04-26 | 补充核心池数据流图 |
| v19.9.5 | 2026-04-25 | 更新股票池准入标准 |
| v19.9.4 | 2026-04-22 | 补充P3问题调查结论 |
| v19.9.3 | 2026-04-21 | 增加代码格式规范 |
| v19.9.1 | 2026-04-20 | 初始版本 |
