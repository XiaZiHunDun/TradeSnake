"""
Alpha 因子分析报告
运行: python scripts/alpha_analysis.py [--start 2025-01-01] [--end 2026-04-28]

用数据回答：哪些因子在 A 股有真实的预测能力？
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from backend.backtester.alpha_analyzer import AlphaAnalyzer


def main():
    parser = argparse.ArgumentParser(description='Factor Alpha Analysis')
    parser.add_argument('--start', default=None, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', default=None, help='End date (YYYY-MM-DD)')
    parser.add_argument('--horizon', type=int, default=5, help='Return horizon in trading days')
    parser.add_argument('--tech-factors', action='store_true', help='Also analyze technical factors')
    args = parser.parse_args()

    print("=" * 60)
    print("TradeSnake Factor Alpha Analysis Report")
    print("=" * 60)

    try:
        analyzer = AlphaAnalyzer()
    except Exception as e:
        print(f"Error initializing AlphaAnalyzer: {e}")
        sys.exit(1)

    # 检查数据是否充足
    dates = analyzer.cp_store.get_available_dates()
    if args.start:
        dates = [d for d in dates if d >= args.start]
    if args.end:
        dates = [d for d in dates if d <= args.end]
    if len(dates) < 30:
        print(f"\nNeed at least 30 dates of CP history data, but only got {len(dates)}.")
        print("Please ensure cp_history_store and daily_kline tables have data.")
        sys.exit(0)

    print(f"\nAnalysis period: {dates[0]} ~ {dates[-1]} ({len(dates)} trading days)")

    # 1. Factor IC
    print(f"\n## Factor IC Analysis (horizon = {args.horizon} days)")
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
    print(f"\n## Quintile Group Returns (horizon = {args.horizon} days, annualized %)")
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

    # 5. Tech factor IC (optional)
    if args.tech_factors:
        print(f"\n## Technical Factor IC Analysis (horizon = {args.horizon} days)")
        print(f"{'Factor':<20} {'Mean IC':>10} {'IC Std':>10} {'ICIR':>10} {'t-stat':>10} {'IC>0%':>10}")
        print("-" * 70)

        for factor in AlphaAnalyzer.TECH_FACTORS:
            result = analyzer.compute_tech_factor_ic(factor, horizon=args.horizon,
                                                     start_date=args.start, end_date=args.end)
            print(f"{result.factor_name:<20} {result.mean_ic:>10.4f} {result.ic_std:>10.4f} "
                  f"{result.icir:>10.4f} {result.t_stat:>10.2f} {result.ic_positive_ratio*100:>9.1f}%")


if __name__ == '__main__':
    main()