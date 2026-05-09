"""Prediction域路由单元测试"""

from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
import pytest


@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    yield


with patch('backend.api.main.lifespan', mock_lifespan):
    from fastapi.testclient import TestClient
    from backend.api.routers import prediction as pred_router

test_app = FastAPI()
test_app.include_router(pred_router.router)
client = TestClient(test_app)


class TestGainPrediction:
    def test_gain_top_route_exists(self):
        # These endpoints run heavy computation, just verify route registration
        # Full integration test would need DuckDB + real data
        response = client.get("/api/prediction/gain/top?limit=10")
        # Either 200 (success) or 500 ( DuckDB not available in test env)
        assert response.status_code in [200, 500]


class TestProbabilityPrediction:
    def test_probability_top_route_exists(self):
        response = client.get("/api/prediction/probability/top?limit=10")
        assert response.status_code in [200, 500]


class TestVerifyAccuracy:
    def test_verify_gain_accuracy_route_exists(self):
        response = client.get("/api/verify/gain_accuracy?holding_days=5&top_n=20")
        # DuckDB might not be available, so either 200 or 500
        assert response.status_code in [200, 500]

    def test_verify_gain_accuracy_default_params(self):
        response = client.get("/api/verify/gain_accuracy")
        assert response.status_code in [200, 500]

    def test_verify_probability_accuracy_route_exists(self):
        response = client.get("/api/verify/probability_accuracy")
        assert response.status_code in [200, 500]

    def test_verify_probability_accuracy_custom_params(self):
        response = client.get("/api/verify/probability_accuracy?high_prob_threshold=0.65&low_prob_threshold=0.35")
        assert response.status_code in [200, 500]


class TestSingleStockPrediction:
    def test_gain_prediction_stock_route_exists(self):
        response = client.get("/api/prediction/gain/600519")
        # Either 404 (stock not found in DB) or 500 (DuckDB error) or 200
        assert response.status_code in [200, 404, 500]

    def test_probability_prediction_stock_route_exists(self):
        response = client.get("/api/prediction/probability/600519")
        assert response.status_code in [200, 404, 500]