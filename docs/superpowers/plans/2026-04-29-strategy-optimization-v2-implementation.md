# Task: 策略优化 V2 — 数据驱动的权重重构 + 风控集成 + ML 修复

## 背景

全量验证（425 天，2024-04 ~ 2026-04）揭示了三个核心问题：

1. **total_cp 合成分数失效**：t=0.76 不显著，五分位反转（Q1 > Q5）。
   原因：value_score（IC=-0.009）和 quality_score（IC=-0.003）是反向/无效因子，
   在合成时稀释了 growth_score（唯一正 IC 因子，t=2.46）。

2. **风控未集成到回测**：MaxDD 17.2%，Fold 12 单折亏 -13.1%。
   `RiskManager` 已实现但未接入 `WalkForwardBacktester`。

3. **ML 超时**：`_get_codes_for_date` fallback 返回 3000+ codes 导致特征计算爆炸。

## 目标

通过 3 项修改，将 Sharpe 从 0.30 提升到 0.50+，MaxDD 控制在 15% 以内。

---

## Part A: 因子权重重构

### A1: 修改 `backend/engine/cp_engine/constants.py`

基于 Alpha 分析的数据驱动权重：

```python
WEIGHTS = {
    'growth': 0.50,      # 唯一显著正 IC (t=2.46)，大幅增配
    'value': 0.00,       # IC=-0.009，反转因子，清零（不反转使用）
    'quality': 0.05,     # IC=-0.003，几乎无效，降到最低
    'momentum': 0.28,    # t=1.71 边界显著，保持适度权重
    'real_time': 0.02,   # 不变
    'risk_penalty': 0.10 # 不变（这不是预测因子，是惩罚项）
}
```

**验证**：WEIGHTS 中预测因子（growth + value + quality + momentum + real_time）之和 = 0.85，加上 risk_penalty 0.10 = 0.95。符合现有框架。

> 注意：不要修改 `MOMENTUM_WEIGHTS`，上次已经调过了（short_reversal=0.50）。

### A2: 修改换仓频率

growth 的 IC 在 20 天最强（0.0238 > 5 天的 0.0104），说明因子有持续预测力，不需要频繁换仓。

在 `backend/backtester/walk_forward.py` 的 `WalkForwardConfig` 中：
```python
rebalance_freq: int = 10   # 从 5 改为 10（与 growth IC 特征匹配）
```

同时修改 `scripts/full_backtest_report.py` 中的默认值：
```python
parser.add_argument("--rebalance", type=int, default=10, ...)
```

---

## Part B: 风控集成到 Walk-Forward 回测

### B1: 修改 `backend/backtester/walk_forward.py`

在 `_run_fold` 方法中集成组合级止损：

1. 在 `_run_fold` 的 test 循环中，追踪组合净值 `portfolio_value`
2. 记录组合峰值 `peak_portfolio_value`
3. 当 `(portfolio_value - peak_portfolio_value) / peak_portfolio_value < -0.15` 时，
   清仓所有持仓（模拟组合级回撤熔断）
4. 清仓后该 fold 剩余交易日返回 0 收益（空仓等待）

具体实现（在 `for dt in test_dates:` 循环内）：

```python
# 在循环开始前添加
portfolio_value = self.config.initial_capital
peak_value = portfolio_value
portfolio_stopped = False

# 在每日收益计算后添加
if day_returns_list:
    avg_ret = float(np.mean(day_returns_list))
    portfolio_value *= (1 + avg_ret)
    peak_value = max(peak_value, portfolio_value)
    
    # 组合级回撤检查
    drawdown = (peak_value - portfolio_value) / peak_value
    if drawdown > 0.15 and not portfolio_stopped:
        # 全部清仓
        for code in list(holdings.keys()):
            sell_val = holdings[code]
            cost = sell_val * sell_cost_rate
            fees += max(cost, TRADE_COST["min_commission"])
            traded_value += sell_val
            n_trades += 1
        holdings = {}
        portfolio_stopped = True
    
    daily_returns.append(avg_ret)
    dates_out.append(dt)
elif not portfolio_stopped:
    daily_returns.append(0.0)
    dates_out.append(dt)
```

### B2: 添加个股级 trailing stop

在 `_run_fold` 的每日循环中，追踪每只股票的最高价，回撤超过 -10% 时卖出：

```python
# 在 holdings 初始化后添加
peak_prices = {}  # code -> peak_price

# 在计算 ret 后添加
if code not in peak_prices:
    peak_prices[code] = c1
else:
    peak_prices[code] = max(peak_prices[code], c1)

trailing_dd = (peak_prices[code] - c1) / peak_prices[code]
if trailing_dd > 0.10:  # trailing stop at -10%
    # 卖出逻辑（同 stop_loss）
```

---

## Part C: ML 修复

### C1: 修改 `backend/ml/features.py`

在 `_get_codes_for_date` 的 fallback 分支限制返回数量：

```python
def _get_codes_for_date(self, date: str) -> List[str]:
    try:
        records = self.cp_store.get_snapshot(date)
        if records:
            return [r["code"] for r in records if "code" in r]
    except Exception:
        pass
    # fallback: 从 daily_kline 取当日有交易的 codes，限制 500 只
    try:
        conn = self.duckdb._get_read_conn()
        df = conn.execute(
            "SELECT DISTINCT code FROM daily_kline WHERE trade_date = ? LIMIT 500",
            [date],
        ).df()
        if not df.empty:
            return df["code"].tolist()
    except Exception:
        pass
    return []
```

### C2: 重新运行 ML 训练

修复后执行：
```bash
conda run --no-capture-output -n tradesnake python -u scripts/train_model.py --walk-forward --start 2024-10-01 --end 2026-04-23
```

记录输出（MAE、IC、AUC）。

---

## Part D: 验证优化效果

### D1: 运行测试确认无回归

```bash
conda run --no-capture-output -n tradesnake python -m pytest backend/tests/ -v -m "not integration" 2>&1 | tail -30
```

### D2: 重新运行 Walk-Forward 回测

```bash
conda run --no-capture-output -n tradesnake python -u scripts/full_backtest_report.py --start 2024-10-01 --end 2026-04-23 --top-n 6 --rebalance 10 --stop-loss -0.07
```

### D3: 重新运行 Alpha 分析（验证权重变更不影响原始 IC）

```bash
conda run --no-capture-output -n tradesnake python -u scripts/alpha_analysis.py --start 2024-04-15 --end 2026-04-23
```

### D4: 对比报告

输出优化前后对比：

```
指标            优化前    优化后    变化
Annual Return   9.54%     ?        ?
Sharpe          0.30      ?        ?
MaxDD           17.2%     ?        ?
Calmar          0.55      ?        ?
Turnover        8.5x      ?        ?
```

---

## 自主决策规则

1. Part A（权重重构）→ Part B（风控集成）→ Part C（ML修复）顺序执行
2. Part D 的 4 项验证可以并行（测试 / 回测 / alpha / ML 互不依赖）
3. 如果 Walk-Forward 报 "No folds"，按之前的调试步骤检查 get_snapshot
4. 如果修改 walk_forward.py 后测试失败，优先修复测试
5. 如果 Sharpe 仍低于 0.50，记录数据并在报告中分析原因
6. 遇到 DuckDB lock，先 `fuser data/historical.duckdb` 检查

## 停止条件

- Part A/B/C 修改完成 + Part D 所有验证执行完毕 + 对比报告输出
- 或遇到无法自行解决的错误，记录详情
