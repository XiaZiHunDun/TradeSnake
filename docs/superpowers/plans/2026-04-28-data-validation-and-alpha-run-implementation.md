# 任务：数据验证 + 首轮 Alpha 分析

> 日期：2026-04-28
> 类型：Data Validation + Analysis Run
> 设计方：Cursor
> 执行方：Claude Code

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions.

---

## Background

6 个优先级的代码实施已全部完成（211 tests passing）。
现在需要用实际数据验证这些修改的效果。

当前数据情况：
- CP History: 63 天 (2026-01-19 ~ 2026-04-28)，约 950 stocks/day
- DuckDB: 391 MB（有 K 线数据，但可能被另一进程锁住）
- Walk-forward 完整版需要 140+ 天，目前数据不够
- Alpha 分析可以在 63 天数据上运行缩减版

---

## Goal

1. 解决 DuckDB 锁冲突问题
2. 确认 DuckDB K 线数据的日期范围和股票覆盖度
3. 修复 CP history store 的接口（`get_snapshot` 和 `get_available_dates` 方法），使 P2/P6 工具能正确读取数据
4. 用现有 63 天数据运行缩减版 Alpha 分析
5. 用缩减版 walk-forward（train=40, test=10）运行回测

---

## Steps

### Step 1: 解决 DuckDB 锁问题

DuckDB 被另一个 Python 进程 (PID 1007858) 锁住了。

```bash
# 检查进程
ps aux | grep 1007858

# 如果是旧的/无用进程，kill 掉
# 如果是后端服务，改用 read-only 连接
```

如果锁无法解除，修改分析脚本使用 DuckDB 的 read-only 模式：
```python
conn = duckdb.connect('data/historical.duckdb', read_only=True)
```

### Step 2: 确认 DuckDB 数据范围

```bash
conda run -n tradesnake python -c "
import duckdb
conn = duckdb.connect('data/historical.duckdb', read_only=True)
print(conn.execute('SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM daily_kline').fetchone())
print(conn.execute('SELECT COUNT(DISTINCT code) FROM daily_kline').fetchone())
conn.close()
"
```

### Step 3: 修复 CP History Store 接口

检查 `backend/data_manager/cp_history_store.py` 中的接口：

1. **`get_snapshot(date)`** — AlphaAnalyzer 和 WalkForwardBacktester 都依赖这个方法。确认它能根据 `recorded_at` 字段返回某天的所有股票 CP 数据。CP history 表的列是：`id, code, name, total_cp, growth_score, value_score, quality_score, momentum_score, risk_score, rank, recorded_at, created_at, price, is_hot, change_pct`。注意没有 `date` 列，日期在 `recorded_at` 中（格式待确认）。

2. **`get_available_dates()`** — 返回所有有数据的日期列表。

3. **`get_cp_history(code, days=5)`** — FeatureBuilder 依赖这个方法。

如果这些方法不存在或者签名不匹配，需要添加/修复。

- [ ] 读取 `cp_history_store.py`，确认方法签名
- [ ] 确认 `recorded_at` 的格式（是 'YYYY-MM-DD' 还是 'YYYY-MM-DD HH:MM:SS'）
- [ ] 如果 `get_snapshot` 不存在，添加
- [ ] 如果 `get_available_dates` 不存在，添加

```python
def get_snapshot(self, date: str) -> List[Dict]:
    """获取某天所有股票的 CP 快照"""
    rows = self.conn.execute(
        "SELECT * FROM cp_history WHERE substr(recorded_at, 1, 10) = ? ORDER BY rank",
        [date]
    ).fetchall()
    # 转为 dict 列表
    ...

def get_available_dates(self) -> List[str]:
    """获取所有有数据的日期列表"""
    rows = self.conn.execute(
        "SELECT DISTINCT substr(recorded_at, 1, 10) as d FROM cp_history ORDER BY d"
    ).fetchall()
    return [r[0] for r in rows]
```

### Step 4: 运行 Alpha 分析（缩减版）

用 63 天数据运行 Alpha 分析（需要至少 10 天就能算 IC）：

```bash
conda run -n tradesnake python scripts/alpha_analysis.py --start 2026-01-19 --end 2026-04-28 --horizon 5
```

如果报错，根据错误信息修复 AlphaAnalyzer 中的数据访问逻辑（特别是 CP store 接口和 DuckDB 查询）。

### Step 5: 运行缩减版 Walk-forward

修改 walk-forward 参数适应 63 天数据：

```bash
conda run -n tradesnake python scripts/full_backtest_report.py \
    --start 2026-01-19 --end 2026-04-28 --top-n 6
```

如果默认 train_window=120 太大，临时在脚本中添加 `--train-window` 参数，或直接修改默认值为 40。

### Step 6: 收集结果并报告

输出以下信息：

1. DuckDB 数据范围（K 线覆盖的日期和股票数）
2. CP History 数据范围（确认 63 天 × 950 stocks）
3. Alpha 分析结果（每个因子的 IC、ICIR）
4. Walk-forward 回测结果（如果数据够的话）
5. 任何需要修复的数据接口问题

---

## Scope

Allowed changes:

- `backend/data_manager/cp_history_store.py`（添加/修复接口）
- `backend/backtester/alpha_analyzer.py`（修复数据访问）
- `backend/backtester/walk_forward.py`（调整默认参数）
- `backend/ml/features.py`（修复数据访问）
- `scripts/alpha_analysis.py`（如需修复）
- `scripts/full_backtest_report.py`（添加参数）

Out of scope:

- 不修改 CP 引擎核心逻辑
- 不修改前端
- 不修改策略权重（权重调整等 alpha 分析结果出来后再做）

---

## Verification

```bash
# Alpha 分析能运行
conda run -n tradesnake python scripts/alpha_analysis.py --start 2026-02-01 --end 2026-04-28

# Walk-forward 能运行（即使结果不显著）
conda run -n tradesnake python scripts/full_backtest_report.py --start 2026-02-01 --end 2026-04-28

# 训练脚本能运行
conda run -n tradesnake python scripts/train_model.py --start 2026-02-01 --end 2026-04-15

# 既有测试不受影响
conda run -n tradesnake python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py
```

---

## Completion Report Format

```markdown
## Data Status
- DuckDB K线: X 行, YYYY-MM-DD ~ YYYY-MM-DD, N stocks
- CP History: X 天, YYYY-MM-DD ~ YYYY-MM-DD, ~N stocks/day

## Interface Fixes
- 列表

## Alpha Analysis Results
- 因子 IC 表格
- 哪个因子最强？

## Walk-forward Results (缩减版)
- 总收益、Sharpe、最大回撤

## Key Finding
- 基于数据的一句话结论

## Remaining Issues
- 需要更多数据？
- 需要修复什么？
```
