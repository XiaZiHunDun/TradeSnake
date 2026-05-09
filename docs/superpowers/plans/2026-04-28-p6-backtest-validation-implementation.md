# 任务：严格回测验证体系（P6）

> 日期：2026-04-28
> 类型：Validation Infrastructure
> 设计方：Cursor
> 执行方：Claude Code
> 前置任务：P1 完成

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions.

回测验证是判断"策略到底能不能赚钱"的最终裁判。必须严格。

---

## Goal

建立严格的策略回测验证体系：

1. Walk-forward 回测 - 滚动窗口训练+测试，杜绝过拟合
2. 基准对比 - 与沪深 300、中证 500、等权组合对比
3. 完整指标报告 - 年化收益、Sharpe、最大回撤、Calmar、换手率、手续费占比
4. 报告脚本 - 输出文本格式的回测报告

---

## Context

当前回测问题：
- 无样本外测试，无法判断是否过拟合
- 无基准对比，不知道策略是否跑赢"买大盘"
- Sharpe 计算不统一，不同接口不可比
- 缺少 Calmar、换手率、手续费占比等关键指标

设计原则：
1. Walk-forward 是必须的
2. 基准线至少要有：沪深 300 和等权买入
3. 指标计算统一使用一套公式

---

## Scope

Allowed changes:

- 创建 `backend/backtester/walk_forward.py`
- 创建 `backend/backtester/benchmark.py`
- 修改 `backend/backtester/metrics.py`（统一指标、新增指标）
- 创建 `scripts/full_backtest_report.py`
- 创建 `backend/tests/test_walk_forward.py`
- 修改 `backend/api/routers/backtest.py`（新增 walk-forward API）

Out of scope:
- 不修改 CP 引擎
- 不修改前端
- 不修改模拟器

---

## Steps

### Step 1: 统一指标计算

修改 `backend/backtester/metrics.py`，使用统一的无风险利率（年化 3%）和交易日天数（250）。

新增指标 dataclass `BacktestMetrics`：
- total_return, annual_return, excess_return
- volatility, max_drawdown, max_drawdown_duration
- sharpe_ratio, calmar_ratio, sortino_ratio
- total_trades, win_rate, profit_factor, avg_holding_days, turnover_rate
- total_fees, fee_ratio
- benchmark_return, alpha, beta, information_ratio

提供 `compute_metrics(daily_returns, benchmark_returns, trades, total_fees, total_traded_value)` 函数。

### Step 2: 创建基准模块

`backend/backtester/benchmark.py`：

BenchmarkProvider 类：
- 从 DuckDB 获取沪深 300 (000300) 日收益率
- 计算等权组合收益（CP 池中所有股票）
- 方法：`get_benchmark_returns(name, start, end)`

### Step 3: Walk-forward 回测引擎

`backend/backtester/walk_forward.py`：

WalkForwardConfig：
- train_window: 120 交易日
- test_window: 20 交易日
- step_size: 20 交易日
- top_n: 6
- rebalance_freq: 5 交易日
- stop_loss: -0.07
- initial_capital: 1000000

WalkForwardBacktester 流程：
1. 用 train_window 最后一天的 CP 排名确定持仓
2. 在 test_window 中模拟持有
3. 按 rebalance_freq 换仓
4. 应用止损、计算费用
5. 滚动到下一个窗口
6. 汇总所有 test_window 收益

### Step 4: 报告脚本

`scripts/full_backtest_report.py`：

```
运行: python scripts/full_backtest_report.py --start 2025-01-01 --end 2026-04-28
```

输出内容：
- 策略 vs 基准的完整指标对比表
- Walk-forward 各 fold 表现
- 风险分析（最大回撤、最差月份）
- 费用分析（换手率、手续费占比）
- 结论：策略是否跑赢基准？alpha 是否统计显著？

### Step 5: 添加 Walk-forward API

在 `backend/api/routers/backtest.py` 添加：

```python
@router.get("/api/backtest/walk_forward")
async def walk_forward_backtest(
    start_date: str = Query(...),
    end_date: str = Query(...),
    top_n: int = Query(6),
    rebalance_freq: int = Query(5),
):
    """Walk-forward 回测"""
    ...
```

### Step 6: 测试

创建 `backend/tests/test_walk_forward.py`：
- 测试窗口生成逻辑
- 测试单窗口回测
- 测试指标计算一致性（两处 Sharpe 公式相同）
- 测试基准对比
- 全量回归测试

---

## Verification

```bash
python -c "from backend.backtester.walk_forward import WalkForwardBacktester; print('OK')"
python -c "from backend.backtester.benchmark import BenchmarkProvider; print('OK')"
python scripts/full_backtest_report.py --help
python -m pytest backend/tests/ tests/backtester/ -v -m "not integration" --ignore=backend/tests/test_routes.py
python -m pytest backend/tests/test_walk_forward.py -v
```

---

## Completion Report Format

```
## Summary
- 创建的模块
- Walk-forward 架构说明

## Backtest Results（如有数据）
- 策略 vs 基准收益
- Sharpe, Calmar
- Walk-forward 各 fold 表现

## Verification
- 测试结果

## Usage
- 如何运行回测报告
```
