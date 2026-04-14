#!/usr/bin/env python
"""
历史日K线补充填充脚本（单线程，快速失败版）
- 强制所有HTTP请求最多等待20秒（防止代理挂起）
- 重置不完整状态
"""
import sys
import sqlite3
import duckdb
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "tradesnake.db"
DUCKDB_PATH = PROJECT_ROOT / "data" / "historical.duckdb"
MIN_RECORDS = 200
DAYS_BACK = 730
HTTP_TIMEOUT = 20  # 秒


# ===== 强制requests超时，防止代理无响应时永久挂起 =====
import requests
from requests.adapters import HTTPAdapter

_original_send = requests.Session.send

def _patched_send(self, request, **kwargs):
    if kwargs.get('timeout') is None:
        kwargs['timeout'] = HTTP_TIMEOUT
    return _original_send(self, request, **kwargs)

requests.Session.send = _patched_send
print(f"[补丁] HTTP请求超时已设为 {HTTP_TIMEOUT} 秒")


def reset_stuck_running(table: str):
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(f"UPDATE {table} SET status='pending', updated_at=datetime('now') WHERE status='running'")
    n = cur.rowcount
    conn.commit()
    conn.close()
    if n:
        print(f"[重置] {table}: {n} 条 running → pending")


def reset_incomplete_kline_status():
    db = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    rows = db.execute(
        f"SELECT code FROM (SELECT code, count(*) as cnt FROM daily_kline GROUP BY code) t WHERE cnt < {MIN_RECORDS}"
    ).fetchall()
    db.close()

    incomplete_codes = [r[0] for r in rows]
    print(f"[重置] 日K线不足（<{MIN_RECORDS}条）: {len(incomplete_codes)} 只 → pending")
    if not incomplete_codes:
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    batch_size = 500
    total_reset = 0
    for i in range(0, len(incomplete_codes), batch_size):
        batch = incomplete_codes[i:i + batch_size]
        placeholders = ','.join(['?' for _ in batch])
        cur.execute(
            f"UPDATE kline_fill_status SET status='pending', updated_at=datetime('now') WHERE code IN ({placeholders})",
            batch
        )
        total_reset += cur.rowcount
    cur.execute("UPDATE kline_fill_status SET status='pending', updated_at=datetime('now') WHERE last_date IS NULL AND status='completed'")
    total_reset += cur.rowcount
    conn.commit()
    conn.close()
    print(f"[重置] 共重置 {total_reset} 条记录")


def main():
    print("=" * 60)
    print("历史日K线补充填充（单线程，快速失败）")
    print("=" * 60)

    reset_stuck_running("kline_fill_status")
    reset_stuck_running("minute_kline_fill_status")
    reset_incomplete_kline_status()

    from backend.data_manager.filler import KlineFiller
    filler = KlineFiller(rate_limit_sleep=0.3)
    codes = filler._get_stock_codes()
    total = len(codes)
    print(f"\n[开始] 共 {total} 只股票，历史 {DAYS_BACK} 天，max_retries=1")

    success = failed = skipped = records = 0
    start_time = time.time()

    for i, code in enumerate(codes, 1):
        try:
            count, status = filler.fill_stock(code, days_back=DAYS_BACK, max_retries=1)
            records += count
            if status == 'success':
                success += 1
            elif status == 'skipped':
                skipped += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1

        if i % 50 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed * 60
            remaining_stocks = total - i
            remaining_min = remaining_stocks / (i / elapsed) if elapsed > 0 else 0
            print(f"进度: {i}/{total} | 成功:{success} 跳过:{skipped} 失败:{failed} "
                  f"记录:{records} | 速度:{rate:.0f}只/分 | 预计剩余:{remaining_min/60:.1f}时")

    elapsed = time.time() - start_time
    print(f"\n[完成] 耗时:{elapsed/60:.1f}分 | 成功:{success} 跳过:{skipped} 失败:{failed} 总记录:{records}")

    # 验证
    db = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    row = db.execute("""
        SELECT
            SUM(CASE WHEN cnt < 10   THEN 1 ELSE 0 END),
            SUM(CASE WHEN cnt >= 200 THEN 1 ELSE 0 END),
            SUM(CASE WHEN cnt >= 400 THEN 1 ELSE 0 END),
            count(*)
        FROM (SELECT code, count(*) as cnt FROM daily_kline GROUP BY code) t
    """).fetchone()
    db.close()
    print(f"[验证] 总:{row[3]} | <10条:{row[0]} | 200+条:{row[1]} | 400+条:{row[2]}")
    print("全部完成!")


if __name__ == "__main__":
    main()
