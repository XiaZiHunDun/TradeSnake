# 任务：Alpha 验证工具（P2）

> 日期：2026-04-28  
> 类型：Analysis Tooling + Data Validation（中等风险）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：P1 Bug 修复完成后执行（动量因子恢复后再验证）

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

**本任务的目标不是修改策略，而是创建分析工具来回答"哪些因子能赚钱"。**

---

## Goal

创建一套 Factor Alpha 验证工具集，包含：

1. **因子 IC 分析脚本** — 每个因子与未来 N 日收益的 Spearman 相关系数（时间序列）
2. **分组回测脚本** — 按因子分 5 组，计算各组平均收益
3. **信号衰减分析** — 因子信号在 1/3/5/10/20 天后的 IC 变化
4. **综合报告生成** — 输出可读的分析报告

完成后：用户可以运行 `python scripts/alpha_analysis.py` 得到每个因子的 alpha 诊断报告。

---

## Context

### 数据来源

- **因子数据**：`cp_history_store`（SQLite）— 记录了每天每只股票的 total_cp、growth_score、value_score、quality_score、momentum_score
- **收益数据**：`duckdb_store`（DuckDB）— 日线 K 线数据，包含 close、volume 等
- **已有的 Factor IC**：`/api/backtest/factor_analysis` 端点和 `FactorAttributor` 类已有基础 IC 计算能力，但缺少时间序列分析和衰减分析

### 核心问题

我们要回答：
1. growth_score 能预测未来 5 天的收益吗？IC 是多少？
2. value_score 呢？quality_score？momentum_score？
3. 哪个因子的 IC 最高（最有预测力）？
4. IC 随时间衰减吗？（如果因子信号只在 1 天内有效，那按 5 天换仓就太慢了）
5. 高因子组真的跑赢低因子组吗？多少 bps？

---

## Scope

Allowed changes:

- 创建 `scripts/alpha_analysis.py`（主分析脚本）
- 创建 `backend/backtester/alpha_analyzer.py`（可复用的分析模块）
- 修改 `backend/backtester/factor_attributor.py`（增强 IC 分析能力）

Out of scope:

- 不修改 CP 公式或权重（本任务只分析，不改策略）
- 不修改 API 端点
- 不修改前端

---

## Steps

### Step 1: 创建 AlphaAnalyzer 类

- [ ] 创建 `backend/backtester/alpha_analyzer.py`

```python
"""Alpha 因子验证分析器

用数据回答：哪些因子在 A 股有真实的预测能力？
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from scipy import stats


@dataclass
class FactorICResult:
    """单因子 IC 分析结果"""
    factor_name: str
    mean_ic: float           # 时间序列 IC 均值
    ic_std: float            # IC 标准差
    icir: float              # IC / IC_std（越高越稳定）
    ic_positive_ratio: float # IC > 0 的日期比例
    ic_series: List[float]   # 逐日 IC 序列
    t_stat: float            # t 统计量（IC 显著性）
    p_value: float           # p 值


@dataclass
class DecayResult:
    """信号衰减分析结果"""
    factor_name: str
    horizons: List[int]       # [1, 3, 5, 10, 20] 天
    ic_by_horizon: List[float] # 各 horizon 的 IC
    half_life_days: Optional[float]  # IC 半衰期（天）


@dataclass
class GroupResult:
    """分组回测结果"""
    factor_name: str
    group_count: int          # 组数（通常 5）
    group_returns: List[float]  # 各组平均日收益（%）
    long_short_spread: float  # 多空组收益差（%）
    monotonic: bool           # 收益是否单调（高分组 > 低分组）


class AlphaAnalyzer:
    """因子 Alpha 分析器"""
    
    FACTORS = ['total_cp', 'growth_score', 'value_score', 
               'quality_score', 'momentum_score']
    HORIZONS = [1, 3, 5, 10, 20]  # 收益计算窗口（交易日）
    GROUP_COUNT = 5  # 分位数分组
    
    def __init__(self):
        from backend.data_manager.cp_history_store import get_cp_history_store
        from backend.data_manager.duckdb_store import get_duckdb_store
        self.cp_store = get_cp_history_store()
        self.duckdb = get_duckdb_store()
    
    def compute_factor_ic(self, factor_name, horizon=5, 
                          start_date=None, end_date=None):
        """计算单因子时间序列 IC"""
        ...
    
    def compute_decay(self, factor_name, start_date=None, end_date=None):
        """计算信号衰减曲线"""
        ...
    
    def compute_group_returns(self, factor_name, horizon=5,
                              start_date=None, end_date=None):
        """分组回测"""
        ...
    
    def full_report(self, start_date=None, end_date=None):
        """生成完整报告"""
        ...
```

### Step 2: 实现 Factor IC 计算

- [ ] 实现 `compute_factor_ic`：
  1. 从 `cp_history_store` 获取每天的因子截面数据
  2. 从 `duckdb_store` 获取对应日期后 `horizon` 天的收益率
  3. 对每个日期计算 Spearman Rank IC（因子值 vs 未来收益）
  4. 返回 IC 时间序列的统计摘要

关键实现细节：
- IC = Spearman(factor_t, return_{t+1:t+horizon})
- 每天的 IC 是一个数（因子截面 vs 收益截面的 rank 相关）
- ICIR = mean(IC) / std(IC)，ICIR > 0.5 通常被认为有用
- t_stat = mean(IC) / (std(IC) / sqrt(n))，|t| > 2 为显著

### Step 3: 实现信号衰减分析

- [ ] 实现 `compute_decay`：
  1. 对同一因子，分别计算 horizon = 1, 3, 5, 10, 20 天的 IC
  2. 画出 IC 随 horizon 的变化
  3. 如果 IC 在 1-3 天最强然后快速衰减 → 短期信号（适合频繁换仓）
  4. 如果 IC 在 10-20 天仍强 → 中期信号（适合低频换仓）

### Step 4: 实现分组回测

- [ ] 实现 `compute_group_returns`：
  1. 每天按因子值排序，分 5 组（Q1=最低 20%, Q5=最高 20%）
  2. 计算每组在 horizon 天后的平均收益率
  3. Long-short spread = Q5 平均收益 - Q1 平均收益
  4. 检查收益是否单调递增（Q1 < Q2 < ... < Q5）

### Step 5: 创建分析脚本

- [ ] 创建 `scripts/alpha_analysis.py`

```python
"""
Alpha 因子分析报告
运行: python scripts/alpha_analysis.py [--start 2025-01-01] [--end 2026-04-28]
"""
import argparse
from backend.backtester.alpha_analyzer import AlphaAnalyzer

def main():
    parser = argparse.ArgumentParser(description='Factor Alpha Analysis')
    parser.add_argument('--start', default=None, help='Start date')
    parser.add_argument('--end', default=None, help='End date')
    parser.add_argument('--horizon', type=int, default=5, help='Return horizon')
    args = parser.parse_args()
    
    analyzer = AlphaAnalyzer()
    
    print("=" * 60)
    print("TradeSnake Factor Alpha Analysis Report")
    print("=" * 60)
    
    # 1. Factor IC
    print("\n## Factor IC Analysis (horizon = {} days)".format(args.horizon))
    print(f"{'Factor':<20} {'Mean IC':>10} {'IC Std':>10} {'ICIR':>10} {'t-stat':>10} {'IC>0%':>10}")
    print("-" * 70)
    
    for factor in AlphaAnalyzer.FACTORS:
        result = analyzer.compute_factor_ic(factor, horizon=args.horizon,
                                            start_date=args.start, end_date=args.end)
        print(f"{result.factor_name:<20} {result.mean_ic:>10.4f} {result.ic_std:>10.4f} "
              f"{result.icir:>10.4f} {result.t_stat:>10.2f} {result.ic_positive_ratio*100:>9.1f}%")
    
    # 2. Decay analysis
    print("\n## Signal Decay Analysis")
    for factor in AlphaAnalyzer.FACTORS:
        decay = analyzer.compute_decay(factor, start_date=args.start, end_date=args.end)
        ic_str = " | ".join(f"{h}d:{ic:.4f}" for h, ic in zip(decay.horizons, decay.ic_by_horizon))
        half_life = f"{decay.half_life_days:.1f}d" if decay.half_life_days else "N/A"
        print(f"  {factor:<20}: {ic_str}  (half-life: {half_life})")
    
    # 3. Group returns
    print("\n## Quintile Group Returns (horizon = {} days, annualized %)".format(args.horizon))
    print(f"{'Factor':<20} {'Q1(low)':>10} {'Q2':>10} {'Q3':>10} {'Q4':>10} {'Q5(high)':>10} {'L/S':>10} {'Mono?':>6}")
    print("-" * 96)
    
    for factor in AlphaAnalyzer.FACTORS:
        group = analyzer.compute_group_returns(factor, horizon=args.horizon,
                                               start_date=args.start, end_date=args.end)
        ann = [r * 250 / args.horizon for r in group.group_returns]
        ls_ann = group.long_short_spread * 250 / args.horizon
        mono = "Yes" if group.monotonic else "No"
        vals = " ".join(f"{r:>10.2f}" for r in ann)
        print(f"{factor:<20} {vals} {ls_ann:>10.2f} {mono:>6}")
    
    # 4. Conclusion
    print("\n## Key Findings")
    print("  (以上数据由脚本自动生成，需要人工解读)")
    print("  - ICIR > 0.5 的因子值得给更高权重")
    print("  - 信号衰减快的因子需要更频繁的换仓")
    print("  - Long-short 正且单调的因子是真正的 alpha 来源")
    print("  - IC 不显著(|t| < 2)的因子可能只是噪声")

if __name__ == '__main__':
    main()
```

### Step 6: 验证

- [ ] 确认 `cp_history_store` 有数据（如果没有，脚本应优雅地提示"数据不足"）
- [ ] `python scripts/alpha_analysis.py --help` 能运行
- [ ] 如果有数据：`python scripts/alpha_analysis.py` 能输出报告
- [ ] 如果没数据：脚本应打印"Need at least 30 dates of CP history data"
- [ ] `python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py`

---

## Verification

```bash
# 模块导入
python -c "from backend.backtester.alpha_analyzer import AlphaAnalyzer; print('OK')"

# 脚本帮助
python scripts/alpha_analysis.py --help

# 尝试运行（可能因数据不足而输出提示，这是正常的）
python scripts/alpha_analysis.py 2>&1 | head -20

# 既有测试不受影响
python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py
python -m pytest tests/backtester/ -v
```

---

## Completion Report Format

```markdown
## Summary
- 创建的文件
- 分析工具的能力说明

## Alpha Analysis Results（如果有数据）
- 各因子 IC 表格
- 衰减分析
- 分组回测

## If No Data Available
- 说明需要什么数据
- 如何生成测试数据

## Verification
- 测试结果

## Key Insight for Strategy
- 基于数据的策略建议（如果有分析结果）
```
