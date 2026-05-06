#!/usr/bin/env python
"""
完整回测验证报告

运行:
  python scripts/full_backtest_report.py --start 2025-01-01 --end 2026-04-28
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Full Walk-Forward Backtest Report")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--top-n", type=int, default=6, help="Portfolio size")
    parser.add_argument("--rebalance", type=int, default=10, help="Rebalance frequency (days)")
    parser.add_argument("--stop-loss", type=float, default=-0.07, help="Stop loss threshold")
    args = parser.parse_args()

    from backend.backtester.walk_forward import WalkForwardBacktester, WalkForwardConfig

    config = WalkForwardConfig(
        top_n=args.top_n,
        rebalance_freq=args.rebalance,
        stop_loss=args.stop_loss,
    )

    print("Running walk-forward backtest ...")
    backtester = WalkForwardBacktester(config)
    report = backtester.run(args.start, args.end)

    if not report.folds:
        print("No folds completed. Need at least 140 trading dates of data.")
        print("Check that CP history and DuckDB K-line data cover the date range.")
        return

    print(report.summary())

    print("\n## Fold Details")
    print(f"{'Fold':>5} {'Train':>22} {'Test':>22} {'Return':>10} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>7}")
    print("-" * 84)
    for f in report.folds:
        print(f"{f.fold_id:>5} {f.train_start}~{f.train_end} {f.test_start}~{f.test_end} "
              f"{f.total_return:>9.2f}% {f.sharpe:>7.2f} {f.max_drawdown:>7.2f}% {f.n_trades:>6}")

    print("\n## Benchmark Comparison")
    try:
        from backend.backtester.benchmark import BenchmarkProvider
        bm = BenchmarkProvider()
        for name in ["hs300", "equal_weight"]:
            bm_rets = bm.get_benchmark_returns(name, args.start, args.end)
            if bm_rets:
                import numpy as np
                vals = list(bm_rets.values())
                cum = np.prod([1 + r for r in vals])
                bm_total = (cum - 1) * 100
                n = len(vals)
                bm_annual = (cum ** (250 / n) - 1) * 100 if n > 0 else 0
                print(f"  {name:<15}: total={bm_total:>8.2f}% annual={bm_annual:>8.2f}% ({n} days)")
            else:
                print(f"  {name:<15}: no data")
    except Exception as e:
        print(f"  Benchmark data unavailable: {e}")

    print("\n## Verdict")
    if report.sharpe > 1.0:
        print("  Strategy shows promising risk-adjusted returns (Sharpe > 1).")
    elif report.sharpe > 0.5:
        print("  Strategy has moderate risk-adjusted returns (Sharpe 0.5-1.0).")
    elif report.sharpe > 0:
        print("  Strategy is positive but weak (Sharpe < 0.5). Consider weight optimization.")
    else:
        print("  Strategy is not profitable on a risk-adjusted basis (Sharpe < 0).")

    if report.max_drawdown > 20:
        print(f"  WARNING: Max drawdown ({report.max_drawdown:.1f}%) exceeds 20%. Tighten stop-loss.")
    if report.fee_ratio > 2:
        print(f"  WARNING: Fee ratio ({report.fee_ratio:.2f}%) is high. Reduce turnover.")


if __name__ == "__main__":
    main()
