#!/usr/bin/env python
"""
K线历史数据填充脚本
====================
从Tushare获取股票历史K线数据并存储到DuckDB

用法:
    python scripts/fill_kline_data.py              # 填充所有股票
    python scripts/fill_kline_data.py --limit 50  # 只填充前50只
    python scripts/fill_kline_data.py --code 000001  # 只填充指定股票
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta

# 设置代理（支持环境变量覆盖）
_PROXY = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY') or 'http://192.168.13.218:10808'
os.environ['http_proxy'] = _PROXY
os.environ['https_proxy'] = _PROXY

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.data_manager.duckdb_store import get_duckdb_store, DuckDBStore
from backend.data_manager.providers.tushare import TushareProvider
from backend.data_manager import get_stock_list
import pandas as pd


def convert_tushare_to_kline(df: pd.DataFrame) -> pd.DataFrame:
    """将Tushare数据转换为DuckDB格式"""
    if df.empty:
        return pd.DataFrame()

    result = pd.DataFrame()
    result['code'] = df['ts_code'].str.split('.').str[0]
    result['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.date
    result['open'] = df['open'].astype(float)
    result['high'] = df['high'].astype(float)
    result['low'] = df['low'].astype(float)
    result['close'] = df['close'].astype(float)
    result['volume'] = df['volume'].astype(float).astype(int)
    result['amount'] = df['amount'].astype(float)
    result['change_pct'] = df['change_pct'].astype(float)

    return result


def fill_stock_klines(provider: TushareProvider, store: DuckDBStore, code: str,
                      start_date: str, end_date: str, days: int = 300) -> int:
    """填充单只股票的K线数据"""
    try:
        klines = provider.get_daily_kline(code, start_date, end_date)
        if not klines:
            return 0

        df = pd.DataFrame(klines)
        converted = convert_tushare_to_kline(df)
        inserted = store.insert_from_dataframe(converted, 'daily_kline')
        return inserted
    except Exception as e:
        print(f"  错误 {code}: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description='填充K线历史数据')
    parser.add_argument('--limit', type=int, default=None, help='限制股票数量')
    parser.add_argument('--code', type=str, default=None, help='指定股票代码')
    parser.add_argument('--days', type=int, default=300, help='获取天数')
    args = parser.parse_args()

    # 初始化
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 初始化...")
    provider = TushareProvider()
    store = get_duckdb_store()

    if not provider.pro:
        print("错误: Tushare API 不可用")
        return

    # 获取日期范围
    end_date = datetime.today().strftime('%Y%m%d')
    start_date = (datetime.today() - timedelta(days=args.days)).strftime('%Y%m%d')

    # 获取股票列表
    if args.code:
        stocks = [{'code': args.code}]
    else:
        stocks = get_stock_list()

    if args.limit:
        stocks = stocks[:args.limit]

    total = len(stocks)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始填充 {total} 只股票的历史数据...")
    print(f"  日期范围: {start_date} ~ {end_date}")

    success = 0
    failed = 0
    total_inserted = 0

    for i, stock in enumerate(stocks):
        code = stock.get('code', '')
        name = stock.get('name', '')

        # 进度
        if (i + 1) % 10 == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 进度: {i+1}/{total}")

        # 获取并存储
        inserted = fill_stock_klines(provider, store, code, start_date, end_date, args.days)
        if inserted > 0:
            success += 1
            total_inserted += inserted
        else:
            failed += 1

        # Tushare限制: 120次/分钟, 等待一下
        time.sleep(0.06)

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 完成!")
    print(f"  成功: {success} 只")
    print(f"  失败: {failed} 只")
    print(f"  总插入: {total_inserted} 条")


if __name__ == '__main__':
    main()
