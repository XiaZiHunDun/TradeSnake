"""策略级 Walk-forward 回测

滚动窗口：用 train_window 的 CP 排名确定持仓，在 test_window 中模拟交易。
严格避免前瞻偏差。
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from backend.engine.cp_engine.constants import TRADE_COST

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 250
RISK_FREE_RATE = 0.03


@dataclass
class WalkForwardConfig:
    train_window: int = 120
    test_window: int = 20
    step_size: int = 20
    top_n: int = 6
    rebalance_freq: int = 10
    stop_loss: float = -0.07
    initial_capital: float = 1_000_000


@dataclass
class FoldMetrics:
    fold_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    total_return: float
    sharpe: float
    max_drawdown: float
    n_trades: int


@dataclass
class WalkForwardReport:
    config: WalkForwardConfig
    folds: List[FoldMetrics] = field(default_factory=list)
    combined_daily_returns: List[float] = field(default_factory=list)
    combined_dates: List[str] = field(default_factory=list)

    # aggregate
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    max_drawdown: float = 0.0
    calmar: float = 0.0
    total_trades: int = 0
    turnover_rate: float = 0.0
    total_fees: float = 0.0
    fee_ratio: float = 0.0

    def summary(self) -> str:
        lines = [
            "=" * 70,
            "Walk-Forward Backtest Report",
            "=" * 70,
            f"  Folds           : {len(self.folds)}",
            f"  Total Return    : {self.total_return:.2f}%",
            f"  Annual Return   : {self.annual_return:.2f}%",
            f"  Sharpe          : {self.sharpe:.2f}",
            f"  Sortino         : {self.sortino:.2f}",
            f"  Max Drawdown    : {self.max_drawdown:.2f}%",
            f"  Calmar          : {self.calmar:.2f}",
            f"  Total Trades    : {self.total_trades}",
            f"  Turnover Rate   : {self.turnover_rate:.1f}x / year",
            f"  Total Fees      : {self.total_fees:,.0f}",
            f"  Fee Ratio       : {self.fee_ratio:.2f}%",
        ]
        return "\n".join(lines)


class WalkForwardBacktester:
    """策略级 walk-forward 回测器"""

    def __init__(self, config: WalkForwardConfig = None):
        self.config = config or WalkForwardConfig()

    def run(self, start_date: str, end_date: str) -> WalkForwardReport:
        from backend.data_manager.cp_history_store import get_cp_history_store
        from backend.data_manager.duckdb_store import get_duckdb_store

        cp_store = get_cp_history_store()
        duckdb = get_duckdb_store()

        dates = self._get_trading_dates(duckdb, start_date, end_date)
        if len(dates) < self.config.train_window + self.config.test_window:
            return WalkForwardReport(config=self.config)

        windows = self._generate_windows(dates)
        report = WalkForwardReport(config=self.config)

        all_daily_returns = []
        all_dates = []
        total_traded_value = 0.0
        total_fees = 0.0
        total_trades = 0

        for fold_id, (train_dates, test_dates) in enumerate(windows, 1):
            fold = self._run_fold(
                fold_id, train_dates, test_dates, cp_store, duckdb
            )
            if fold is None:
                continue
            report.folds.append(fold["metrics"])
            all_daily_returns.extend(fold["daily_returns"])
            all_dates.extend(fold["dates"])
            total_traded_value += fold["traded_value"]
            total_fees += fold["fees"]
            total_trades += fold["metrics"].n_trades

        if not all_daily_returns:
            return report

        report.combined_daily_returns = all_daily_returns
        report.combined_dates = all_dates
        report.total_trades = total_trades
        report.total_fees = total_fees

        arr = np.array(all_daily_returns)
        cum = np.cumprod(1 + arr)
        report.total_return = (cum[-1] - 1) * 100
        n_days = len(arr)
        report.annual_return = ((cum[-1]) ** (TRADING_DAYS_PER_YEAR / n_days) - 1) * 100 if n_days > 0 else 0

        vol = np.std(arr) * np.sqrt(TRADING_DAYS_PER_YEAR) if len(arr) > 1 else 0
        report.sharpe = (report.annual_return / 100 - RISK_FREE_RATE) / vol if vol > 0 else 0

        downside = arr[arr < 0]
        down_vol = np.std(downside) * np.sqrt(TRADING_DAYS_PER_YEAR) if len(downside) > 1 else 0
        report.sortino = (report.annual_return / 100 - RISK_FREE_RATE) / down_vol if down_vol > 0 else 0

        report.max_drawdown = self._max_drawdown(cum) * 100
        report.calmar = report.annual_return / abs(report.max_drawdown) if report.max_drawdown != 0 else 0

        if total_traded_value > 0:
            report.fee_ratio = total_fees / total_traded_value * 100
        capital = self.config.initial_capital
        years = n_days / TRADING_DAYS_PER_YEAR
        report.turnover_rate = total_traded_value / capital / years / 2 if years > 0 else 0

        return report

    def _generate_windows(self, dates):
        windows = []
        i = 0
        tw, tt, step = self.config.train_window, self.config.test_window, self.config.step_size
        while i + tw + tt <= len(dates):
            train = dates[i: i + tw]
            test = dates[i + tw: i + tw + tt]
            windows.append((train, test))
            i += step
        return windows

    def _run_fold(self, fold_id, train_dates, test_dates, cp_store, duckdb):
        ranking_date = train_dates[-1]
        snapshot = cp_store.get_snapshot(ranking_date) if hasattr(cp_store, "get_snapshot") else []
        if not snapshot:
            return None

        sorted_stocks = sorted(snapshot, key=lambda x: x.get("total_cp", 0), reverse=True)
        top_codes = [s["code"] for s in sorted_stocks[:self.config.top_n] if "code" in s]
        if not top_codes:
            return None

        klines = duckdb.get_klines_bulk_for_date(top_codes, end_date=test_dates[-1], days=len(test_dates) + 5)

        daily_returns = []
        dates_out = []
        traded_value = 0.0
        fees = 0.0
        n_trades = 0
        portfolio_value = self.config.initial_capital
        peak_portfolio_value = portfolio_value
        holdings = {code: portfolio_value / len(top_codes) for code in top_codes}
        peak_prices = {}  # code -> peak_price for trailing stop
        n_trades += len(top_codes)
        buy_cost_rate = TRADE_COST["commission"] + TRADE_COST["transfer_fee"]
        sell_cost_rate = TRADE_COST["commission"] + TRADE_COST["stamp_tax"] + TRADE_COST["transfer_fee"]
        for code, val in holdings.items():
            cost = val * buy_cost_rate
            fees += max(cost, TRADE_COST["min_commission"])
            traded_value += val
            # Initialize peak price at entry (use first available close)
            kdf = klines.get(code)
            if kdf is not None and not kdf.empty:
                first_close = float(kdf["close"].iloc[0])
                peak_prices[code] = first_close

        rebal_counter = 0
        portfolio_stopped = False
        TRAILING_STOP = 0.07  # -7% trailing stop
        PORTFOLIO_DRAWDOWN_LIMIT = 0.15  # -15% portfolio drawdown circuit breaker

        for dt in test_dates:
            day_returns_list = []

            # Process each holding
            for code in list(holdings.keys()):
                kdf = klines.get(code)
                if kdf is None or kdf.empty:
                    continue
                today_rows = kdf[kdf["trade_date"] == dt]
                yesterday_rows = kdf[kdf["trade_date"] < dt].tail(1)
                if today_rows.empty or yesterday_rows.empty:
                    continue
                c0 = float(yesterday_rows["close"].iloc[-1])
                c1 = float(today_rows["close"].iloc[-1])
                if c0 <= 0:
                    continue

                # Update peak price for trailing stop
                if code not in peak_prices:
                    peak_prices[code] = c0
                peak_prices[code] = max(peak_prices[code], c1)

                ret = c1 / c0 - 1

                # Check trailing stop (-10%)
                trailing_dd = (peak_prices[code] - c1) / peak_prices[code] if peak_prices[code] > 0 else 0
                if trailing_dd > TRAILING_STOP:
                    # Sell: hit trailing stop
                    sell_val = holdings[code]
                    cost = sell_val * sell_cost_rate
                    fees += max(cost, TRADE_COST["min_commission"])
                    traded_value += sell_val
                    n_trades += 1
                    holdings[code] = 0
                    day_returns_list.append(ret)
                elif ret <= self.config.stop_loss:
                    # Stop loss triggered
                    sell_val = holdings[code]
                    cost = sell_val * sell_cost_rate
                    fees += max(cost, TRADE_COST["min_commission"])
                    traded_value += sell_val
                    n_trades += 1
                    holdings[code] = 0
                    day_returns_list.append(self.config.stop_loss)
                else:
                    holdings[code] *= (1 + ret)
                    day_returns_list.append(ret)

            holdings = {c: v for c, v in holdings.items() if v > 0}

            if day_returns_list:
                avg_ret = float(np.mean(day_returns_list))
                portfolio_value *= (1 + avg_ret)
                peak_portfolio_value = max(peak_portfolio_value, portfolio_value)
                daily_returns.append(avg_ret)
                dates_out.append(dt)

                # Portfolio-level drawdown circuit breaker (-15%)
                if not portfolio_stopped:
                    drawdown = (peak_portfolio_value - portfolio_value) / peak_portfolio_value
                    if drawdown > PORTFOLIO_DRAWDOWN_LIMIT:
                        # Liquidate all positions
                        for code, val in list(holdings.items()):
                            cost = val * sell_cost_rate
                            fees += max(cost, TRADE_COST["min_commission"])
                            traded_value += val
                            n_trades += 1
                        holdings = {}
                        portfolio_stopped = True

            elif portfolio_stopped:
                # Already stopped, stay in cash
                daily_returns.append(0.0)
                dates_out.append(dt)
            elif not day_returns_list and not holdings:
                # No holdings and not stopped
                daily_returns.append(0.0)
                dates_out.append(dt)

            rebal_counter += 1

            # Periodic rebalancing
            if rebal_counter >= self.config.rebalance_freq and not portfolio_stopped:
                rebal_counter = 0
                # Re-select top stocks from CP ranking
                curr_snapshot = cp_store.get_snapshot(ranking_date) if hasattr(cp_store, "get_snapshot") else snapshot
                sorted_curr = sorted(curr_snapshot, key=lambda x: x.get("total_cp", 0), reverse=True)
                new_top_codes = [s["code"] for s in sorted_curr[:self.config.top_n] if "code" in s]
                # Sell all current holdings
                for code, val in list(holdings.items()):
                    cost = val * sell_cost_rate
                    fees += max(cost, TRADE_COST["min_commission"])
                    traded_value += val
                    n_trades += 1
                # Re-allocate to new top codes
                n = len(new_top_codes)
                if n > 0:
                    holdings = {code: portfolio_value / n for code in new_top_codes}
                    for code, val in holdings.items():
                        cost = val * buy_cost_rate
                        fees += max(cost, TRADE_COST["min_commission"])
                        traded_value += val
                        n_trades += 1
                    peak_prices = {}  # Reset peak prices for new holdings
                    # Load peak prices for new holdings
                    new_klines = duckdb.get_klines_bulk_for_date(new_top_codes, end_date=dt, days=5)
                    for code in new_top_codes:
                        kdf = new_klines.get(code)
                        if kdf is not None and not kdf.empty:
                            peak_prices[code] = float(kdf["close"].iloc[-1])
                        else:
                            peak_prices[code] = 0.0

        metrics = FoldMetrics(
            fold_id=fold_id,
            train_start=train_dates[0],
            train_end=train_dates[-1],
            test_start=test_dates[0],
            test_end=test_dates[-1],
            total_return=float((np.prod([1 + r for r in daily_returns]) - 1) * 100) if daily_returns else 0,
            sharpe=self._fold_sharpe(daily_returns),
            max_drawdown=self._max_drawdown(np.cumprod([1 + r for r in daily_returns])) * 100 if daily_returns else 0,
            n_trades=n_trades,
        )

        return {
            "metrics": metrics,
            "daily_returns": daily_returns,
            "dates": dates_out,
            "traded_value": traded_value,
            "fees": fees,
        }

    @staticmethod
    def _fold_sharpe(daily_returns):
        if len(daily_returns) < 2:
            return 0.0
        arr = np.array(daily_returns)
        ann_ret = np.mean(arr) * TRADING_DAYS_PER_YEAR
        ann_vol = np.std(arr) * np.sqrt(TRADING_DAYS_PER_YEAR)
        return (ann_ret - RISK_FREE_RATE) / ann_vol if ann_vol > 0 else 0.0

    @staticmethod
    def _max_drawdown(cum_values):
        if len(cum_values) == 0:
            return 0.0
        peak = cum_values[0]
        max_dd = 0.0
        for v in cum_values:
            if v > peak:
                peak = v
            if peak > 0:
                dd = (peak - v) / peak
                max_dd = max(max_dd, dd)
        return max_dd

    @staticmethod
    def _get_trading_dates(duckdb, start, end):
        try:
            conn = duckdb._get_read_conn()
            sql = """
                SELECT DISTINCT trade_date FROM daily_kline
                WHERE trade_date >= ? AND trade_date <= ?
                ORDER BY trade_date
            """
            df = conn.execute(sql, [start, end]).df()
            return df["trade_date"].tolist() if not df.empty else []
        except Exception:
            return []
