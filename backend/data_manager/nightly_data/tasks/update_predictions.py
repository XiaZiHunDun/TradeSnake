"""预测数据更新任务

为所有有足够K线数据的股票更新预测
使用 gain_predictor 和 probability_predictor
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.data_manager.nightly_data.state_manager import StateManager
from backend.data_manager.nightly_data.logger import get_logger, log_task_start, log_task_complete, log_task_error

TASK_ID = 'update_predictions'

def get_codes_with_enough_data(min_days: int = 60):
    """获取有足够K线数据的股票"""
    from backend.data_manager.duckdb_store import get_duckdb_store
    store = get_duckdb_store()

    try:
        result = store.query("""
            SELECT code, COUNT(*) as cnt
            FROM daily_kline
            GROUP BY code
            HAVING cnt >= ?
        """, [min_days])

        if result.success:
            return [row[0] for row in result.data.itertuples()]
        return []
    except Exception as e:
        logger = get_logger(TASK_ID)
        logger.error(f"Failed to get codes with enough data: {e}")
        return []

def update_predictions():
    """执行预测更新任务"""
    logger = get_logger(TASK_ID)
    state_mgr = StateManager()

    if state_mgr.is_task_done_today(TASK_ID):
        logger.info(f"Task {TASK_ID} already completed today, skip")
        return

    logger.info("Starting prediction update")

    try:
        codes = get_codes_with_enough_data(min_days=60)
        logger.info(f"Found {len(codes)} stocks with enough data")

        from backend.engine.gain_predictor.predictor import GainPredictor
        from backend.engine.probability_predictor.predictor import ProbabilityPredictor
        from backend.data_manager.duckdb_store import get_duckdb_store

        gain_pred = GainPredictor()
        prob_pred = ProbabilityPredictor()
        duckdb_store = get_duckdb_store()

        updated = 0
        for code in codes:
            try:
                # 获取K线数据
                klines_result = duckdb_store.query("""
                    SELECT trade_date, open, high, low, close, volume, amount
                    FROM daily_kline
                    WHERE code = ?
                    ORDER BY trade_date
                """, [code])

                if not klines_result.success or len(klines_result.data) < 60:
                    continue

                klines_dict = {code: klines_result.data.to_dict('records')}
                # 确保按日期升序排列
                klines_dict = {code: sorted(klines, key=lambda x: x.get('trade_date', '')) for code, klines in klines_dict.items()}
                gain_result = gain_pred.predict(klines_dict)
                prob_result = prob_pred.predict(klines_dict)

                # 保存到 prediction_store
                if gain_result and gain_result.predictions:
                    gain_pred.save_to_store(gain_result)
                if prob_result and prob_result.predictions:
                    prob_pred.save_to_store(prob_result)

                updated += 1

                if updated % 100 == 0:
                    logger.info(f"Updated predictions for {updated}/{len(codes)}")

            except Exception as e:
                logger.debug(f"Failed to update predictions for {code}: {e}")

        state_mgr.mark_task_done(TASK_ID)
        log_task_complete(TASK_ID, f"Updated {updated} stocks")

    except Exception as e:
        log_task_error(TASK_ID, str(e))
        state_mgr.mark_task_failed(TASK_ID, str(e))

if __name__ == '__main__':
    update_predictions()