# 股票筛选模块架构方案

> 本文档是 stock_selector 模块架构的入口索引，实际内容拆分到以下两个文件中：

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| [STOCK_SELECTOR_OVERVIEW.md](./STOCK_SELECTOR_OVERVIEW.md) | 版本历史、输入输出、模块定位、数据流设计、核心组件概览 | ~548 |
| [STOCK_SELECTOR_DETAIL.md](./STOCK_SELECTOR_DETAIL.md) | 数据结构、接口设计、配置项、监控指标、实现计划 | ~390 |
| [STOCK_SELECTOR_TROUBLESHOOTING.md](./STOCK_SELECTOR_TROUBLESHOOTING.md) | 文件清单、待确认事项、v19.9更新、附录 | ~330 |

## 内容速览

### STOCK_SELECTOR_OVERVIEW.md
- **版本历史 (v19.9)**：DuckDB稳定性、分钟K线自动填充、池状态持久化
- **输入输出**：产品范围（仅沪深主板）、输出股票池分层
- **模块定位**：职责边界（只读数据、通过回调通知）、核心价值
- **数据流设计**：三层过滤（硬性排除→准入→分层）、盘后批处理 vs 盘中实时
- **核心组件**：PoolManager、Rebalancer、EventTrigger、FinancialWatcher 等

### STOCK_SELECTOR_DETAIL.md
- **数据结构**：StockInfo、TempStockInfo、StockSnapshot、枚举定义
- **接口设计**：StockSelector Facade、SelectorCallback 协议、CPBoard联动
- **配置项**：白名单/黑名单、硬性排除、质量准入、分层阈值、再平衡、临时池、事件触发、财务预警、指数同步、更新频率策略
- **监控指标**：各池数量、周转率、过滤统计、预警统计、事件统计
- **实现计划**：8个Phase（基础框架→核心筛选→动态调整→财务预警→更新策略→事件驱动→白名单→联动集成）

### STOCK_SELECTOR_TROUBLESHOOTING.md
- **文件清单**：backend/stock_selector/ 目录结构
- **待确认事项**：9项核心决策（核心池数量、次新股保护期、晋级/降级阈值等）
- **v19.9更新**：DuckDB文件锁、单连接复用、Checkpoint、池状态持久化、分钟K线自动填充、Tushare Revenue Fallback
- **附录A/B**：专家评审贡献、阈值量化依据

## 原文档拆分说明

原 `STOCK_SELECTOR_DETAIL.md`（738行）拆分为两个文件以降低单文件大小，改进文档加载性能和可维护性。
