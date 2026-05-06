"""多维动量因子 v20.0 单元测试"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from backend.engine.cp_engine.cp_engine import CPEngine, StockCP
from backend.engine.cp_engine.constants import MOMENTUM_WEIGHTS, MOMENTUM_PARAMS, WEIGHTS


# --------------- helpers ---------------

def _make_klines_df(closes, volumes=None, days=None):
    n = len(closes)
    if volumes is None:
        volumes = [1_000_000] * n
    dates = pd.date_range(end="2026-04-28", periods=n, freq="B").strftime("%Y-%m-%d").tolist()
    return pd.DataFrame({
        "code": ["000001"] * n,
        "trade_date": dates,
        "open": closes,
        "high": [c * 1.02 for c in closes],
        "low": [c * 0.98 for c in closes],
        "close": closes,
        "volume": volumes,
        "amount": [c * v for c, v in zip(closes, volumes)],
    })


def _make_stock(**overrides):
    defaults = dict(
        code="000001", name="Test", price=10.0,
        change_pct=1.0, pe=15.0, pb=2.0,
        revenue_growth=0.2, net_profit_growth=0.15,
        roe=0.12, gross_margin=0.35, debt_ratio=0.4,
        market_cap=5e9, volume=1e6,
        high=10.2, low=9.8, sector="科技",
    )
    defaults.update(overrides)
    stock = StockCP(
        code=defaults["code"], name=defaults["name"],
        price=defaults["price"], change_pct=defaults["change_pct"],
        pe=defaults["pe"], roe=defaults["roe"],
        net_profit_growth=defaults["net_profit_growth"],
        revenue_growth=defaults["revenue_growth"],
    )
    stock.pb = defaults["pb"]
    stock.gross_margin = defaults["gross_margin"]
    stock.debt_ratio = defaults["debt_ratio"]
    stock.market_cap = defaults["market_cap"]
    stock.volume = defaults["volume"]
    stock.high = defaults["high"]
    stock.low = defaults["low"]
    stock.sector = defaults["sector"]
    stock.calculate_scores()
    return stock


# --------------- constants ---------------

class TestMomentumConstants:
    def test_weights_sum_to_one(self):
        total = sum(MOMENTUM_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_main_weights_changed(self):
        assert WEIGHTS["momentum"] == 0.28
        assert WEIGHTS["quality"] == 0.05
        assert WEIGHTS["growth"] == 0.50

    def test_momentum_params_present(self):
        assert "reversal_days" in MOMENTUM_PARAMS
        assert "momentum_days" in MOMENTUM_PARAMS
        assert "volume_avg_days" in MOMENTUM_PARAMS


# --------------- short reversal ---------------

class TestShortReversal:
    def test_big_drop_gives_high_score(self):
        closes = [10.0, 9.5, 9.0, 8.5, 8.2, 8.0]
        df = _make_klines_df(closes)
        score = CPEngine._calc_short_reversal(df, days=5)
        assert score > 60

    def test_big_rise_gives_low_score(self):
        closes = [10.0, 10.5, 11.0, 11.5, 12.0, 12.5]
        df = _make_klines_df(closes)
        score = CPEngine._calc_short_reversal(df, days=5)
        assert score < 40

    def test_flat_gives_neutral(self):
        closes = [10.0] * 6
        df = _make_klines_df(closes)
        score = CPEngine._calc_short_reversal(df, days=5)
        assert 45 <= score <= 55

    def test_none_klines_returns_neutral(self):
        score = CPEngine._calc_short_reversal(None, days=5)
        assert score == 50.0

    def test_insufficient_data_returns_neutral(self):
        df = _make_klines_df([10.0, 10.1])
        score = CPEngine._calc_short_reversal(df, days=5)
        assert score == 50.0

    def test_score_bounded(self):
        closes = [10.0, 5.0, 3.0, 2.0, 1.5, 1.0]
        df = _make_klines_df(closes)
        score = CPEngine._calc_short_reversal(df, days=5)
        assert 0 <= score <= 100


# --------------- medium momentum ---------------

class TestMediumMomentum:
    def test_strong_uptrend(self):
        closes = list(np.linspace(10, 15, 30))
        df = _make_klines_df(closes)
        score = CPEngine._calc_medium_momentum(df, days=20, skip=5)
        assert score > 60

    def test_strong_downtrend(self):
        closes = list(np.linspace(15, 10, 30))
        df = _make_klines_df(closes)
        score = CPEngine._calc_medium_momentum(df, days=20, skip=5)
        assert score < 40

    def test_flat_gives_neutral(self):
        closes = [10.0] * 30
        df = _make_klines_df(closes)
        score = CPEngine._calc_medium_momentum(df, days=20, skip=5)
        assert 45 <= score <= 55

    def test_none_klines(self):
        assert CPEngine._calc_medium_momentum(None, 20, 5) == 50.0

    def test_skip_excludes_recent(self):
        base = [10.0] * 25
        spike = [10.0] * 20 + [15.0] * 5 + [15.0] * 5
        df_base = _make_klines_df(base + [10.0] * 5)
        df_spike = _make_klines_df(spike)
        score_base = CPEngine._calc_medium_momentum(df_base, days=20, skip=5)
        score_spike = CPEngine._calc_medium_momentum(df_spike, days=20, skip=5)
        assert score_spike > score_base


# --------------- volume confirmation ---------------

class TestVolumeConfirmation:
    def test_rally_with_volume(self):
        closes = list(np.linspace(10, 12, 25))
        vols = [1_000_000] * 15 + [2_000_000] * 10
        df = _make_klines_df(closes, vols)
        score = CPEngine._calc_volume_confirmation(df, lookback=10, avg_days=20)
        assert score > 60

    def test_drop_with_volume(self):
        closes = list(np.linspace(12, 10, 25))
        vols = [1_000_000] * 15 + [2_000_000] * 10
        df = _make_klines_df(closes, vols)
        score = CPEngine._calc_volume_confirmation(df, lookback=10, avg_days=20)
        assert score < 40

    def test_drop_low_volume_is_bottom_signal(self):
        closes = list(np.linspace(12, 11, 25))
        vols = [1_000_000] * 15 + [400_000] * 10
        df = _make_klines_df(closes, vols)
        score = CPEngine._calc_volume_confirmation(df, lookback=10, avg_days=20)
        assert score >= 40

    def test_none_klines(self):
        assert CPEngine._calc_volume_confirmation(None) == 50.0

    def test_score_bounded(self):
        closes = list(np.linspace(10, 20, 25))
        vols = [100] * 15 + [10_000_000] * 10
        df = _make_klines_df(closes, vols)
        score = CPEngine._calc_volume_confirmation(df, lookback=10, avg_days=20)
        assert 0 <= score <= 100


# --------------- integration: apply_multi_day_momentum ---------------

class TestApplyMultiDayMomentum:
    @patch.object(CPEngine, '_get_bulk_klines_for_momentum')
    def test_momentum_score_in_valid_range(self, mock_bulk):
        closes = list(np.linspace(10, 12, 35))
        kdf = _make_klines_df(closes)
        mock_bulk.return_value = {"000001": kdf}

        engine = CPEngine()
        stock = _make_stock()
        engine.stocks = [stock]

        def dummy_momentum(code, days):
            return 5.0

        engine.apply_multi_day_momentum(dummy_momentum, days=5)
        assert -10 <= stock.momentum_score <= 10

    @patch.object(CPEngine, '_get_bulk_klines_for_momentum')
    def test_no_klines_still_works(self, mock_bulk):
        mock_bulk.return_value = {}

        engine = CPEngine()
        stock = _make_stock()
        engine.stocks = [stock]

        engine.apply_multi_day_momentum(lambda c, d: 0, days=5)
        assert -10 <= stock.momentum_score <= 10

    @patch.object(CPEngine, '_get_bulk_klines_for_momentum')
    def test_different_klines_produce_different_scores(self, mock_bulk):
        """反转主导权重下，下跌K线的动量分 > 上涨K线（买跌反弹）"""
        up_closes = list(np.linspace(10, 15, 35))
        down_closes = list(np.linspace(15, 10, 35))

        engine1 = CPEngine()
        s1 = _make_stock(change_pct=2.0)
        engine1.stocks = [s1]
        mock_bulk.return_value = {"000001": _make_klines_df(up_closes)}
        engine1.apply_multi_day_momentum(lambda c, d: 5.0, days=5)

        engine2 = CPEngine()
        s2 = _make_stock(change_pct=-2.0)
        engine2.stocks = [s2]
        mock_bulk.return_value = {"000001": _make_klines_df(down_closes)}
        engine2.apply_multi_day_momentum(lambda c, d: -5.0, days=5)

        assert s1.momentum_score != s2.momentum_score
        # short_reversal=0.50: 下跌股票反转分高，总分更高
        assert s2.momentum_score > s1.momentum_score
