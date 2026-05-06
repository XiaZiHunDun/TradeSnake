"""ML 特征工程

从 CP 因子 + K 线数据构建特征矩阵。
每行 = 一只股票在一天的截面特征。
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional


CP_FEATURES = [
    "total_cp", "growth_score", "value_score",
    "quality_score", "momentum_score", "risk_score",
]

TECHNICAL_FEATURES = [
    "rsi_14", "macd_diff", "macd_signal",
    "ma5_slope", "ma10_slope", "ma20_slope",
    "volume_ratio_5d", "volume_ratio_10d",
]

STAT_FEATURES = [
    "return_5d", "return_10d", "return_20d",
    "volatility_10d", "volatility_20d",
    "skew_20d",
]

ALL_FEATURES = CP_FEATURES + TECHNICAL_FEATURES + STAT_FEATURES


# ── helpers ──────────────────────────────────────────────

def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    alpha = 2.0 / (span + 1)
    out = np.empty_like(arr, dtype=float)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def compute_rsi(closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[-period:].mean()
    avg_loss = losses[-period:].mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def compute_macd(closes: np.ndarray):
    if len(closes) < 26:
        return 0.0, 0.0
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    diff = ema12 - ema26
    signal = _ema(diff, 9)
    return float(diff[-1]), float(signal[-1])


def compute_ma_slope(closes: np.ndarray, period: int) -> float:
    if len(closes) < period + 1:
        return 0.0
    ma_now = closes[-period:].mean()
    ma_prev = closes[-(period + 1):-1].mean()
    if ma_prev == 0:
        return 0.0
    return (ma_now / ma_prev - 1) * 100


def compute_volume_ratio(volumes: np.ndarray, short: int, long: int = 20) -> float:
    if len(volumes) < long:
        return 1.0
    short_avg = volumes[-short:].mean()
    long_avg = volumes[-long:].mean()
    if long_avg == 0:
        return 1.0
    return float(short_avg / long_avg)


# ── main builder ──────────────────────────────────────────

class FeatureBuilder:
    """为一组股票构建 ML 特征矩阵"""

    def __init__(self):
        from backend.data_manager.cp_history_store import get_cp_history_store
        from backend.data_manager.duckdb_store import get_duckdb_store
        self.cp_store = get_cp_history_store()
        self.duckdb = get_duckdb_store()

    def build_features_for_date(
        self, date: str, codes: List[str]
    ) -> pd.DataFrame:
        """构建某日截面特征矩阵 (rows=stocks, cols=features)"""
        klines_bulk = self.duckdb.get_klines_bulk_for_date(codes, end_date=date, days=70)

        rows = []
        for code in codes:
            kdf = klines_bulk.get(code)
            row = self._build_row(code, date, kdf)
            if row is not None:
                rows.append(row)

        if not rows:
            return pd.DataFrame(columns=["code", "date"] + ALL_FEATURES)
        return pd.DataFrame(rows)

    def build_target(
        self, date: str, codes: List[str], horizon: int = 5
    ) -> pd.Series:
        """构建 N 日后收益率目标变量"""
        from datetime import datetime, timedelta
        # 处理 DuckDB Timestamp 类型
        date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else date
        end = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=horizon * 2)).strftime("%Y-%m-%d")
        klines_bulk = self.duckdb.get_klines_bulk_for_date(codes, end_date=end, days=horizon * 2 + 5)

        targets = {}
        for code in codes:
            kdf = klines_bulk.get(code)
            if kdf is None or kdf.empty or "trade_date" not in kdf.columns:
                continue
            future = kdf[kdf["trade_date"] > date].head(horizon)
            current = kdf[kdf["trade_date"] <= date].tail(1)
            if current.empty or future.empty:
                continue
            c0 = float(current["close"].iloc[-1])
            cf = float(future["close"].iloc[-1])
            if c0 > 0:
                targets[code] = (cf / c0 - 1) * 100

        return pd.Series(targets, name=f"return_{horizon}d")

    def build_dataset(
        self, start_date: str, end_date: str, horizon: int = 5
    ) -> pd.DataFrame:
        """构建完整数据集（多日 × 多股票）"""
        dates = self._get_trading_dates(start_date, end_date)
        if not dates:
            return pd.DataFrame()

        frames = []
        for dt in dates:
            codes = self._get_codes_for_date(dt)
            if not codes:
                continue
            feat_df = self.build_features_for_date(dt, codes)
            if feat_df.empty:
                continue
            target = self.build_target(dt, codes, horizon)
            feat_df = feat_df.set_index("code")
            feat_df["target"] = target
            feat_df = feat_df.dropna(subset=["target"])
            if not feat_df.empty:
                frames.append(feat_df.reset_index())

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    # ── private ──────────────────────────────────────────

    def _build_row(self, code: str, date: str, kdf) -> Optional[Dict]:
        if kdf is None or kdf.empty or "close" not in kdf.columns:
            return None

        before = kdf[kdf["trade_date"] <= date] if "trade_date" in kdf.columns else kdf
        if len(before) < 26:
            return None

        closes = before["close"].values.astype(float)
        volumes = before["volume"].values.astype(float) if "volume" in before.columns else np.ones(len(closes))

        row: Dict = {"code": code, "date": date}

        cp_data = self._get_cp_for_date(code, date)
        for f in CP_FEATURES:
            row[f] = cp_data.get(f, 0.0)

        row["rsi_14"] = compute_rsi(closes, 14)
        row["macd_diff"], row["macd_signal"] = compute_macd(closes)
        row["ma5_slope"] = compute_ma_slope(closes, 5)
        row["ma10_slope"] = compute_ma_slope(closes, 10)
        row["ma20_slope"] = compute_ma_slope(closes, 20)
        row["volume_ratio_5d"] = compute_volume_ratio(volumes, 5)
        row["volume_ratio_10d"] = compute_volume_ratio(volumes, 10)

        for d in [5, 10, 20]:
            if len(closes) > d:
                row[f"return_{d}d"] = (closes[-1] / closes[-d - 1] - 1) * 100
            else:
                row[f"return_{d}d"] = 0.0

        if len(closes) >= 10:
            rets = np.diff(np.log(np.maximum(closes[-11:], 1e-8)))
            row["volatility_10d"] = float(np.std(rets) * np.sqrt(250) * 100)
        else:
            row["volatility_10d"] = 0.0

        if len(closes) >= 20:
            rets = np.diff(np.log(np.maximum(closes[-21:], 1e-8)))
            row["volatility_20d"] = float(np.std(rets) * np.sqrt(250) * 100)
        else:
            row["volatility_20d"] = 0.0

        if len(closes) >= 20:
            rets = np.diff(closes[-21:]) / np.maximum(closes[-21:-1], 1e-8)
            from scipy.stats import skew
            row["skew_20d"] = float(skew(rets))
        else:
            row["skew_20d"] = 0.0

        return row

    def _get_cp_for_date(self, code: str, date: str) -> Dict:
        try:
            records = self.cp_store.get_cp_history(code, days=30)
            for r in records:
                rd = r.get("recorded_at", r.get("date", ""))
                if rd <= date:
                    return r
        except Exception:
            pass
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

    def _get_codes_for_date(self, date: str) -> List[str]:
        try:
            records = self.cp_store.get_snapshot(date)
            if records:
                return [r["code"] for r in records if "code" in r]
        except Exception:
            pass
        # fallback: 从 daily_kline 取当日有交易的 codes，限制 500 只
        try:
            conn = self.duckdb._get_read_conn()
            df = conn.execute(
                "SELECT DISTINCT code FROM daily_kline WHERE trade_date = ? LIMIT 500",
                [date],
            ).df()
            if not df.empty:
                return df["code"].tolist()
        except Exception:
            pass
        return []
