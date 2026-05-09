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