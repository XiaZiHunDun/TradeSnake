"""基准数据获取和对比

提供沪深 300、等权组合等基准的日收益率。
"""

import logging
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class BenchmarkProvider:
    """提供基准收益数据"""

    INDEX_CODES = {
        "hs300": "000300",
        "zz500": "000905",
    }

    def __init__(self):
        from backend.data_manager.duckdb_store import get_duckdb_store
        self.duckdb = get_duckdb_store()

    def get_benchmark_returns(
        self, name: str, start_date: str, end_date: str
    ) -> Dict[str, float]:
        """获取基准日收益率 {date: daily_return}"""
        if name == "equal_weight":
            return self.get_equal_weight_returns(start_date, end_date)

        code = self.INDEX_CODES.get(name)
        if not code:
            logger.warning("Unknown benchmark: %s", name)
            return {}

        return self._get_index_returns(code, start_date, end_date)

    def get_equal_weight_returns(
        self, start_date: str, end_date: str
    ) -> Dict[str, float]:
        """等权组合日收益率 — 每日等权持有 CP 池中所有股票"""
        try:
            from backend.data_manager.cp_history_store import get_cp_history_store
            cp_store = get_cp_history_store()
        except Exception:
            return {}

        try:
            dates = self._get_trading_dates(start_date, end_date)
            if len(dates) < 2:
                return {}

            returns: Dict[str, float] = {}
            prev_prices: Dict[str, float] = {}

            for dt in dates:
                snapshot = cp_store.get_snapshot(dt) if hasattr(cp_store, "get_snapshot") else []
                if not snapshot:
                    continue

                codes = [r.get("code") for r in snapshot if r.get("code")]
                if not codes:
                    continue

                klines = self.duckdb.get_klines_bulk_for_date(codes, end_date=dt, days=5)
                current_prices = {}
                for code in codes:
                    kdf = klines.get(code)
                    if kdf is not None and not kdf.empty and "close" in kdf.columns:
                        row = kdf[kdf["trade_date"] <= dt].tail(1)
                        if not row.empty:
                            current_prices[code] = float(row["close"].iloc[-1])

                if prev_prices and current_prices:
                    overlap = set(prev_prices) & set(current_prices)
                    if overlap:
                        day_rets = [
                            (current_prices[c] / prev_prices[c] - 1)
                            for c in overlap if prev_prices[c] > 0
                        ]
                        if day_rets:
                            returns[dt] = float(np.mean(day_rets))

                prev_prices = current_prices

            return returns
        except Exception as e:
            logger.warning("Equal weight benchmark failed: %s", e)
            return {}

    def _get_index_returns(
        self, code: str, start_date: str, end_date: str
    ) -> Dict[str, float]:
        try:
            result = self.duckdb.get_klines(
                code, start_date=start_date, end_date=end_date, limit=500
            )
            rows = result.rows if result and hasattr(result, "rows") else []
            if len(rows) < 2:
                return {}

            returns = {}
            for i in range(1, len(rows)):
                prev_close = rows[i - 1].get("close", 0)
                curr_close = rows[i].get("close", 0)
                dt = rows[i].get("trade_date", "")
                if prev_close > 0 and dt:
                    returns[dt] = (curr_close / prev_close - 1)
            return returns
        except Exception as e:
            logger.warning("Index returns for %s failed: %s", code, e)
            return {}

    def _get_trading_dates(self, start: str, end: str) -> List[str]:
        try:
            conn = self.duckdb._get_read_conn()
            sql = """
                SELECT DISTINCT trade_date FROM daily_kline
                WHERE trade_date >= ? AND trade_date <= ?
                ORDER BY trade_date
            """
            df = conn.execute(sql, [start, end]).df()
            return df["trade_date"].tolist() if not df.empty else []
        except Exception:
            return []
