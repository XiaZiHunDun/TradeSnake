"""多源数据校验任务

从多个数据源获取同一数据，检测不一致并记录
校验：价格数据、复权因子、财务数据
"""
import sys
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.data_manager.nightly_data.state_manager import StateManager
from backend.data_manager.nightly_data.logger import get_logger, log_task_start, log_task_complete, log_task_error

TASK_ID = 'validate_data'

# 验证阈值
PRICE_DIFF_THRESHOLD = 0.01  # 1%
ADJ_FACTOR_DIFF_THRESHOLD = 0.001  # 0.1%
FINANCIAL_DIFF_THRESHOLD = 0.05  # 5%

def get_stock_list(limit: int = 100):
    """获取待验证的股票列表"""
    from backend.data_manager.manager import get_data_manager
    dm = get_data_manager()
    return dm.get_stock_list()[:limit]

def validate_price(code: str, date_str: str, state_mgr: StateManager, logger) -> bool:
    """验证价格数据 - Tushare vs AkShare"""
    try:
        import tushare as ts
        pro = ts.pro()

        # Tushare 数据
        df_ts = pro.daily(
            ts_code=f"{code}.SZ" if code.startswith(('000', '002', '300')) else f"{code}.SH",
            start_date=date_str,
            end_date=date_str
        )

        if df_ts is None or len(df_ts) == 0:
            return False

        ts_close = df_ts.iloc[0]['close']

        # AkShare 数据
        import akshare as ak
        try:
            df_ak = ak.stock_zh_a_hist(symbol=code[-6:], period="daily",
                                        start_date=date_str.replace('-', ''),
                                        end_date=date_str.replace('-', ''))
            if df_ak is not None and len(df_ak) > 0:
                ak_close = df_ak.iloc[0]['收盘']
                diff = abs(ts_close - ak_close) / ts_close if ts_close else 0
                if diff > PRICE_DIFF_THRESHOLD:
                    state_mgr.log_validation('price', code, 'tushare', 'akshare', diff * 100)
                    logger.warning(f"Price diff for {code} on {date_str}: {diff*100:.2f}%")
        except Exception as e:
            logger.debug(f"AkShare validation error for {code}: {e}")

        return True
    except Exception as e:
        logger.debug(f"Price validation error for {code}: {e}")
        return False

def validate_adj_factor(code: str, state_mgr: StateManager, logger) -> bool:
    """验证复权因子"""
    try:
        import tushare as ts
        pro = ts.pro()

        # 从 Tushare 获取复权因子
        df = pro.adj_factor(ts_code=f"{code}.SZ" if code.startswith(('000', '002', '300')) else f"{code}.SH",
                            start_date='20230101', end_date=datetime.now().strftime('%Y%m%d'))

        if df is None or len(df) == 0:
            return False

        # 从 DuckDB 获取复权因子
        from backend.data_manager.duckdb_store import get_duckdb_store
        store = get_duckdb_store()
        result = store.query(
            "SELECT trade_date, adj_factor FROM daily_kline WHERE code = ? ORDER BY trade_date DESC LIMIT 10",
            [code]
        )

        if not result.success or len(result.data) == 0:
            return False

        # 对比最新复权因子
        ts_factor = df.iloc[0]['adj_factor']
        db_factor = result.data.iloc[0]['adj_factor']
        diff = abs(ts_factor - db_factor) / ts_factor if ts_factor else 0

        if diff > ADJ_FACTOR_DIFF_THRESHOLD:
            state_mgr.log_validation('adj_factor', code, 'tushare', 'duckdb', diff * 100)
            logger.warning(f"Adj factor diff for {code}: {diff*100:.3f}%")

        return True
    except Exception as e:
        logger.debug(f"Adj factor validation error for {code}: {e}")
        return False

def validate_financial(code: str, state_mgr: StateManager, logger) -> bool:
    """验证财务数据 - 东方财富 vs Tushare"""
    try:
        from backend.data_manager.fetcher import get_financial_data

        # 获取东方财富数据
        try:
            from backend.data_manager.fetcher import FinancialDataFetcher
            fetcher = FinancialDataFetcher()
            df_em = fetcher.get_income_data(code)
            em_revenue = df_em.iloc[0]['revenue'] if df_em is not None and len(df_em) > 0 else None
        except:
            em_revenue = None

        # 获取 Tushare 数据
        import tushare as ts
        pro = ts.pro()
        df_ts = pro.income(ts_code=f"{code}.SZ" if code.startswith(('000', '002', '300')) else f"{code}.SH")

        if df_ts is None or len(df_ts) == 0:
            return False

        ts_revenue = df_ts.iloc[0]['revenue']

        if em_revenue and ts_revenue:
            diff = abs(em_revenue - ts_revenue) / ts_revenue if ts_revenue else 0
            if diff > FINANCIAL_DIFF_THRESHOLD:
                state_mgr.log_validation('financial', code, 'eastmoney', 'tushare', diff * 100)
                logger.warning(f"Financial diff for {code}: {diff*100:.2f}%")

        return True
    except Exception as e:
        logger.debug(f"Financial validation error for {code}: {e}")
        return False

def validate_data():
    """执行数据校验任务"""
    logger = get_logger(TASK_ID)
    state_mgr = StateManager()

    if state_mgr.is_task_done_today(TASK_ID):
        logger.info(f"Task {TASK_ID} already completed today, skip")
        return

    log_task_start(TASK_ID)

    try:
        stocks = get_stock_list(limit=100)
        validated_count = 0
        date_str = date.today().isoformat()

        for code_info in stocks:
            code = code_info.get('code', '') if isinstance(code_info, dict) else str(code_info)
            if not code:
                continue

            try:
                # 价格验证
                validate_price(code, date_str, state_mgr, logger)
                # 复权因子验证
                validate_adj_factor(code, state_mgr, logger)
                # 财务数据验证
                validate_financial(code, state_mgr, logger)

                validated_count += 1

                if validated_count % 20 == 0:
                    logger.info(f"Validated {validated_count}/{len(stocks)}")

            except Exception as e:
                logger.warning(f"Validation failed for {code}: {e}")

        state_mgr.mark_task_done(TASK_ID)
        log_task_complete(TASK_ID, f"Validated {validated_count} stocks")

    except Exception as e:
        log_task_error(TASK_ID, str(e))
        state_mgr.mark_task_failed(TASK_ID, str(e))

if __name__ == '__main__':
    validate_data()
