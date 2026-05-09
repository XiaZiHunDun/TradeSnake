# 系统数据填充模块方案

> 本文档是数据填充模块的入口索引，实际内容拆分到以下两个文件中：

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| [DATA_FILLER_OVERVIEW.md](./DATA_FILLER_OVERVIEW.md) | 版本历史、概述（职责定位、数据存储清单、战力历史特殊性、预测引擎存储、ExRightFactor、price_history、财务历史、设计目标） | ~329 |
| [DATA_FILLER_DETAIL.md](./DATA_FILLER_DETAIL.md) | 数据流设计、数据结构设计、核心类设计、与现有模块集成、API接口设计、使用示例、实现清单、已知约束 | ~1045 |

## 内容速览

### DATA_FILLER_OVERVIEW.md
- **版本历史**：v19.10~v19.14 更新记录
- **职责定位**：系统数据填充模块 vs update_scheduler 的区别
- **数据存储清单**：DuckDB (daily_kline, minute_kline)、SQLite (stocks, ex_right_factor, cp_history, price_history, predictions)
- **战力历史特殊性**：cp_history 是计算得出的人口数据，非外部填充
- **预测引擎存储**：gain_predictions、probability_predictions 由引擎计算写入
- **ExRightFactor 填充**：P0紧急，除权因子表为空
- **price_history 定位**：历史遗留表，计划迁移到DuckDB
- **财务历史数据**：P2级，战力回填前置条件
- **设计目标**：6条核心目标

### DATA_FILLER_DETAIL.md
- **数据流设计**：KlineFiller 完整数据流、填充类型（批量/增量/单股）
- **数据结构设计**：填充状态表（SQLite WAL模式）、交易日历表（DuckDB）
- **核心类设计**：FillerState、GapDetector、KlineFiller、辅助函数、DataValidator、Tushare分页、RetryHandler、MultiSourceProvider、AdjFactorHandler、DataAlignmentValidator
- **与现有模块集成**：DataManager、update_scheduler、cleanup
- **API接口设计**：异步任务模式（防HTTP超时）
- **使用示例**：首次部署、日常增量、断点续跑、除权因子、分钟K线
- **实现清单**：34项任务（P0~P3）
- **已知约束**：17条关键约束

## 原文档拆分说明

原 `DATA_FILLER_ARCHITECTURE.md`（1368行）拆分为两个文件以降低单文件大小，改进文档加载性能和可维护性。
