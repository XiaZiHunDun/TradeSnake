# 回测验证模块方案

> 本文档是回测验证模块的入口索引，实际内容拆分到以下两个文件中：

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| [BACKTESTER_OVERVIEW.md](./BACKTESTER_OVERVIEW.md) | 概述、输入输出、回测声明、一、实现差异说明、二、设计背景、三、模块结构、四、核心组件 | ~404 |
| [BACKTESTER_DETAIL.md](./BACKTESTER_DETAIL.md) | 五、关键实现、六、配置参数、七、使用示例、八、API集成状态、九、输入输出验证、十、版本历史、十一 | ~389 |

## 内容速览

### BACKTESTER_OVERVIEW.md
- **概述**：回测引擎（backtest.py）+ 策略验证（verification.py）两个子组件
- **输入输出**：输入（cp_history/prediction_store/行情/simulator持仓快照）、输出（绩效指标/换股验证/预测准确性）
- **回测声明**：5项简化假设（不分股模式/T+1可选/固定收盘价/固定股票池/可选手续费）
- **实现差异**：3项未完成功能（成交价模型/基准数据/预测分数融合）
- **设计背景**：战力驱动选股回测，与模拟炒股区分（T+1/手续费/适用场景）
- **模块结构**：backtest.py + verification.py + strategies.py + metrics.py + reports.py
- **核心组件**：Backtest回测引擎（信号日→成交日分离/涨跌停拦截）、Strategy策略基类、Metrics绩效指标（17项）、Reports报告结构、Verification策略验证（5个功能方法）

### BACKTESTER_DETAIL.md
- **关键实现**：历史数据获取（数据防护机制）、撮合模拟（涨跌停拦截/T+1检查/成本模型）、调仓执行（5步逻辑）、持仓管理（PositionManager v19.8）
- **配置参数**：13个参数（initial_capital/max_positions/max_position_days/include_fees/strict_t1等）
- **使用示例**：TopNStrategy回测完整代码、策略有效性判断标准（五档：优秀/良好/一般/较差）
- **API集成状态**：已清理遗留core/目录、当前5个模块版本、4项待完善TODO
- **输入输出验证**：5项输入验证（⚠️ cp_history和历史行情仍从simulator读取）、6项输出验证（✅ 全部通过）、模块对接检查（v19.9.2已修复cp_history读取）
- **版本历史**：v19.1~v19.9.2 共10个版本记录

## 原文档拆分说明

原 `BACKTESTER_ARCHITECTURE.md`（793行）拆分为两个文件以降低单文件大小，改进文档加载性能和可维护性。
