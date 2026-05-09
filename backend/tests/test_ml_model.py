"""ML 模块单元测试"""
import pytest
import tempfile
import shutil
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── feature helpers ──────────────────────────────────────

class TestFeatureHelpers:
    def test_compute_rsi_normal(self):
        from backend.ml.features import compute_rsi
        closes = np.array([10 + 0.1 * i for i in range(20)])
        rsi = compute_rsi(closes, 14)
        assert 50 < rsi <= 100

    def test_compute_rsi_all_up(self):
        from backend.ml.features import compute_rsi
        closes = np.arange(1, 20, dtype=float)
        rsi = compute_rsi(closes, 14)
        assert rsi == 100.0

    def test_compute_rsi_short_data(self):
        from backend.ml.features import compute_rsi
        assert compute_rsi(np.array([10.0, 11.0]), 14) == 50.0

    def test_compute_macd(self):
        from backend.ml.features import compute_macd
        closes = np.array([10 + 0.05 * i for i in range(30)])
        diff, signal = compute_macd(closes)
        assert isinstance(diff, float)
        assert isinstance(signal, float)

    def test_compute_macd_short(self):
        from backend.ml.features import compute_macd
        diff, signal = compute_macd(np.array([10.0] * 5))
        assert diff == 0.0

    def test_ma_slope(self):
        from backend.ml.features import compute_ma_slope
        closes = np.array([10 + i for i in range(10)])
        slope = compute_ma_slope(closes, 5)
        assert slope > 0

    def test_volume_ratio(self):
        from backend.ml.features import compute_volume_ratio
        vols = np.array([1e6] * 15 + [2e6] * 5)
        ratio = compute_volume_ratio(vols, 5, 20)
        assert ratio > 1.0


# ── model train/predict/save/load ────────────────────────

class TestStockPredictor:
    @pytest.fixture
    def sample_data(self):
        np.random.seed(42)
        n = 200
        from backend.ml.features import ALL_FEATURES
        X = pd.DataFrame(
            np.random.randn(n, len(ALL_FEATURES)),
            columns=ALL_FEATURES,
        )
        y = pd.Series(np.random.randn(n) * 5, name="target")
        return X, y

    def test_train_and_predict(self, sample_data):
        from backend.ml.model import StockPredictor
        X, y = sample_data
        model = StockPredictor()
        metrics = model.train(X[:160], y[:160], X[160:], y[160:])
        assert "val_mae" in metrics
        assert model.is_trained

        preds = model.predict_return(X[:10])
        assert len(preds) == 10

        probs = model.predict_direction(X[:10])
        assert len(probs) == 10
        assert all(0 <= p <= 1 for p in probs)

    def test_feature_importance(self, sample_data):
        from backend.ml.model import StockPredictor
        X, y = sample_data
        model = StockPredictor()
        model.train(X, y)
        imp = model.feature_importance()
        assert len(imp) > 0
        assert sum(imp.values()) == pytest.approx(1.0, abs=0.01)

    def test_save_and_load(self, sample_data):
        from backend.ml.model import StockPredictor, MODEL_DIR
        X, y = sample_data

        tmp = Path(tempfile.mkdtemp())
        try:
            with patch("backend.ml.model.MODEL_DIR", tmp):
                m1 = StockPredictor()
                m1.train(X[:160], y[:160], X[160:], y[160:])
                m1.save("test_v1")

                m2 = StockPredictor()
                assert m2.load("test_v1")
                assert m2.is_trained

                p1 = m1.predict_return(X[:5])
                p2 = m2.predict_return(X[:5])
                np.testing.assert_array_almost_equal(p1, p2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_nonexistent(self):
        from backend.ml.model import StockPredictor
        model = StockPredictor()
        assert not model.load("nonexistent_version_xyz")

    def test_predict_without_train_raises(self):
        from backend.ml.model import StockPredictor
        model = StockPredictor()
        with pytest.raises(RuntimeError, match="not trained"):
            model.predict_return(pd.DataFrame({"a": [1]}))


# ── walk-forward ─────────────────────────────────────────

class TestWalkForwardValidator:
    def test_generate_folds(self):
        from backend.ml.walk_forward import WalkForwardValidator
        v = WalkForwardValidator(train_window=5, test_window=2, step_size=2)
        dates = [f"2026-01-{d:02d}" for d in range(1, 21)]
        folds = v._generate_folds(dates)
        assert len(folds) >= 1
        for train, test in folds:
            assert len(train) == 5
            assert len(test) == 2
            assert train[-1] < test[0]

    def test_empty_dates(self):
        from backend.ml.walk_forward import WalkForwardValidator
        v = WalkForwardValidator(train_window=120, test_window=20)
        folds = v._generate_folds([])
        assert folds == []


# ── predictor fallback ───────────────────────────────────

class TestPredictorFallback:
    def test_gain_predictor_falls_back_to_rules(self):
        from backend.engine.gain_predictor.predictor import GainPredictor
        gp = GainPredictor()
        ml = gp._get_ml_model()
        assert ml is None
        assert gp.model_version == "rule_v19.8"

    def test_probability_predictor_falls_back_to_rules(self):
        from backend.engine.probability_predictor.predictor import ProbabilityPredictor
        pp = ProbabilityPredictor()
        ml = pp._get_ml_model()
        assert ml is None
        assert pp.model_version == "rule_v19.8"
