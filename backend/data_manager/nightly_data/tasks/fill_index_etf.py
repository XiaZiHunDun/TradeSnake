"""指数和ETF数据获取任务

获取A股主要指数和ETF的日K线数据
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.data_manager.nightly_data.state_manager import StateManager
from backend.data_manager.nightly_data.logger import get_logger, log_task_start, log_task_complete, log_task_error

TASK_ID = 'fill_index_etf'

# A股主要指数
INDEX_CODES = {
    '000001': '上证指数',
    '399001': '深证成指',
    '399006': '创业板指',
    '000688': '科创50',
    '000016': '上证50',
    '000300': '沪深300',
    '000905': '中证500',
    '000852': '中证1000',
}

# 主要ETF
ETF_CODES = {
    '510050': '上证50ETF',
    '510300': '沪深300ETF',
    '510500': '中证500ETF',
    '512000': '券商ETF',
    '512880': '证券ETF',
    '515000': '科技ETF',
    '159915': '创业板ETF',
}


def fill_index_etf():
    """执行指数/ETF数据获取任务"""
    logger = get_logger(TASK_ID)
    state_mgr = StateManager()

    if state_mgr.is_task_done_today(TASK_ID):
        logger.info(f"Task {TASK_ID} already completed today, skip")
        return

    total = len(INDEX_CODES) + len(ETF_CODES)
    log_task_start(TASK_ID, total=total)

    try:
        import tushare as ts
        from backend.data_manager.duckdb_store import get_duckdb_store
        from backend.data_manager.duckdb_store import KlineRecord

        pro = ts.pro()
        store = get_duckdb_store()
        today_str = datetime.now().strftime('%Y%m%d')

        # 获取指数数据
        for code, name in INDEX_CODES.items():
            try:
                logger.debug(f"Fetching index {code} ({name})")
                suffix = '.SH' if code.startswith('000') else '.SZ'
                df = pro.index_daily(
                    ts_code=f"{code}{suffix}",
                    start_date='20100101',
                    end_date=today_str
                )
                if df is not None and len(df) > 0:
                    records = []
                    for _, row in df.iterrows():
                        records.append(KlineRecord(
                            code=code,
                            trade_date=row['trade_date'],
                            open=row['open'],
                            high=row['high'],
                            low=row['low'],
                            close=row['close'],
                            volume=row['vol'],
                            amount=row.get('amount', 0),
                        ))
                    if records:
                        store.insert_daily_klines_batch(records)
                        logger.debug(f"Index {code} saved {len(records)} records")
                state_mgr.update_task_state(TASK_ID, last_code=code, status='running')
            except Exception as e:
                logger.warning(f"Failed to fetch index {code}: {e}")

        # 获取ETF数据
        for code, name in ETF_CODES.items():
            try:
                logger.debug(f"Fetching ETF {code} ({name})")
                suffix = '.SH' if code.startswith('5') else '.SZ'
                df = pro.fund_daily(
                    ts_code=f"{code}{suffix}",
                    start_date='20100101',
                    end_date=today_str
                )
                if df is not None and len(df) > 0:
                    records = []
                    for _, row in df.iterrows():
                        records.append(KlineRecord(
                            code=code,
                            trade_date=row['trade_date'],
                            open=row['open'],
                            high=row['high'],
                            low=row['low'],
                            close=row['close'],
                            volume=row['vol'],
                            amount=row.get('amount', 0),
                        ))
                    if records:
                        store.insert_daily_klines_batch(records)
                        logger.debug(f"ETF {code} saved {len(records)} records")
                state_mgr.update_task_state(TASK_ID, last_code=code, status='running')
            except Exception as e:
                logger.warning(f"Failed to fetch ETF {code}: {e}")

        state_mgr.mark_task_done(TASK_ID)
        log_task_complete(TASK_ID, f"Index: {len(INDEX_CODES)}, ETF: {len(ETF_CODES)}")

    except Exception as e:
        log_task_error(TASK_ID, str(e))
        state_mgr.mark_task_failed(TASK_ID, str(e))


if __name__ == '__main__':
    fill_index_etf()
