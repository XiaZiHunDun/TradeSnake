# 数据管理模块方案

> 本文档是数据管理模块的入口索引，实际内容拆分到以下两个文件中：

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| [DATA_MANAGER_OVERVIEW.md](./DATA_MANAGER_OVERVIEW.md) | 概述、输入输出、数据存储现状、数据分类总结、一、模块结构、二、核心组件详解（DataManager/Fetcher/Cache/Cleaner/CircuitBreaker/Batcher/Adjuster/Monitor/Backup/DuckDB/Cleanup/Providers） | ~411 |
| [DATA_MANAGER_DETAIL.md](./DATA_MANAGER_DETAIL.md) | 三、数据流、四、便捷函数、五、数据分类、六、测试覆盖、七、已实现功能清单、八、数据源问题排查、九、版本历史、十、相关文档 | ~463 |

## 内容速览

### DATA_MANAGER_OVERVIEW.md
- **概述**：核心流程（获取→清洗→存储）、产品范围（仅沪深主板）
- **输入输出**：数据源（Tushare/腾讯/东方财富/akshare/stock_selector）、输出（行情/财务/K线/cp_history/predictions）
- **数据存储现状**：DuckDB（daily_kline 244万行、minute_kline 239万行、trade_cal空）、SQLite（stocks 3432行、cp_history、prediction库）
- **数据分类总结**：独立外部数据、关联外部数据（核心池分钟K线）、引擎写入数据
- **模块结构**：13个核心文件 + providers/ + tests/
- **核心组件**：DataManager统一入口、Fetcher多数据源、Cache LRU+JSON、CircuitBreaker熔断限流、Batcher异步批量、Adjuster复权因子、Monitor监控、Backup备份、DuckDB历史K线、Cleanup生命周期、Providers数据源

### DATA_MANAGER_DETAIL.md
- **数据流**：实时行情获取（腾讯→新浪备用）、财务数据获取（东方财富→Baostock→akshare）、Tushare→DuckDB、回测读取、与stock_selector联动（核心池5分钟/活跃池30分钟/观察池不更新）
- **便捷函数**：快速获取股票/Tushare/DuckDB/监控指标
- **测试覆盖**：106个测试全部通过
- **数据源问题排查**：东方财富API不稳定、Baostock连接池、SQLite损坏、cp_engine启动为空、数据源网络特性矩阵（v19.9.8）
- **版本历史**：v18.1~v19.9.3 共15个版本记录

## 原文档拆分说明

原 `DATA_MANAGER_ARCHITECTURE.md`（874行）拆分为两个文件以降低单文件大小，改进文档加载性能和可维护性。
