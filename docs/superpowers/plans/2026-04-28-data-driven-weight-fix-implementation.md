# 任务：数据驱动的权重修正 + DuckDB 并发修复

> 日期：2026-04-28
> 类型：Strategy Fix + Infrastructure
> 设计方：Cursor
> 执行方：Claude Code
> 前置数据：Alpha 分析结果（growth IC=+0.016, momentum IC=-0.027）

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions.

---

## Background

Alpha 分析结果显示当前因子权重有严重问题：

| 因子 | Mean IC | 结论 |
|------|---------|------|
| growth_score | +0.016 | 唯一正 IC，增配 |
| value_score | -0.003 | 无预测力，降权 |
| quality_score | -0.004 | 无预测力，降权 |
| momentum_score | -0.027 | **反向指标**，A 股反转效应 |
| total_cp | -0.007 | 综合分负 IC — 当前权重在亏钱 |

核心问题：momentum IC=-0.027 说明"动量高的股票反而跌"。系统给动量正权重 = 系统性追涨。

---

## Part A: 权重修正

### 文件：`backend/engine/cp_engine/constants.py`

修改 `WEIGHTS`：

```python
# 战力公式权重 v20.1（数据驱动版）
# 基于 63 天 Alpha 分析: growth IC=+0.016（唯一正 IC），
# momentum IC=-0.027（翻转为反转因子后有效）
WEIGHTS = {
    'growth': 0.35,
    'value': 0.20,
    'quality': 0.08,
    'momentum': 0.20,
    'real_time': 0.02,
    'risk_penalty': 0.10
}
```

修改 `MOMENTUM_WEIGHTS`：

```python
# 动量子因子权重 v20.1（反转主导）
# Alpha 数据: 短期反转 IC 为正（跌多反弹），中期动量 IC 为负
MOMENTUM_WEIGHTS = {
    'short_reversal': 0.50,
    'medium_momentum': 0.15,
    'volume_confirm': 0.20,
    'daily_change': 0.15,
}
```

验证权重总和：
- WEIGHTS 不含 risk_penalty: 0.35+0.20+0.08+0.20+0.02 = 0.85（正确，与之前一致）
- MOMENTUM_WEIGHTS: 0.50+0.15+0.20+0.15 = 1.00（正确）

### 测试更新

更新 `backend/tests/test_momentum_enhanced.py` 中的 `TestMomentumConstants`：

```python
class TestMomentumConstants:
    def test_weights_sum_to_one(self):
        total = sum(MOMENTUM_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_main_weights_changed(self):
        assert WEIGHTS["momentum"] == 0.20
        assert WEIGHTS["quality"] == 0.08
        assert WEIGHTS["growth"] == 0.35
```

---

## Part B: DuckDB 并发修复

### 文件：`backend/data_manager/duckdb_store.py`

在 `DuckDBStore` 类中添加一个静态方法：

```python
@staticmethod
def get_readonly_connection(db_path=None):
    """获取只读连接，用于分析脚本。不与主进程的写锁冲突。"""
    import duckdb
    from backend.config import DUCKDB_PATH
    path = db_path or str(DUCKDB_PATH)
    return duckdb.connect(path, read_only=True)
```

也在模块级别暴露：

```python
def get_readonly_connection(db_path=None):
    """获取只读 DuckDB 连接，用于分析脚本"""
    return DuckDBStore.get_readonly_connection(db_path)
```

### 修改分析脚本使用 readonly 连接

1. `backend/backtester/alpha_analyzer.py` — 如果 duckdb 初始化失败，回退到 readonly
2. `backend/ml/features.py` — 同上
3. `backend/backtester/benchmark.py` — 同上
4. `backend/backtester/walk_forward.py` — 同上

模式：在每个文件的 `__init__` 中 try/except，写锁失败时自动切 readonly：

```python
def __init__(self):
    from backend.data_manager.duckdb_store import get_duckdb_store
    try:
        self.duckdb = get_duckdb_store()
        # 测试连接是否可用
        self.duckdb._get_read_conn()
    except Exception:
        # 主进程持有写锁时，用只读连接
        from backend.data_manager.duckdb_store import get_readonly_connection
        self._readonly_conn = get_readonly_connection()
        # 创建一个 duck-typed wrapper
        self.duckdb = self._make_readonly_wrapper()
```

注意：这个改动比较侵入性。更简单的方案是只在 `_get_read_conn` 方法中 try/except 自动降级：

```python
def _get_read_conn(self):
    if self._read_conn is None:
        with self._conn_lock:
            if self._read_conn is None:
                try:
                    self._read_conn = duckdb.connect(self.db_path, read_only=False)
                except duckdb.IOException:
                    # 另一个进程持有写锁，降级为只读
                    self._read_conn = duckdb.connect(self.db_path, read_only=True)
                self._read_conn.execute("SET threads=1")
    return self._read_conn
```

**推荐方案**：修改 `_get_read_conn()` 添加 try/except 降级为 read_only=True。这是最小侵入的改法，所有依赖 `get_duckdb_store()` 的代码自动受益。

同时也修改 `__init__` 中建表逻辑的错误处理，如果是只读连接就跳过建表。

---

## Part C: 自动权重校准脚本

### 创建 `scripts/calibrate_weights.py`

```python
#!/usr/bin/env python
"""
自动权重校准脚本

基于 Alpha 分析结果，按 IC 符号和大小建议因子权重。

用法:
  python scripts/calibrate_weights.py --start 2026-01-19 --end 2026-04-28
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description='Auto Weight Calibration')
    parser.add_argument('--start', default=None)
    parser.add_argument('--end', default=None)
    parser.add_argument('--horizon', type=int, default=5)
    args = parser.parse_args()
    
    from backend.backtester.alpha_analyzer import AlphaAnalyzer
    
    analyzer = AlphaAnalyzer()
    
    # 因子到权重键的映射
    factor_map = {
        'growth_score': 'growth',
        'value_score': 'value',
        'quality_score': 'quality',
        'momentum_score': 'momentum',
    }
    
    print("=" * 60)
    print("Auto Weight Calibration")
    print("=" * 60)
    
    # 计算每个因子的 IC
    ics = {}
    for factor in factor_map:
        result = analyzer.compute_factor_ic(
            factor, horizon=args.horizon,
            start_date=args.start, end_date=args.end
        )
        ics[factor] = result
        print(f"  {factor:<20} IC={result.mean_ic:+.4f}  ICIR={result.icir:.3f}  t={result.t_stat:.2f}")
    
    # 权重分配逻辑
    # 1. IC > 0 的因子：按 |IC| 分配权重
    # 2. IC < 0 的因子：如果 |IC| > 0.02 说明有反向预测力，翻转信号方向后可用
    # 3. |IC| < 0.005 的因子：几乎无预测力，给最低权重
    
    MIN_WEIGHT = 0.05  # 最低权重 5%
    TOTAL_BUDGET = 0.85  # 减去 real_time(2%) 和 risk_penalty(10%) 后的总量
    REAL_TIME = 0.02
    RISK_PENALTY = 0.10
    
    raw_weights = {}
    reversal_needed = {}
    
    for factor, result in ics.items():
        abs_ic = abs(result.mean_ic)
        if abs_ic < 0.005:
            # 几乎无预测力
            raw_weights[factor] = MIN_WEIGHT
            reversal_needed[factor] = False
        elif result.mean_ic > 0:
            # 正向 IC — 正常使用
            raw_weights[factor] = abs_ic
            reversal_needed[factor] = False
        else:
            # 负向 IC — 有反向预测力
            raw_weights[factor] = abs_ic
            reversal_needed[factor] = True
    
    # 归一化到 TOTAL_BUDGET
    total_raw = sum(raw_weights.values())
    if total_raw > 0:
        for f in raw_weights:
            raw_weights[f] = max(MIN_WEIGHT, raw_weights[f] / total_raw * TOTAL_BUDGET)
    
    # 再次归一化确保总和 = TOTAL_BUDGET
    total_assigned = sum(raw_weights.values())
    scale = TOTAL_BUDGET / total_assigned if total_assigned > 0 else 1
    for f in raw_weights:
        raw_weights[f] = round(raw_weights[f] * scale, 2)
    
    print("\n## Suggested WEIGHTS")
    print("WEIGHTS = {")
    for factor, weight_key in factor_map.items():
        w = raw_weights[factor]
        rev = " ← REVERSE SIGNAL" if reversal_needed[factor] else ""
        print(f"    '{weight_key}': {w},{rev}")
    print(f"    'real_time': {REAL_TIME},")
    print(f"    'risk_penalty': {RISK_PENALTY}")
    print("}")
    
    print("\n## Momentum Direction")
    if reversal_needed.get('momentum_score', False):
        print("  momentum_score 有负 IC → 建议增大 short_reversal 子权重（反转为主）")
        print("  MOMENTUM_WEIGHTS = {")
        print("      'short_reversal': 0.50,")
        print("      'medium_momentum': 0.15,")
        print("      'volume_confirm': 0.20,")
        print("      'daily_change': 0.15,")
        print("  }")
    else:
        print("  momentum_score 有正 IC → 保持正向动量为主")
    
    print("\n## Note")
    print(f"  样本天数: {len(ics['growth_score'].ic_series) if ics.get('growth_score') else 'N/A'}")
    print("  |t| < 2 的因子结论仅供参考，方向性可靠但幅度可能变化")
    print("  建议 140+ 天数据后重新校准")


if __name__ == '__main__':
    main()
```

---

## Part D: 验证

运行以下验证命令：

```bash
# 1. 全量测试
conda run -n tradesnake python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py

# 2. 导入验证
conda run -n tradesnake python -c "from backend.api.main import app; print('OK')"

# 3. Alpha 分析（验证 DuckDB readonly 修复）
# 注意：如果后端服务在运行，这应该也能成功
conda run -n tradesnake python scripts/alpha_analysis.py --start 2026-02-01 --end 2026-04-28

# 4. 校准脚本
conda run -n tradesnake python scripts/calibrate_weights.py --start 2026-02-01 --end 2026-04-28

# 5. Walk-forward（如果 DuckDB 可用）
conda run -n tradesnake python scripts/full_backtest_report.py --start 2026-02-01 --end 2026-04-28
```

理想结果：
- total_cp 的 IC 从 -0.007 改善（因为 growth 增配 + momentum 翻转为反转）
- 测试全部通过（可能需要更新常量测试中的期望值）

---

## Scope

Allowed:
- `backend/engine/cp_engine/constants.py`
- `backend/data_manager/duckdb_store.py`
- `backend/tests/test_momentum_enhanced.py`
- `scripts/calibrate_weights.py`（新建）
- `backend/backtester/alpha_analyzer.py`（如需修复 readonly）
- `backend/ml/features.py`（如需修复 readonly）
- `backend/backtester/benchmark.py`（如需修复 readonly）
- `backend/backtester/walk_forward.py`（如需修复 readonly 或添加 --train-window 参数）
- `scripts/full_backtest_report.py`（如需添加 --train-window 参数）

Out of scope:
- 不修改 CP 引擎核心逻辑（只改常量）
- 不修改前端
- 不修改 API 端点

---

## Completion Report Format

```markdown
## Changes
- 权重变化表格（Before/After）
- DuckDB 修复说明

## Alpha Re-run Results
- 修改后 total_cp 的 IC 变化

## Tests
- 通过情况

## Calibration Script Output
- 建议权重
```
