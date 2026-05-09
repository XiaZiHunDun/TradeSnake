"""补充历史预测数据

从 prediction_store 缺失的日期补充预测数据
使用每日收盘后的 K 线数据进行预测并保存

Usage:
    python scripts/backfill_predictions.py
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.data_manager.duckdb_store import get_duckdb_store
from backend.engine.gain_predictor.predictor import GainPredictor
from backend.engine.probability_predictor.predictor import ProbabilityPredictor
from backend.data_manager.prediction_store import get_prediction_store


def fill_predictions_for_date(date: str, codes: list, lookback: int = 60):
    """为指定日期填充所有股票的预测

    Args:
        date: 预测日期 (YYYY-MM-DD)
        codes: 股票代码列表
        lookback: 回看天数
    """
    if not codes:
        return 0, 0

    gain_pred = GainPredictor()
    prob_pred = ProbabilityPredictor()
    duckdb = get_duckdb_store()

    # 获取之前 lookback 天的 K 线数据
    end_dt = datetime.strptime(date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=lookback + 30)
    start_str = start_dt.strftime("%Y-%m-%d")

    klines_dict = {}
    for code in codes:
        result = duckdb.get_klines(code, start_date=start_str, end_date=date)
        if result.success and result.data is not None and len(result.data) >= 30:
            df = result.data.sort_values('trade_date').tail(lookback + 30)
            klines_dict[code] = df.to_dict('records')

    if not klines_dict:
        return 0, 0

    # 预测
    gain_result = gain_pred.predict(klines_dict)
    prob_result = prob_pred.predict(klines_dict)

    saved_gain = 0
    saved_prob = 0

    if gain_result and gain_result.predictions:
        saved_gain = gain_pred.save_to_store(gain_result, date)
    if prob_result and prob_result.predictions:
        saved_prob = prob_pred.save_to_store(prob_result, date)

    return saved_gain, saved_prob


def main():
    import sqlite3

    # 获取缺失的日期
    conn = sqlite3.connect('/home/ailearn/projects/TradeSnake/data/tradesnake_prediction.db')
    cursor = conn.cursor()

    cursor.execute('SELECT DISTINCT recorded_at FROM gain_predictions ORDER BY recorded_at')
    existing_dates = set(row[0] for row in cursor.fetchall())
    conn.close()

    # 获取 CP history 日期作为参考
    conn2 = sqlite3.connect('/home/ailearn/projects/TradeSnake/data/tradesnake_cp_history.db')
    cursor2 = conn2.cursor()
    cursor2.execute('SELECT DISTINCT recorded_at FROM cp_history ORDER BY recorded_at')
    cp_dates = sorted(set(row[0] for row in cursor2.fetchall()))
    conn2.close()

    missing = sorted(set(cp_dates) - existing_dates)
    print(f"缺失预测日期: {len(missing)} 天")
    if missing:
        print(f"  范围: {missing[0]} ~ {missing[-1]}")
        # 补充最近的 30 天
        recent_missing = missing[-30:]
        print(f"  补充最近 30 天: {recent_missing[0]} ~ {recent_missing[-1]}")

        duckdb = get_duckdb_store()
        total_gain = 0
        total_prob = 0

        for date in recent_missing:
            # 获取该日期有 K 线数据的股票
            result = duckdb.query(
                "SELECT DISTINCT code FROM daily_kline WHERE trade_date <= ? LIMIT 500",
                [date]
            )
            if result.success:
                codes = result.data['code'].tolist()
                print(f"  {date}: {len(codes)} 只股票...", end=" ", flush=True)
                saved_gain, saved_prob = fill_predictions_for_date(date, codes)
                print(f"gain={saved_gain}, prob={saved_prob}")
                total_gain += saved_gain
                total_prob += saved_prob
            else:
                print(f"  {date}: 获取股票失败")

        print(f"\\n完成! 共保存 gain={total_gain}, prob={total_prob}")


if __name__ == '__main__':
    main()