#!/usr/bin/env python
"""
批量生成预测数据脚本

为核心池所有股票生成涨幅预测和上涨概率预测，并保存到 prediction DB。
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))

import sqlite3
import duckdb
from datetime import datetime, date
from dataclasses import asdict
from typing import List, Dict

from backend.engine.gain_predictor.predictor import GainPredictor
from backend.engine.probability_predictor.predictor import ProbabilityPredictor
from backend.data_manager.prediction_store import PredictionStore


def normalize_code(code: str) -> str:
    """标准化股票代码：去除sh/sz前缀，匹配DuckDB格式"""
    code = str(code)
    if code.startswith('sh') or code.startswith('sz'):
        return code[2:]
    return code


def get_core_pool_stocks() -> List[Dict]:
    """SQLite 中 total_cp>0 的股票（非 StockSelector 的 PoolTier.CORE）。"""
    conn = sqlite3.connect(str(PROJECT_ROOT / 'data' / 'tradesnake.db'))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT code, name, total_cp FROM stocks WHERE total_cp > 0 ORDER BY total_cp DESC')
    stocks = [dict(r) for r in cur.fetchall()]
    conn.close()
    return stocks


def fetch_klines_batch(codes: List[str], days: int = 60) -> Dict[str, List[Dict]]:
    """从 DuckDB 批量获取K线数据

    Args:
        codes: 原始股票代码列表（可能带sh/sz前缀）
        days: 获取最近N日K线

    Returns:
        {原始代码: [klines]} 保持原始代码格式作为key
    """
    if not codes:
        return {}

    # 建立原始代码 -> 标准化代码的映射
    orig_to_norm = {c: normalize_code(c) for c in codes}
    normalized_codes = list(orig_to_norm.values())

    conn = duckdb.connect(str(PROJECT_ROOT / 'data' / 'historical.duckdb'), read_only=True)

    placeholders = ', '.join(['?' for _ in normalized_codes])
    query = f"""
        SELECT code, trade_date, open, high, low, close, volume, change_pct
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY code ORDER BY trade_date DESC) AS rn
            FROM daily_kline
            WHERE code IN ({placeholders})
        ) t
        WHERE rn <= {days}
        ORDER BY code, trade_date ASC
    """
    rows = conn.execute(query, normalized_codes).fetchall()
    conn.close()

    # 建立标准化代码 -> 原始代码的反向映射
    norm_to_orig = {v: k for k, v in orig_to_norm.items()}

    # 使用原始代码作为key构建结果
    klines_dict = {}
    for row in rows:
        norm_code, trade_date, open_, high, low, close, volume, change_pct = row
        # 转换为原始代码
        orig_code = norm_to_orig.get(norm_code, norm_code)
        if orig_code not in klines_dict:
            klines_dict[orig_code] = []
        klines_dict[orig_code].append({
            'date': str(trade_date),
            'open': float(open_) if open_ is not None else 0.0,
            'high': float(high) if high is not None else 0.0,
            'low': float(low) if low is not None else 0.0,
            'close': float(close) if close is not None else 0.0,
            'volume': float(volume) if volume is not None else 0.0,
            'change_pct': float(change_pct) if change_pct is not None else 0.0,
        })

    return klines_dict


def prediction_to_dict(pred) -> Dict:
    """将预测 dataclass 转为 dict"""
    return asdict(pred)


def run(batch_size: int = 100):
    today = date.today().strftime('%Y-%m-%d')
    print(f"=== 批量生成预测数据 [{today}] ===\n")

    stocks = get_core_pool_stocks()
    print(f"核心池股票: {len(stocks)} 只")

    codes = [s['code'] for s in stocks]
    name_map = {s['code']: s['name'] for s in stocks}

    gain_predictor = GainPredictor()
    prob_predictor = ProbabilityPredictor()
    store = PredictionStore()

    all_gain_preds = []
    all_prob_preds = []

    total_batches = (len(codes) + batch_size - 1) // batch_size
    for i in range(0, len(codes), batch_size):
        batch_codes = codes[i:i+batch_size]
        batch_num = i // batch_size + 1
        print(f"  处理批次 {batch_num}/{total_batches}: {len(batch_codes)} 只股票...", end='', flush=True)

        klines_dict = fetch_klines_batch(batch_codes, days=60)

        # 只预测有足够K线数据的股票
        valid_klines = {code: klines for code, klines in klines_dict.items() if len(klines) >= 5}
        if not valid_klines:
            print(f" (无有效K线数据，跳过)")
            continue

        # 涨幅预测
        gain_result = gain_predictor.predict(valid_klines)
        for pred in gain_result.predictions:
            d = prediction_to_dict(pred)
            # 确保name字段存在
            if not d.get('name'):
                d['name'] = name_map.get(pred.code, pred.code)
            all_gain_preds.append(d)

        # 概率预测
        prob_result = prob_predictor.predict(valid_klines)
        for pred in prob_result.predictions:
            d = prediction_to_dict(pred)
            if not d.get('name'):
                d['name'] = name_map.get(pred.code, pred.code)
            all_prob_preds.append(d)

        print(f" 完成 (涨幅:{len(gain_result.predictions)}, 概率:{len(prob_result.predictions)})")

    # 保存到 DB
    print(f"\n保存涨幅预测 {len(all_gain_preds)} 条...")
    n1 = store.record_gain_predictions(all_gain_preds, date=today)
    print(f"保存概率预测 {len(all_prob_preds)} 条...")
    n2 = store.record_probability_predictions(all_prob_preds, date=today)

    print(f"\n✅ 完成! 涨幅预测: {n1} 只, 概率预测: {n2} 只")

    # 验证
    conn = sqlite3.connect(str(PROJECT_ROOT / 'data' / 'tradesnake_prediction.db'))
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM gain_predictions WHERE recorded_at = ?', (today,))
    print(f"   gain_predictions [{today}]: {cur.fetchone()[0]} 条")
    cur.execute('SELECT COUNT(*) FROM probability_predictions WHERE recorded_at = ?', (today,))
    print(f"   probability_predictions [{today}]: {cur.fetchone()[0]} 条")
    conn.close()


if __name__ == '__main__':
    run()
