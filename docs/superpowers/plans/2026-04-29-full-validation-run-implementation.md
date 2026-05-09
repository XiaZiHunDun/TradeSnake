# Task: 全量验证运行 — Alpha + Walk-Forward + ML

## 背景

Part 1-3 已完成：
- CPHistoryStore 已添加 `get_snapshot()` 方法（兼容 WalkForward/ML 调用）
- features.py 已修复 `recorded_at` key 不匹配和 codes fallback
- filler.py 已修复 `DB_PATH`、`FillResult.skipped`、`record_cp_history(date=)` 传参、CPEngine 跨日期堆积 bug
- CP 历史已回填 425 天 (2024-04-01 ~ 2026-04-28)，每天 500 只股票
- DuckDB daily_kline 有 2010~2026 共 157 万行数据

## 目标

运行 3 项全量验证，输出综合报告，让我们知道策略的真实表现。

---

## Step 1: Alpha 分析 (统计显著性验证)

```bash
conda run --no-capture-output -n tradesnake python -u scripts/alpha_analysis.py --start 2024-04-15 --end 2026-04-23 --horizon 5
```

**预期输出：**
- 每个因子的 Mean IC、ICIR、t-stat（425 天数据，t-stat 应该可靠）
- 信号衰减（1/3/5/10/20 天 IC）
- 五分位分组回测（Q1~Q5 收益和 Long/Short spread）

**如果报错：**
- "Need at least 30 dates" → 检查 `cp_history_store.get_available_dates()` 返回值
- DuckDB lock → 先确认无其他进程占用：`fuser data/historical.duckdb`

**记录完整输出。**

---

## Step 2: Walk-Forward 策略回测

```bash
conda run --no-capture-output -n tradesnake python -u scripts/full_backtest_report.py --start 2024-10-01 --end 2026-04-23 --top-n 6 --rebalance 5 --stop-loss -0.07
```

注意：start 设为 2024-10-01（需要 train_window=120 天训练期，从 2024-04 开始才有 CP 数据，120 个交易日约 6 个月后才能开始第一个 fold）。

**预期输出：**
- Walk-Forward Report: Total Return、Annual Return、Sharpe、Sortino、Max Drawdown、Calmar
- 逐 Fold 明细（train/test 日期、收益、Sharpe、MaxDD、交易次数）
- Benchmark 对比

**如果 "No folds completed"：**
- 说明 `cp_store.get_snapshot(date)` 返回空。
- 调试：在 python 交互模式中测试：
  ```python
  from backend.data_manager.cp_history_store import get_cp_history_store
  store = get_cp_history_store()
  dates = store.get_available_dates()
  print(f"dates: {len(dates)}, sample: {dates[:5]}")
  snapshot = store.get_snapshot(dates[100])
  print(f"snapshot for {dates[100]}: {len(snapshot)} stocks")
  if snapshot:
      print(f"sample: {snapshot[0]}")
  ```
- 如果 get_snapshot 返回空，检查 `get_cp_history_by_date` 是否正常。
- 如果 snapshot 有数据但 walk_forward 仍失败，检查 `walk_forward.py` 第 168 行的 `hasattr(cp_store, "get_snapshot")` 是否为 True。

**记录完整输出。**

---

## Step 3: ML 模型训练与 Walk-Forward 验证

```bash
conda run --no-capture-output -n tradesnake python -u scripts/train_model.py --walk-forward --start 2024-10-01 --end 2026-04-23
```

**预期输出：**
- Walk-forward fold 结果（MAE、IC、AUC）
- 整体平均指标

**如果报错 "No data" 或 dataset 为空：**
- 可能是 `FeatureBuilder._get_codes_for_date()` 仍返回空
- 测试：
  ```python
  from backend.ml.features import FeatureBuilder
  fb = FeatureBuilder()
  codes = fb._get_codes_for_date("2025-01-06")
  print(f"codes: {len(codes)}")
  if codes:
      df = fb.build_features_for_date("2025-01-06", codes[:50])
      print(f"features shape: {df.shape}")
  ```
- 如果 codes 来自 fallback（daily_kline），数量会很多（3000+），可能导致内存/速度问题
- 修复方案：在 `_get_codes_for_date` 的 fallback 分支增加 LIMIT 500

**记录完整输出。**

---

## Step 4: 运行全部现有测试确认无回归

```bash
conda run --no-capture-output -n tradesnake python -m pytest backend/tests/ -v -m "not integration" 2>&1 | tail -30
```

**预期：** 所有测试通过（211+）

---

## Step 5: 综合报告

将 Step 1-3 的输出整理为一份简洁的总结，包括：

1. **Alpha 分析结果表**
   - 每个因子：Mean IC、ICIR、t-stat、是否显著（|t|>2）
   - 信号衰减特征
   - 最强因子排名

2. **Walk-Forward 回测结果**
   - 总收益、年化收益、Sharpe、MaxDD
   - 与沪深300基准对比
   - 逐 fold 稳定性评估

3. **ML 模型验证结果**
   - 平均 IC、MAE、AUC
   - 特征重要性 Top 10

4. **结论与建议**
   - 策略是否有正 alpha
   - 哪些因子贡献最大
   - 风险警告（前瞻偏差：财务因子使用当前值，非时点值）
   - 下一步优化方向

---

## 自主决策规则

1. 如果 alpha_analysis 正常完成，直接进入 Step 2
2. 如果 walk_forward 报 "No folds"，按调试步骤排查并修复
3. 如果 ML train 因数据集为空失败，修复 `_get_codes_for_date` fallback 加 LIMIT 后重试
4. 遇到 DuckDB lock，执行 `fuser data/historical.duckdb` 确认是否有其他进程占用，如果有先 kill
5. 所有测试通过后，输出综合报告

## 停止条件

- 3 项验证全部完成并输出报告
- 或遇到无法自行解决的错误（如数据库损坏、依赖缺失等），记录错误详情并报告
