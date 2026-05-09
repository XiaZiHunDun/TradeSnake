# 模拟炒股模块实现文档

> **状态**: 文档已拆分。设计概述见 [SIMULATOR_OVERVIEW.md](./SIMULATOR_OVERVIEW.md)

## 实现差异说明

| 项目 | 设计文档描述 | 状态 |
|------|-------------|------|
| **RiskControl.check_all()调用** | Trader.buy/sell应在执行前调用`RiskControl.check_all()`进行综合风控检查 | **已修复** (v19.8.1) |

> **说明**：`RiskControl.check_all()`现已整合到Trader.buy()和Trader.sell()中，包含：资金检查、持仓30%上限检查、每日买入80%限额检查、每日10次交易限制、T+1检查、涨跌停拦截。

## 输入输出验证 (2026-04-16)

### 输入验证

| 来源 | 方案描述 | 实际实现 | 状态 |
|------|----------|----------|------|
| data_manager | 实时行情 | `get_single_stock_data()` 在 trader.py:36-52, risk_control.py:53-59, account.py:66-71 调用 |  |
| recommender | 交易建议 | 通过 `/api/orders` API端点接收买入/卖出指令 |  |
| 用户操作 | 手动交易 | `trader.buy/sell/cancel_order` 方法 |  |
| 内部状态 | 账户/持仓 | `Account`, `Portfolio` 类内部管理 |  |

### 输出验证

| 输出内容 | 方案描述 | 实际实现 | 状态 |
|----------|----------|----------|------|
| 账户摘要 | 用户/前端、recommender | `Account.get_summary()` -> `api/router.py /api/account` |  |
| 持仓明细 | 用户/前端、recommender | `Portfolio.get_holdings()` -> `api/router.py /api/portfolio` |  |
| trades | 用户/前端、backtester | `database.record_trade()` -> `trades` 表 |  |
| orders | 用户/前端 | `orders` 表 -> `api/router.py /api/orders` |  |
| holding_snapshots | backtester | `record_daily_holding_snapshots()` -> `holding_snapshots` 表 |  |

### 实现与方案一致性确认

| 检查项 | 方案要求 | 实现状态 |
|--------|----------|----------|
| 市价单成交价 | 按当前最新价（非涨跌停价） | trader.py:30-52 `get_market_price()` |
| 交易费用 | 佣金0.03%最低5元，印花税0.05%，过户费0.001% | account.py:11-14 从 `TRADE_COST` 导入 |
| check_pending_orders触发 | 支持事件驱动/定时轮询/查询触发三种方案 | trader.py:356-398 支持三种触发 |
| RiskControl.check_all调用 | Trader.buy/sell执行前调用综合风控 | trader.py:92-97, 230-235 调用 |
| holding_snapshots表 | v19.7新增，用于backtester验证持仓收益 | database.py:192-209 建表，846-941 操作方法 |

**结论**：模拟引擎实现与方案完全一致，无差异。

## 模块对接检查 (2026-04-16)

### 1. simulator <-> data_manager

| 对接项 | 方向 | 实现方式 | 状态 |
|--------|------|----------|------|
| 实时行情 | data_manager -> simulator | `get_single_stock_data()` 在 trader.py:36,67,209,364,507 调用 |  |
| 风控检查 | data_manager -> simulator | risk_control.py:53-59 调用 `get_single_stock_data` 获取涨跌停状态 |  |
| 市值计算 | data_manager -> simulator | account.py:66-71 调用获取持仓当前价格 |  |

### 2. simulator <-> recommender

| 对接项 | 方向 | 实现方式 | 状态 |
|--------|------|----------|------|
| 交易建议 | recommender -> simulator | recommender输出BuySignal/SellSignal，用户通过API手动执行 |  |
| API入口 | recommender -> simulator | `/api/trade/buy` (router.py:377-400), `/api/trade/sell` (router.py:403-426) |  |

**说明**：方案设计中recommender生成交易建议后传给simulator执行。实际实现为：recommender只输出信号和建议，用户或外部系统通过API手动调用执行。这是合理的设计分离（决策与执行分离），但需知晓不是自动执行。

### 3. simulator <-> backtester

| 对接项 | 方向 | 实现方式 | 状态 |
|--------|------|----------|------|
| cp_history读取 | simulator -> backtester | backtest.py:609-618 从 `simulator.database` 读取交易日列表 |  |
| holding_snapshots | simulator -> backtester | verification.py:100-179 `verify_swap_effectiveness()` 读取快照验证换股效果 |  |
| 持仓市值历史 | simulator -> backtester | database.py:998-1037 `get_portfolio_value_history()` |  |

### 4. API层对接

| 对接项 | 实现方式 | 状态 |
|--------|----------|------|
| 全局Trader实例 | `router.py:54 _trader = Trader()` |  |
| 持仓快照自动记录 |战力刷新时调用 `record_daily_holding_snapshots()` (router.py:624-626) |  |
| 手动记录快照 | `/api/snapshot/record` (router.py:677-706) |  |

## 版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v21 | 2026-05-06 | 集成 v21 风控参数：stop_loss=-7%, **trailing_stop=-8%**, portfolio_drawdown=-15%，与 Walk-Forward v3 参数一致（TS=-8%） |
| v19.8.1 | 2026-04-14 | 修复RiskControl.check_all()未被调用问题：Trader.buy/sell()现使用RiskControl.check_all()进行综合风控检查 |
| v19.8 | 2026-04-09 | 修复导入路径错误（TRADE_COST）、盈亏计算使用FIFO匹配、最大回撤使用快照表计算 |
| v19.7 | 2026-04-08 | 每日持仓快照记录（holding_snapshots表）、换股效果验证、战力预测准确性分析 |
| v19.1 | 2026-04-07 | 完整实现：Stats + RiskControl模块、市价单最新价成交、限价单触发机制 |
| v19.0 | 2026-04-07 | 基于单人模拟场景重构：移除订单簿撮合，改为价格对比成交，增加除权除息与统计 |
| v18.6 | 2026-04-07 | 根据专家评审优化：集合竞价/连续竞价、价格笼子、并发安全 |
| v18.5 | 2026-04-07 | 增强：委托单/限价单/撤单/冻结资金 |
| v18.4 | 2026-04-07 | 初始完整实现 |

## 相关文档

- [SIMULATOR_OVERVIEW.md](./SIMULATOR_OVERVIEW.md) - 设计概述
- [ENGINE_ARCHITECTURE.md](../engine/ENGINE_ARCHITECTURE.md) - 分析引擎
- [RECOMMENDER_ARCHITECTURE.md](../recommender/RECOMMENDER_ARCHITECTURE.md) - 推荐引擎
- [DATA_MANAGER_ARCHITECTURE.md](../data_manager/DATA_MANAGER_ARCHITECTURE.md) - 数据管理
