#!/usr/bin/env python3
"""批量回填历史 CP 分数

利用 DuckDB 中已有的 16 年 K 线数据，使用 CPEngine 计算历史每个交易日的
全市场 CP 排名，写入 cp_history 表。

已知限制:
- 财务因子 (PE/ROE) 使用当前值而非时点值，Growth/Value/Quality 有轻微前瞻偏差
- Momentum 完全基于 K 线计算，无前瞻偏差

用法:
  python scripts/backfill_cp_history.py                                  # 默认回填 2024-04 至今
  python scripts/backfill_cp_history.py --start 2025-01-01 --end 2026-04-23
  python scripts/backfill_cp_history.py --batch-size 20 --force          # 强制重算
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.data_manager.duckdb_store import get_duckdb_store


def get_trading_dates(duckdb, start_date: str, end_date: str):
    """从 daily_kline 获取交易日历"""
    conn = duckdb._get_read_conn()
    df = conn.execute("""
        SELECT DISTINCT trade_date
        FROM daily_kline
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """, [start_date, end_date]).df()

    if df.empty:
        return []

    dates = []
    for d in df['trade_date'].tolist():
        ds = str(d)[:10]
        dates.append(ds)
    return dates


def main():
    parser = argparse.ArgumentParser(description="批量回填历史 CP 分数")
    parser.add_argument("--start", default="2024-04-01",
                        help="起始日期 (默认 2024-04-01，此前仅 15 只股票)")
    parser.add_argument("--end", default="2026-04-23",
                        help="截止日期")
    parser.add_argument("--batch-size", type=int, default=30,
                        help="每批处理天数 (默认 30)")
    parser.add_argument("--force", action="store_true",
                        help="强制重算已有数据")
    parser.add_argument("--codes", type=str, default=None,
                        help="指定股票代码，逗号分隔 (默认核心池)")
    parser.add_argument("--max-stocks", type=int, default=500,
                        help="每日最大股票数 (默认 500，0=不限)")
    args = parser.parse_args()

    print("=" * 70)
    print("CP 历史回填")
    print("=" * 70)
    print(f"  范围: {args.start} ~ {args.end}")
    print(f"  批次大小: {args.batch_size} 天")
    print(f"  强制重算: {args.force}")

    duckdb = get_duckdb_store()
    all_dates = get_trading_dates(duckdb, args.start, args.end)

    if not all_dates:
        print("[ERROR] 指定范围内无交易日数据")
        return

    print(f"  交易日总数: {len(all_dates)}")
    print(f"  日期范围: {all_dates[0]} ~ {all_dates[-1]}")

    # 检查已有 CP 历史
    from backend.data_manager.cp_history_store import get_cp_history_store
    cp_store = get_cp_history_store()
    existing_dates = set(cp_store.get_available_dates())
    new_dates = [d for d in all_dates if d not in existing_dates or args.force]

    print(f"  已有 CP 快照: {len(existing_dates & set(all_dates))} 天")
    print(f"  需要计算: {len(new_dates)} 天")

    if not new_dates and not args.force:
        print("\n[OK] 所有日期已有数据，无需回填。使用 --force 强制重算。")
        return

    # 解析指定的 codes；默认从 daily_kline 获取有充足数据的股票
    codes = None
    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        print(f"  指定股票: {len(codes)} 只")
    else:
        conn = duckdb._get_read_conn()
        min_days = min(30, max(1, len(all_dates) // 3))
        codes_df = conn.execute("""
            SELECT code, COUNT(DISTINCT trade_date) AS days
            FROM daily_kline
            WHERE trade_date >= ? AND trade_date <= ?
            GROUP BY code
            HAVING days >= ?
            ORDER BY days DESC
        """, [args.start, args.end, min_days]).df()
        if not codes_df.empty:
            codes = codes_df['code'].tolist()
        if codes and args.max_stocks > 0 and len(codes) > args.max_stocks:
            codes = codes[:args.max_stocks]
        print(f"  数据充足的股票 (>={min_days}天): {len(codes) if codes else 0} 只")

    if not codes:
        print("[ERROR] 无有效股票代码")
        return

    # 分批执行
    from backend.data_manager.filler import CPHistoryBatchCalculator

    calculator = CPHistoryBatchCalculator()
    total_success = 0
    total_failed = 0
    total_skipped = 0
    start_time = time.time()

    n_batches = (len(new_dates) + args.batch_size - 1) // args.batch_size

    for batch_idx in range(n_batches):
        batch_start = batch_idx * args.batch_size
        batch_end = min(batch_start + args.batch_size, len(new_dates))
        batch_dates = new_dates[batch_start:batch_end]

        batch_t0 = time.time()
        print(f"\n--- 批次 {batch_idx + 1}/{n_batches}: "
              f"{batch_dates[0]} ~ {batch_dates[-1]} ({len(batch_dates)} 天) ---")

        result = calculator.calculate_historical_cp(
            dates=batch_dates,
            codes=codes,
            force_recalculate=args.force,
        )

        batch_elapsed = time.time() - batch_t0
        total_success += result.success
        total_failed += result.failed
        total_skipped += result.skipped

        print(f"  成功: {result.success}, 失败: {result.failed}, "
              f"跳过: {result.skipped}, 耗时: {batch_elapsed:.1f}s")

        if result.errors:
            for err in result.errors[:3]:
                print(f"  [ERROR] {err}")

        # 进度估算
        elapsed = time.time() - start_time
        done = batch_end
        remaining = len(new_dates) - done
        if done > 0:
            rate = elapsed / done
            eta = rate * remaining
            print(f"  进度: {done}/{len(new_dates)} ({done/len(new_dates)*100:.0f}%), "
                  f"预计剩余: {eta/60:.1f} 分钟")

    total_elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("回填完成")
    print("=" * 70)
    print(f"  总成功: {total_success} 条记录")
    print(f"  总失败: {total_failed} 天")
    print(f"  总跳过: {total_skipped} 条")
    print(f"  总耗时: {total_elapsed/60:.1f} 分钟")

    # 验证
    updated_dates = cp_store.get_available_dates()
    print(f"\n  CP 历史总天数: {len(updated_dates)}")
    if updated_dates:
        print(f"  CP 历史范围: {updated_dates[0]} ~ {updated_dates[-1]}")


if __name__ == "__main__":
    main()
