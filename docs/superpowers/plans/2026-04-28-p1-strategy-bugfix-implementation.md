# 任务：策略核心 Bug 修复（P1）

> 日期：2026-04-28  
> 类型：Critical Bug Fix（高影响）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 设计文档：alpha_diagnosis_and_fix 计划

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

**重要**：这些是影响策略核心行为的 bug。每个修复后必须运行相关测试验证。

---

## Goal

修复 5 个策略核心 bug：

1. 多日动量 import 错误（导致动量因子从未生效）
2. 行业 PE 调整后不重算 total_cp
3. simple backtest 的 holding_days 参数是装饰性的
4. FullBacktestEngine 和 constants.py 手续费不一致
5. ParameterScanner 参数不传递给实际回测

完成后：所有现有测试通过 + 每个 bug 有针对性的回归测试。

---

## Context

这些 bug 的共同特征是"代码在运行，但行为不是设计意图"——静默的逻辑错误。

---

## Scope

Allowed changes:

- `backend/engine/cp_engine/cp_engine.py`
- `backend/engine/cp_engine/history.py`（如需添加别名）
- `backend/backtester/backtest.py`
- `backend/backtester/full_backtest.py`
- `backend/backtester/parameter_scanner.py`
- `backend/backtester/strategy_comparator.py`
- `backend/backtester/metrics.py`（如需统一 Sharpe）
- `backend/tests/` 中的测试文件
- `tests/backtester/` 中的测试文件

Out of scope:

- 不改变 CP 公式的权重或设计
- 不改变 API 端点路径
- 不修改前端

---

## Steps

### Bug 1: 修复 momentum import（最关键）

**位置**：`backend/engine/cp_engine/cp_engine.py` 第 1046 行

**问题**：
```python
from .history import calc_momentum_5d  # ❌ 不存在
```
`history.py` 中只有 `get_momentum_5d`（第 237 行），没有 `calc_momentum_5d`。`except ImportError: pass` 静默吞掉错误，导致 `apply_multi_day_momentum` 从未被调用。

**修复**：
```python
from .history import get_momentum_5d
self.apply_multi_day_momentum(get_momentum_5d, days=5)
```

注意 `apply_multi_day_momentum` 的签名（约第 886 行）接受 `momentum_func` 参数，调用方式是 `momentum_func(stock.code, days)`。但 `get_momentum_5d` 签名是 `get_momentum_5d(code: str) -> float`（不接受 days）。

检查 `apply_multi_day_momentum` 的调用方式：
- 如果它调用 `momentum_func(stock.code, days)`，而 `get_momentum_5d` 不接受 days 参数，需要用 `calc_momentum_nd` 替代
- `calc_momentum_nd(code, days=5)` 才是正确的接口

**正确修复**：
```python
from .history import calc_momentum_nd
self.apply_multi_day_momentum(calc_momentum_nd, days=5)
```

- [ ] 阅读 `apply_multi_day_momentum` 确认它如何调用 `momentum_func`
- [ ] 选择正确的函数（`calc_momentum_nd` 或包装后的 `get_momentum_5d`）
- [ ] 修复 import
- [ ] 同时将 `except ImportError` 改为更精确的异常处理，避免再次静默失败：
```python
except ImportError as e:
    import warnings
    warnings.warn(f"Multi-day momentum disabled: {e}")
```
- [ ] 验证：`python -m pytest backend/tests/test_cp_engine.py -v`

### Bug 2: 行业 PE 调整后重算 total_cp

**位置**：`backend/engine/cp_engine/cp_engine.py`

**问题**：`_apply_industry_pe_adjustment()`（第 1177 行）修改 `stock.risk_score`，但 `total_cp` 在第 1141 行已经计算完毕。后续展示的 `risk_score` 与 `total_cp` 不一致。

**修复**：在 `_apply_industry_pe_adjustment()` 结尾，为每个被调整的 stock 重算 total_cp。

方案：在 `_apply_industry_pe_adjustment` 方法最后添加重算逻辑。需要知道每个 stock 的 `base_cp`。

最安全的方式是：在 `calculate_all` 的循环中先把 `base_cp` 存到 stock 上（`stock._base_cp = base_cp`），然后 `_apply_industry_pe_adjustment` 中用 `stock._base_cp` 和新的 `risk_score` 重算。

- [ ] 在 `calculate_all` 循环中存储 `stock._base_cp = base_cp`
- [ ] 在 `_apply_industry_pe_adjustment` 中对被调整的 stock 重算：
```python
risk_factor = 1 - (stock.risk_score / 100) * WEIGHTS['risk_penalty']
stock.total_cp = max(0, stock._base_cp * risk_factor)
```
- [ ] 验证：`python -m pytest backend/tests/test_cp_engine.py -v`
- [ ] 添加测试：构造有行业数据的 stocks，验证调整后 total_cp 与 risk_score 一致

### Bug 3: simple backtest holding_days 实际生效

**位置**：`backend/backtester/backtest.py` 第 777-817 行

**问题**：`calculate_simple_backtest` 接收 `holding_days` 参数但只是放进返回值中，实际逻辑只比较首尾两天的 CP 均值。

**修复**：让 `holding_days` 真正用于选取日期窗口。

```python
def calculate_simple_backtest(self, start_date, end_date, holding_days=30, top_n=10):
    dates = self.get_available_dates(start_date, end_date)
    if len(dates) < 2:
        return {"error": "数据不足"}
    
    # 使用 holding_days 限制窗口
    if holding_days < len(dates):
        dates = dates[:holding_days + 1]  # +1 因为需要首尾两天
    
    initial_date = dates[0]
    final_date = dates[-1]
    # ... 其余逻辑不变
```

- [ ] 修改 `calculate_simple_backtest` 使用 `holding_days` 截取日期窗口
- [ ] 同步修改 `calculate_compare_backtest`（目前直接调用 simple）
- [ ] 验证：`python -m pytest tests/backtester/ -v`
- [ ] 添加测试：验证不同 holding_days 产生不同结果

### Bug 4: 统一手续费常量

**位置**：
- `backend/engine/cp_engine/constants.py`：`TRADE_COST['commission'] = 0.0003`（万3）
- `backend/backtester/full_backtest.py`：`COMMISSION_RATE = 0.0001`（万1）

**问题**：回测用万1佣金，但实盘模拟器用万3。回测结果比实盘乐观。

**修复**：`FullBacktestEngine` 从 `constants.py` 导入费用常量：

```python
from backend.engine.cp_engine.constants import TRADE_COST

class FullBacktestEngine:
    COMMISSION_RATE = TRADE_COST['commission']
    MIN_COMMISSION = TRADE_COST['min_commission']
    STAMP_TAX_RATE = TRADE_COST['stamp_tax']
    TRANSFER_FEE_RATE = TRADE_COST['transfer_fee']
    SLIPPAGE_RATE = 0.001  # 滑点保留——这是回测特有的
```

- [ ] 修改 `full_backtest.py` 导入 `TRADE_COST`
- [ ] 保留 `SLIPPAGE_RATE`（滑点是回测特有的，实盘不需要模拟）
- [ ] 验证：`python -m pytest tests/backtester/ -v`

### Bug 5: ParameterScanner 参数传递

**位置**：`backend/backtester/parameter_scanner.py` 第 190-225 行

**问题**：`_evaluate_params` 创建了 `BacktestConfig` 但没有传给 `self.comparator`。`self.comparator` 在 `__init__` 时就用默认 config 创建了，后续参数变化不生效。

**修复**：在 `_evaluate_params` 中用新 config 重建 comparator 或传入 config：

```python
def _evaluate_params(self, strategy_name, params, start_date, end_date):
    try:
        config = BacktestConfig(
            top_n=params['top_n'],
            stop_loss=params['stop_loss'],
            max_holding_days=params['max_holding_days']
        )
        # 用当前参数创建临时 comparator
        comparator = StrategyComparator(config=config)
        results = comparator.compare_strategies(
            start_date=start_date,
            end_date=end_date,
            strategy_names=[strategy_name]
        )
        ...
```

- [ ] 修改 `_evaluate_params` 用新的 config 创建 comparator
- [ ] 验证：`python -m pytest tests/backtester/ -v`
- [ ] 添加测试：验证不同参数确实产生不同回测结果

### 附加：统一 Sharpe 计算

**位置**：
- `backend/backtester/metrics.py`：Sharpe = (annual_return - 3%) / volatility
- `backend/backtester/full_backtest.py`：Sharpe = mean_daily_return / std × √250（无风险利率 = 0）

- [ ] 在 `full_backtest.py` 的 Sharpe 计算中减去无风险利率（年化 3% 即日化 3/250 = 0.012%）
- [ ] 或统一为不减无风险利率（在注释中说明）
- [ ] 关键是两处计算方式一致

### 全量验证

- [ ] `python -m pytest backend/tests/test_cp_engine.py -v`
- [ ] `python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py`
- [ ] `python -m pytest tests/backtester/ -v`
- [ ] `python -m pytest backend/tests/test_routes.py -v -m "not integration"`
- [ ] `python -c "from backend.api.main import app; print('OK')"`

---

## Verification

```bash
# CP 引擎测试
python -m pytest backend/tests/test_cp_engine.py -v

# 全量后端测试
python -m pytest backend/tests/ tests/backtester/ backend/data_manager/tests/ tests/test_simulator.py -v -m "not integration" --ignore=backend/tests/test_routes.py

# 路由测试
python -m pytest backend/tests/test_routes.py -v -m "not integration"

# 导入验证
python -c "from backend.engine.cp_engine.cp_engine import CPEngine; e = CPEngine(); print('OK')"
```

---

## Completion Report Format

```markdown
## Summary
- 逐个 bug 说明修复内容

## Verification
- 测试结果

## Behavioral Changes
- 动量因子恢复后对 CP 排名的影响说明
- 手续费统一后对回测结果的影响说明

## New Tests Added
- 列表

## Next Task Recommendation
```
