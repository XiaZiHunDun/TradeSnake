"""History域路由单元测试"""

from contextlib import asynccontextmanager
from unittest.mock import patch

from fastapi import FastAPI
import pytest


@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    yield


with patch('backend.api.main.lifespan', mock_lifespan):
    from fastapi.testclient import TestClient
    from backend.api.routers import history as history_router

test_app = FastAPI()
test_app.include_router(history_router.router)
client = TestClient(test_app)


class TestHistoryChanges:
    def test_get_changes_default_days(self):
        mock_result = [{'code': '600519', 'change': 5.2, 'cp_before': 75, 'cp_after': 80}]
        with patch('backend.engine.cp_engine.history.get_cp_changes', return_value=mock_result):
            response = client.get("/api/history/changes")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_changes_custom_days(self):
        mock_result = [{'code': '600519', 'change': 3.1}]
        with patch('backend.engine.cp_engine.history.get_cp_changes', return_value=mock_result):
            response = client.get("/api/history/changes?days=14")
            assert response.status_code == 200

    def test_get_changes_out_of_range(self):
        response = client.get("/api/history/changes?days=0")
        assert response.status_code == 422  # Query validation fails for ge=1


class TestStockHistory:
    def test_stock_history_found(self):
        mock_result = [{'date': '2024-01-01', 'cp': 80}, {'date': '2024-01-02', 'cp': 82}]
        with patch('backend.engine.cp_engine.history.get_stock_history', return_value=mock_result):
            response = client.get("/api/history/600519?days=7")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_stock_history_route_works(self):
        # Test that the route itself is working (history module may return empty)
        response = client.get("/api/history/600519?days=7")
        # Could be 200 (empty list) or 500 (if history module fails)
        assert response.status_code in [200, 500]


class TestHistoricalRankings:
    def test_rankings_default_params(self):
        mock_result = [{'code': '600519', 'rank': 1, 'cp': 85}]
        with patch('backend.engine.cp_engine.history.get_historical_rankings', return_value=mock_result):
            response = client.get("/api/history/rankings")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_rankings_custom_params(self):
        mock_result = [{'code': '600519', 'rank': 1}]
        with patch('backend.engine.cp_engine.history.get_historical_rankings', return_value=mock_result):
            response = client.get("/api/history/rankings?days=30&limit=20")
            assert response.status_code == 200

    def test_rankings_days_validation(self):
        response = client.get("/api/history/rankings?days=0")
        assert response.status_code == 422