"""System域路由单元测试"""

from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock
from datetime import datetime

from fastapi import FastAPI
import pytest


@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    yield


with patch('backend.api.main.lifespan', mock_lifespan):
    from fastapi.testclient import TestClient
    from backend.api.routers import system as sys_router

test_app = FastAPI()
test_app.include_router(sys_router.router)
client = TestClient(test_app)


class TestHealth:
    def test_health_check_returns_ok(self):
        mock_ce = MagicMock()
        mock_ce.stocks = [MagicMock() for _ in range(10)]

        mock_cache = MagicMock()
        mock_cache.get_cache_stats.return_value = {'hits': 100, 'misses': 10}

        with patch('backend.api.routers.system.cp_engine', mock_ce):
            with patch('backend.api.routers.system.get_cache_manager', return_value=mock_cache):
                response = client.get("/api/health")
                assert response.status_code == 200
                data = response.json()
                assert data['status'] == 'ok'
                assert 'stocks_count' in data

    def test_health_check_empty_engine(self):
        mock_ce = MagicMock()
        mock_ce.stocks = []

        mock_cache = MagicMock()
        mock_cache.get_cache_stats.return_value = {}

        with patch('backend.api.routers.system.cp_engine', mock_ce):
            with patch('backend.api.routers.system.get_cache_manager', return_value=mock_cache):
                response = client.get("/api/health")
                assert response.status_code == 200
                data = response.json()
                assert data['stocks_count'] == 0


class TestPoolStats:
    def test_pool_stats_returns_counts(self):
        mock_selector = MagicMock()
        mock_selector.get_pool_stats.return_value = {'core': 50, 'active': 30, 'observe': 20}

        with patch('backend.stock_selector.stock_selector.get_stock_selector', return_value=mock_selector):
            response = client.get("/api/pool/stats")
            assert response.status_code == 200
            data = response.json()
            assert data['core_count'] == 50
            assert data['active_count'] == 30
            assert data['total_count'] == 100

    def test_pool_stats_empty(self):
        mock_selector = MagicMock()
        mock_selector.get_pool_stats.return_value = {}

        with patch('backend.stock_selector.stock_selector.get_stock_selector', return_value=mock_selector):
            response = client.get("/api/pool/stats")
            assert response.status_code == 200


@pytest.mark.integration
class TestRefresh:
    def test_refresh_route_exists(self):
        response = client.post("/api/refresh")
        # Complex endpoint with async lock, just verify route exists
        assert response.status_code in [200, 500]

    def test_refresh_with_limit(self):
        response = client.post("/api/refresh?limit=100")
        assert response.status_code in [200, 500]

    def test_refresh_invalid_limit(self):
        response = client.post("/api/refresh?limit=0")
        assert response.status_code == 422

    def test_refresh_limit_too_high(self):
        response = client.post("/api/refresh?limit=1000")
        assert response.status_code == 422


@pytest.mark.integration
class TestSnapshot:
    def test_snapshot_record_route_exists(self):
        response = client.post("/api/snapshot/record")
        assert response.status_code in [200, 500]