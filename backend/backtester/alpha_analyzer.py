"""Alpha 因子验证分析器

用数据回答：哪些因子在 A 股有真实的预测能力？

因子 IC、分组回测、信号衰减分析
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np
from scipy import stats

from backend.data_manager.cp_history_store import get_cp_history_store
from backend.data_manager.duckdb_store import get_duckdb_store


@dataclass
class FactorICResult:
    """单因子 IC 分析结果"""
    factor_name: str
    mean_ic: float
    ic_std: float
    icir: float
    ic_positive_ratio: float
    ic_series: List[float]
    t_stat: float
    p_value: float


@dataclass
class DecayResult:
    """信号衰减分析结果"""
    factor_name: str
    horizons: List[int]
    ic_by_horizon: List[float]
    half_life_days: Optional[float]


@dataclass
class GroupResult:
    """分组回测结果"""
    factor_name: str
    group_count: int
    group_returns: List[float]
    long_short_spread: float
    monotonic: bool


class AlphaAnalyzer:
    """因子 Alpha 分析器"""

    FACTORS = ['total_cp', 'growth_score', 'value_score',
               'quality_score', 'momentum_score']
    TECH_FACTORS = ['return_5d', 'return_10d', 'return_20d',
                    'volatility_20d', 'volume_ratio_5d', 'macd_diff']
    HORIZONS = [1, 3, 5, 10, 20]
    GROUP_COUNT = 5

    def __init__(self):
        self.cp_store = get_cp_history_store()
        self.duckdb = get_duckdb_store()
        # 缓存：避免重复加载 K 线数据
        self._price_map: Optional[Dict[tuple, float]] = None
        self._cp_snapshots: Optional[Dict[str, List[Dict]]] = None
        self._cp_dates: Optional[List[str]] = None
        self._ic_cache: Dict[tuple, FactorICResult] = {}

    def compute_factor_ic(self, factor_name: str, horizon: int = 5,
                          start_date: str = None, end_date: str = None) -> FactorICResult:
        """计算单因子时间序列 IC（带缓存）"""
        # 检查缓存
        cache_key = (factor_name, horizon, start_date or '', end_date or '')
        if cache_key in self._ic_cache:
            return self._ic_cache[cache_key]

        cp_dates = self._get_cp_dates(start_date, end_date)
        if len(cp_dates) < horizon + 5:
            result = self._empty_ic_result(factor_name)
            self._ic_cache[cache_key] = result
            return result

        # 预加载数据（只做一次）
        self._ensure_data_loaded(cp_dates, horizon, start_date, end_date)

        # 计算 IC
        ic_series = []
        n_dates = len(cp_dates)
        end_idx = n_dates - horizon

        for i in range(end_idx):
            signal_date = cp_dates[i]
            return_end_idx = min(i + horizon, n_dates - 1)
            return_end_date = cp_dates[return_end_idx]

            cp_data = self._cp_snapshots.get(signal_date, [])
            if not cp_data or len(cp_data) < 10:
                continue

            factor_vals = []
            return_vals = []
            for item in cp_data:
                code = item.get('code', '')
                start_p = self._price_map.get((code, signal_date))
                end_p = self._price_map.get((code, return_end_date))
                if start_p and end_p and start_p > 0:
                    factor_val = item.get(factor_name, 0)
                    if factor_val is not None:
                        factor_vals.append(factor_val)
                        return_vals.append((end_p - start_p) / start_p)

            if len(factor_vals) < 10:
                continue

            try:
                ic, _ = stats.spearmanr(factor_vals, return_vals)
                if not np.isnan(ic):
                    ic_series.append(ic)
            except Exception:
                continue

        if not ic_series:
            result = self._empty_ic_result(factor_name)
            self._ic_cache[cache_key] = result
            return result

        ic_array = np.array(ic_series)
        mean_ic = float(np.mean(ic_array))
        ic_std = float(np.std(ic_array))
        icir = mean_ic / ic_std if ic_std > 0 else 0.0
        ic_positive_ratio = float(np.mean(ic_array > 0))
        n = len(ic_series)
        t_stat = float(mean_ic / (ic_std / np.sqrt(n))) if ic_std > 0 else 0.0
        p_value = float(2 * (1 - stats.t.cdf(abs(t_stat), n - 1))) if n > 1 else 1.0

        result = FactorICResult(
            factor_name=factor_name,
            mean_ic=mean_ic,
            ic_std=ic_std,
            icir=icir,
            ic_positive_ratio=ic_positive_ratio,
            ic_series=ic_series,
            t_stat=t_stat,
            p_value=p_value
        )
        self._ic_cache[cache_key] = result
        return result

    def compute_decay(self, factor_name: str, start_date: str = None,
                      end_date: str = None) -> DecayResult:
        """计算信号衰减曲线（从缓存读取，不重复加载数据）"""
        ic_by_horizon = []
        for h in self.HORIZONS:
            result = self.compute_factor_ic(factor_name, horizon=h,
                                            start_date=start_date, end_date=end_date)
            ic_by_horizon.append(result.mean_ic)

        half_life = self._compute_half_life(self.HORIZONS, ic_by_horizon)

        return DecayResult(
            factor_name=factor_name,
            horizons=self.HORIZONS,
            ic_by_horizon=ic_by_horizon,
            half_life_days=half_life
        )

    def compute_tech_factor_ic(self, factor_name: str, horizon: int = 5,
                                start_date: str = None, end_date: str = None) -> FactorICResult:
        """计算技术因子的 IC（从 DuckDB 加载 + Python 计算，更稳定）"""
        cache_key = (f"tech_{factor_name}", horizon, start_date or '', end_date or '')
        if cache_key in self._ic_cache:
            return self._ic_cache[cache_key]

        cp_dates = self._get_cp_dates(start_date, end_date)
        if len(cp_dates) < horizon + 25:
            result = self._empty_ic_result(factor_name)
            self._ic_cache[cache_key] = result
            return result

        start = start_date or cp_dates[0]
        end = end_date or cp_dates[-1]
        # 加载所有 K 线（一次查询，约 0.5s）
        try:
            conn = self.duckdb._get_read_conn()
            df = conn.execute("""
                SELECT code, trade_date::TEXT as td, close, volume
                FROM daily_kline
                WHERE trade_date >= ? AND trade_date <= ?
                ORDER BY code, trade_date
            """, [start, end]).df()

            if df is None or df.empty:
                result = self._empty_ic_result(factor_name)
                self._ic_cache[cache_key] = result
                return result

            # 转换日期
            df['td'] = pd.to_datetime(df['td']).dt.strftime('%Y-%m-%d')
        except Exception as e:
            print(f"compute_tech_factor_ic query error: {e}")
            result = self._empty_ic_result(factor_name)
            self._ic_cache[cache_key] = result
            return result

        # 按股票分组计算因子和未来收益
        ic_by_date: Dict[str, List[float]] = {}
        ic_by_date_ret: Dict[str, List[float]] = {}
        grouped = df.groupby('code')

        for code, stock_df in grouped:
            stock_df = stock_df.sort_values('td').reset_index(drop=True)
            closes = stock_df['close'].values
            volumes = stock_df['volume'].values
            dates = stock_df['td'].values
            n = len(closes)

            for i in range(horizon, n):
                sig_date = dates[i]
                ret_date_idx = min(i + horizon, n - 1)
                ret_date = dates[ret_date_idx]

                if sig_date not in cp_dates or ret_date not in cp_dates:
                    continue

                sig_close = closes[i]
                ret_close = closes[ret_date_idx]
                if sig_close <= 0:
                    continue

                future_ret = (ret_close - sig_close) / sig_close

                tech_val = self._calc_tech_factor(closes, volumes, i, factor_name)
                if tech_val is None:
                    continue

                if sig_date not in ic_by_date:
                    ic_by_date[sig_date] = []
                    ic_by_date_ret[sig_date] = []
                ic_by_date[sig_date].append(tech_val)
                ic_by_date_ret[sig_date].append(future_ret)

        # 按日期计算 IC
        ic_series = []
        for sig_date in sorted(ic_by_date.keys()):
            tvals = ic_by_date[sig_date]
            rvals = ic_by_date_ret[sig_date]
            if len(tvals) >= 10:
                try:
                    ic, _ = stats.spearmanr(tvals, rvals)
                    if not np.isnan(ic):
                        ic_series.append(ic)
                except Exception:
                    continue

        if not ic_series or len(ic_series) < 5:
            result = self._empty_ic_result(factor_name)
            self._ic_cache[cache_key] = result
            return result

        ic_array = np.array(ic_series)
        mean_ic = float(np.mean(ic_array))
        ic_std = float(np.std(ic_array))
        icir = mean_ic / ic_std if ic_std > 0 else 0.0
        ic_positive_ratio = float(np.mean(ic_array > 0))
        n = len(ic_series)
        t_stat = float(mean_ic / (ic_std / np.sqrt(n))) if ic_std > 0 else 0.0
        p_value = float(2 * (1 - stats.t.cdf(abs(t_stat), n - 1))) if n > 1 else 1.0

        result = FactorICResult(
            factor_name=factor_name,
            mean_ic=mean_ic,
            ic_std=ic_std,
            icir=icir,
            ic_positive_ratio=ic_positive_ratio,
            ic_series=ic_series,
            t_stat=t_stat,
            p_value=p_value
        )
        self._ic_cache[cache_key] = result
        return result

    def _calc_tech_factor(self, closes, volumes, idx: int, factor_name: str) -> Optional[float]:
        """从 K 线数组计算指定索引位置的技术因子值"""
        n = idx + 1  # current position
        try:
            if factor_name == 'return_5d':
                if n < 6:
                    return None
                prev = closes[idx - 5]
                return float((closes[idx] - prev) / prev) if prev > 0 else None
            elif factor_name == 'return_10d':
                if n < 11:
                    return None
                prev = closes[idx - 10]
                return float((closes[idx] - prev) / prev) if prev > 0 else None
            elif factor_name == 'return_20d':
                if n < 21:
                    return None
                prev = closes[idx - 20]
                return float((closes[idx] - prev) / prev) if prev > 0 else None
            elif factor_name == 'volatility_20d':
                if n < 21:
                    return None
                window = closes[idx - 20:idx + 1]
                prevs = closes[idx - 20:idx]
                rets = np.diff(window) / prevs
                return float(np.std(rets)) if len(rets) > 0 else None
            elif factor_name == 'volume_ratio_5d':
                if n < 6:
                    return None
                avg_vol = float(np.mean(volumes[idx - 5:idx]))
                today_vol = float(volumes[idx])
                return float(today_vol / avg_vol) if avg_vol > 0 else None
            elif factor_name == 'macd_diff':
                if n < 26:
                    return None
                ema12 = self._ema(closes[idx - 12 + 1:idx + 1], 12)
                ema26 = self._ema(closes[idx - 26 + 1:idx + 1], 26)
                if ema12 is None or ema26 is None:
                    return None
                macd = ema12 - ema26
                signal = self._ema([macd] * 9, 9)
                return float(macd - signal) if signal is not None else None
            return None
        except Exception:
            return None

    def _ema(self, values, span: int) -> Optional[float]:
        """计算 EMA"""
        try:
            if len(values) < span:
                return None
            arr = np.array(values, dtype=float)
            alpha = 2.0 / (span + 1)
            ema = arr[0]
            for v in arr[1:]:
                ema = alpha * v + (1 - alpha) * ema
            return float(ema)
        except Exception:
            return None


    def compute_group_returns(self, factor_name: str, horizon: int = 5,
                              start_date: str = None, end_date: str = None) -> GroupResult:
        """分组回测"""
        cp_dates = self._get_cp_dates(start_date, end_date)
        if not cp_dates:
            return GroupResult(factor_name, self.GROUP_COUNT, [0.0]*5, 0.0, False)

        if len(cp_dates) < horizon + 5:
            return GroupResult(factor_name, self.GROUP_COUNT, [0.0]*5, 0.0, False)

        # 预加载
        self._ensure_data_loaded(cp_dates, horizon, start_date, end_date)

        end_idx = len(cp_dates) - horizon
        all_group_returns: List[List[float]] = [[] for _ in range(self.GROUP_COUNT)]

        for i in range(end_idx):
            signal_date = cp_dates[i]
            return_end_idx = min(i + horizon, len(cp_dates) - 1)
            return_end_date = cp_dates[return_end_idx]

            cp_data = self._cp_snapshots.get(signal_date, [])
            if not cp_data or len(cp_data) < self.GROUP_COUNT:
                continue

            stock_returns = []
            for item in cp_data:
                code = item.get('code', '')
                start_p = self._price_map.get((code, signal_date))
                end_p = self._price_map.get((code, return_end_date))
                if start_p and end_p and start_p > 0:
                    stock_returns.append((item, (end_p - start_p) / start_p))

            if len(stock_returns) < self.GROUP_COUNT:
                continue

            stock_returns.sort(key=lambda x: x[0].get(factor_name, 0) or 0)
            n = len(stock_returns)
            group_size = n // self.GROUP_COUNT

            for g in range(self.GROUP_COUNT):
                start_g = g * group_size
                end_g = start_g + group_size if g < self.GROUP_COUNT - 1 else n
                group_rets = [r for _, r in stock_returns[start_g:end_g]]
                if group_rets:
                    all_group_returns[g].append(np.mean(group_rets))

        group_avg_returns = []
        for g_returns in all_group_returns:
            group_avg_returns.append(float(np.mean(g_returns)) * 100 if g_returns else 0.0)

        long_short = group_avg_returns[-1] - group_avg_returns[0] if len(group_avg_returns) >= 2 else 0.0
        monotonic = all(group_avg_returns[i] <= group_avg_returns[i + 1]
                       for i in range(len(group_avg_returns) - 1))

        return GroupResult(
            factor_name=factor_name,
            group_count=self.GROUP_COUNT,
            group_returns=group_avg_returns,
            long_short_spread=long_short,
            monotonic=monotonic
        )

    def full_report(self, start_date: str = None, end_date: str = None) -> Dict:
        """生成完整报告"""
        horizon = 5
        ic_results = {}
        decay_results = {}
        group_results = {}

        for factor in self.FACTORS:
            ic_results[factor] = self.compute_factor_ic(factor, horizon=horizon,
                                                        start_date=start_date, end_date=end_date)
            decay_results[factor] = self.compute_decay(factor,
                                                       start_date=start_date, end_date=end_date)
            group_results[factor] = self.compute_group_returns(factor, horizon=horizon,
                                                               start_date=start_date, end_date=end_date)

        return {
            'ic': ic_results,
            'decay': decay_results,
            'groups': group_results,
            'horizon': horizon,
            'start_date': start_date,
            'end_date': end_date
        }

    # ---- 内部方法 ----

    def _get_cp_dates(self, start_date: str = None, end_date: str = None) -> List[str]:
        """获取交易日列表"""
        cp_dates = self.cp_store.get_available_dates()
        if not cp_dates:
            return []
        if start_date:
            cp_dates = [d for d in cp_dates if d >= start_date]
        if end_date:
            cp_dates = [d for d in cp_dates if d <= end_date]
        return cp_dates

    def _ensure_data_loaded(self, cp_dates: List[str], horizon: int,
                            start_date: str = None, end_date: str = None):
        """确保价格数据和CP快照已加载（只加载一次）"""
        cache_key = (start_date or '', end_date or '', horizon)
        if self._price_map is not None and self._cp_dates == cache_key:
            return

        self._cp_dates = cache_key
        self._price_map = {}
        self._cp_snapshots = {}

        n = len(cp_dates)
        load_end_idx = min(n - 1, n - 1)
        first_date = cp_dates[0]
        last_date = cp_dates[load_end_idx]

        # 加载 K 线数据
        self._price_map = self._load_kline_data(first_date, last_date)

        # 加载 CP 快照
        for d in cp_dates:
            self._cp_snapshots[d] = self.cp_store.get_cp_history_by_date(d)

    def _load_kline_data(self, start_date: str, end_date: str) -> Dict[tuple, float]:
        """一次性加载指定日期范围的 K 线收盘价"""
        try:
            result = self.duckdb.query(f"""
                SELECT code, trade_date::TEXT as td, close
                FROM daily_kline
                WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
                ORDER BY code, trade_date
            """)

            price_map: Dict[tuple, float] = {}
            if result.success and result.data is not None and not result.data.empty:
                for _, row in result.data.iterrows():
                    code = str(row['code'])
                    date_str = str(row['td'])[:10]
                    close = float(row['close'])
                    if close > 0:
                        price_map[(code, date_str)] = close

            return price_map
        except Exception as e:
            print(f"_load_kline_data error: {e}")
            return {}

    def _compute_half_life(self, horizons: List[int],
                            ic_values: List[float]) -> Optional[float]:
        """计算 IC 半衰期（线性插值）"""
        if not ic_values or len(ic_values) < 2:
            return None

        peak_ic = max(abs(v) for v in ic_values)
        if peak_ic <= 0:
            return None

        for i in range(len(ic_values)):
            if abs(ic_values[i]) <= peak_ic / 2:
                if i == 0:
                    return float(horizons[0])
                prev_ic = ic_values[i - 1]
                curr_ic = ic_values[i]
                prev_h = horizons[i - 1]
                curr_h = horizons[i]
                if curr_ic != prev_ic:
                    frac = (peak_ic / 2 - abs(prev_ic)) / (abs(curr_ic) - abs(prev_ic))
                    return float(prev_h + frac * (curr_h - prev_h))
                return float(curr_h)

        return None

    def _empty_ic_result(self, factor_name: str) -> FactorICResult:
        """返回空结果"""
        return FactorICResult(
            factor_name=factor_name,
            mean_ic=0.0, ic_std=0.0, icir=0.0,
            ic_positive_ratio=0.0, ic_series=[],
            t_stat=0.0, p_value=1.0
        )