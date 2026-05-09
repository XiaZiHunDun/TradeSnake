#!/usr/bin/env python3
"""K 线数据完整性检查与补充

功能:
1. 扫描 daily_kline 表，统计每年交易日覆盖
2. 对 2024-01 至今的数据做精确 gap 检测
3. 可选：使用 Tushare 补充缺失数据

用法:
  python scripts/check_and_fill_klines.py              # 仅检查
  python scripts/check_and_fill_klines.py --fill        # 检查+补充
  python scripts/check_and_fill_klines.py --start 2024-01-01 --end 2026-04-30
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.data_manager.duckdb_store import get_duckdb_store


def check_yearly_coverage(duckdb):
    """统计每年的交易日和股票覆盖"""
    conn = duckdb._get_read_conn()

    df = conn.execute("""
        SELECT
            EXTRACT(YEAR FROM trade_date) AS year,
            COUNT(DISTINCT trade_date) AS trading_days,
            COUNT(DISTINCT code) AS stocks,
            COUNT(*) AS total_rows,
            MIN(trade_date) AS first_date,
            MAX(trade_date) AS last_date
        FROM daily_kline
        GROUP BY EXTRACT(YEAR FROM trade_date)
        ORDER BY year
    """).df()

    print("=" * 80)
    print("K 线数据年度覆盖统计")
    print("=" * 80)
    print(f"{'年份':>6} {'交易日':>8} {'股票数':>8} {'总行数':>12} {'起始日':>12} {'截止日':>12}")
    print("-" * 80)

    for _, row in df.iterrows():
        print(f"{int(row['year']):>6} {int(row['trading_days']):>8} "
              f"{int(row['stocks']):>8} {int(row['total_rows']):>12} "
              f"{str(row['first_date'])[:10]:>12} {str(row['last_date'])[:10]:>12}")

    total = df['total_rows'].sum()
    print("-" * 80)
    print(f"{'合计':>6} {int(df['trading_days'].sum()):>8} — {int(total):>12}")

    return df


def check_recent_gaps(duckdb, start_date: str, end_date: str):
    """检测指定日期范围的 K 线数据 gap"""
    conn = duckdb._get_read_conn()

    dates_df = conn.execute("""
        SELECT DISTINCT trade_date
        FROM daily_kline
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, [start_date, end_date]).df()

    if dates_df.empty:
        print(f"\n[WARNING] {start_date} ~ {end_date} 范围内无任何数据!")
        return None

    dates = sorted(dates_df['trade_date'].tolist())
    first = str(dates[0])[:10]
    last = str(dates[-1])[:10]
    n_days = len(dates)

    print(f"\n{'=' * 80}")
    print(f"区间详细检查: {start_date} ~ {end_date}")
    print(f"{'=' * 80}")
    print(f"  交易日数量: {n_days}")
    print(f"  实际范围: {first} ~ {last}")

    # 每月统计
    monthly = conn.execute("""
        SELECT
            strftime(trade_date, '%Y-%m') AS month,
            COUNT(DISTINCT trade_date) AS days,
            COUNT(DISTINCT code) AS stocks,
            COUNT(*) AS rows
        FROM daily_kline
        WHERE trade_date >= ? AND trade_date <= ?
        GROUP BY strftime(trade_date, '%Y-%m')
        ORDER BY month
    """, [start_date, end_date]).df()

    print(f"\n  {'月份':>8} {'交易日':>8} {'股票数':>8} {'行数':>10}")
    print(f"  {'-' * 40}")
    for _, row in monthly.iterrows():
        print(f"  {row['month']:>8} {int(row['days']):>8} "
              f"{int(row['stocks']):>8} {int(row['rows']):>10}")

    # 检查连续日期 gap（超过 5 个自然日的间隔可能是异常）
    gaps = []
    for i in range(1, len(dates)):
        d0 = dates[i - 1]
        d1 = dates[i]
        if hasattr(d0, 'date'):
            d0 = d0.date()
        if hasattr(d1, 'date'):
            d1 = d1.date()
        if isinstance(d0, str):
            d0 = datetime.strptime(str(d0)[:10], '%Y-%m-%d').date()
        if isinstance(d1, str):
            d1 = datetime.strptime(str(d1)[:10], '%Y-%m-%d').date()
        delta = (d1 - d0).days
        if delta > 5:
            gaps.append((str(d0), str(d1), delta))

    if gaps:
        print(f"\n  大间隔（>5自然日，可能含长假）:")
        for g0, g1, delta in gaps:
            print(f"    {g0} → {g1}: {delta} 天")
    else:
        print(f"\n  无异常间隔（所有间隔 <= 5 自然日）")

    # 核心池股票覆盖率
    stock_coverage = conn.execute("""
        SELECT code, COUNT(DISTINCT trade_date) AS days
        FROM daily_kline
        WHERE trade_date >= ? AND trade_date <= ?
        GROUP BY code
        HAVING days < ?
        ORDER BY days
        LIMIT 20
    """, [start_date, end_date, n_days * 0.5]).df()

    if not stock_coverage.empty:
        print(f"\n  覆盖率低于 50% 的股票（前20）:")
        for _, row in stock_coverage.iterrows():
            pct = int(row['days']) / n_days * 100
            print(f"    {row['code']}: {int(row['days'])}/{n_days} 天 ({pct:.0f}%)")
    else:
        print(f"\n  所有股票覆盖率 >= 50%")

    # 总体 gap 比率
    expected_a_share = 250  # 每年约 250 个交易日
    start_y = int(start_date[:4])
    end_y = int(end_date[:4])
    years = max(0.5, (datetime.strptime(end_date, '%Y-%m-%d') -
                       datetime.strptime(start_date, '%Y-%m-%d')).days / 365)
    expected_days = int(expected_a_share * years)
    coverage = n_days / expected_days * 100 if expected_days > 0 else 0

    print(f"\n  交易日覆盖率: {n_days}/{expected_days} ({coverage:.1f}%)")

    return {
        'n_days': n_days,
        'first': first,
        'last': last,
        'gaps': gaps,
        'coverage_pct': coverage,
    }


def fill_gaps_tushare(duckdb, start_date: str, end_date: str):
    """使用 Tushare 补充缺失数据"""
    try:
        from backend.data_manager.filler import KlineFiller
        filler = KlineFiller()
        print(f"\n开始补充 K 线数据 ({start_date} ~ {end_date})...")
        filler.fill_all(limit=500, days_back=730)
        print("K 线补充完成")
    except Exception as e:
        print(f"[ERROR] K 线补充失败: {e}")
        print("可尝试手动运行: python scripts/fill_history.py")


def main():
    parser = argparse.ArgumentParser(description="K 线数据完整性检查")
    parser.add_argument("--start", default="2024-01-01", help="检查起始日期")
    parser.add_argument("--end", default="2026-04-30", help="检查截止日期")
    parser.add_argument("--fill", action="store_true", help="补充缺失数据")
    args = parser.parse_args()

    duckdb = get_duckdb_store()

    yearly = check_yearly_coverage(duckdb)
    result = check_recent_gaps(duckdb, args.start, args.end)

    if result:
        if result['coverage_pct'] < 95:
            print(f"\n[WARN] 覆盖率 {result['coverage_pct']:.1f}% < 95%，建议补充数据")
            if args.fill:
                fill_gaps_tushare(duckdb, args.start, args.end)
            else:
                print("  使用 --fill 参数自动补充")
        else:
            print(f"\n[OK] 覆盖率 {result['coverage_pct']:.1f}% >= 95%，数据充足")


if __name__ == "__main__":
    main()
