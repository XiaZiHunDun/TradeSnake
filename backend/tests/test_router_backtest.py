"""Backtest域路由单元测试"""

from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
import pytest


@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    yield


with patch('backend.api.main.lifespan', mock_lifespan):
    from fastapi.testclient import TestClient
    from backend.api.routers import backtest as bt_router

test_app = FastAPI()
test_app.include_router(bt_router.router)
client = TestClient(test_app)


class TestSimpleBacktest:
    def test_backtest_simple_valid_params(self):
        mock_be = MagicMock()
        mock_be.calculate_simple_backtest.return_value = {
            'total_return': 15.5, 'annualized_return': 18.2,
            'sharpe_ratio': 1.8, 'max_drawdown': -8.5,
            'win_rate': 62.5, 'total_trades': 45
        }

        with patch('backend.api.routers.backtest.backtest_engine', mock_be):
            response = client.get("/api/backtest/simple?start_date=2024-01-01&end_date=2024-12-31&holding_days=30&top_n=10")
            assert response.status_code == 200
            data = response.json()
            assert data['total_return'] == 15.5

    def test_backtest_simple_default_params(self):
        mock_be = MagicMock()
        mock_be.calculate_simple_backtest.return_value = {'total_return': 0}

        with patch('backend.api.routers.backtest.backtest_engine', mock_be):
            response = client.get("/api/backtest/simple?start_date=2024-01-01&end_date=2024-12-31")
            assert response.status_code == 200


class TestCompareAndBenchmark:
    def test_backtest_compare(self):
        mock_be = MagicMock()
        mock_be.calculate_compare_backtest.return_value = {'results': []}

        with patch('backend.api.routers.backtest.backtest_engine', mock_be):
            response = client.get("/api/backtest/compare?start_date=2024-01-01&end_date=2024-12-31&holding_days=30")
            assert response.status_code == 200

    def test_backtest_benchmark(self):
        mock_be = MagicMock()
        mock_be.calculate_benchmark_backtest.return_value = {'benchmark_return': 10}

        with patch('backend.api.routers.backtest.backtest_engine', mock_be):
            response = client.get("/api/backtest/benchmark?start_date=2024-01-01&end_date=2024-12-31&benchmark=hs300")
            assert response.status_code == 200

    def test_backtest_benchmark_invalid(self):
        response = client.get("/api/backtest/benchmark?start_date=2024-01-01&end_date=2024-12-31&benchmark=invalid")
        assert response.status_code == 422


class TestFullBacktest:
    def test_full_backtest_valid(self):
        mock_engine = MagicMock()
        mock_stats = MagicMock()
        mock_stats.initial_capital = 20000
        mock_stats.final_value = 23000
        mock_stats.total_return = 15.0
        mock_stats.annualized_return = 18.0
        mock_stats.sharpe_ratio = 1.5
        mock_stats.max_drawdown = -5.0
        mock_stats.win_rate = 60.0
        mock_stats.total_trades = 30
        mock_stats.equity_curve = [
            {'date': '2024-01-01', 'total_value': 20000, 'cash': 20000, 'position_value': 0}
        ]
        mock_stats.trades = [
            {'date': '2024-01-05', 'action': 'buy', 'code': '600519', 'name': '贵州茅台',
             'price': 1800, 'quantity': 10, 'amount': 18000, 'commission': 5, 'profit': 0, 'reason': ''}
        ]
        mock_stats.completed_pnls = []
        mock_engine.run.return_value = mock_stats

        with patch('backend.backtester.full_backtest.FullBacktestEngine', return_value=mock_engine):
            response = client.get("/api/backtest/full?start_date=2024-01-01&end_date=2024-12-31&strategy=top&top_n=10&initial_capital=20000")
            assert response.status_code == 200
            data = response.json()
            assert data['total_return'] == 15.0

    def test_full_backtest_invalid_date_format(self):
        response = client.get("/api/backtest/full?start_date=invalid&end_date=2024-12-31")
        assert response.status_code == 422


class TestOptimization:
    def test_optimize_strategy_creates_task(self):
        response = client.post("/api/backtest/optimize", json={
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'val_start': '2025-01-01',
            'val_end': '2025-06-30'
        })
        assert response.status_code == 200
        data = response.json()
        assert 'task_id' in data
        assert data['status'] == 'running'

    def test_optimization_status_not_found(self):
        response = client.get("/api/backtest/status/nonexistent-task-id")
        assert response.status_code == 404


class TestFactorAnalysis:
    def test_factor_analysis_valid(self):
        mock_cp_store = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Return only 5 rows (< 10), triggering the "insufficient data" early return
        mock_cursor.fetchall.return_value = [(f'2024-0{i}-01',) for i in range(1, 6)]
        mock_conn.cursor.return_value = mock_cursor
        mock_cp_store._get_conn.return_value = mock_conn

        mock_duckdb = MagicMock()

        with patch('backend.data_manager.cp_history_store.get_cp_history_store', return_value=mock_cp_store):
            with patch('backend.data_manager.duckdb_store.get_duckdb_store', return_value=mock_duckdb):
                response = client.get("/api/backtest/factor_analysis?start_date=2024-01-01&end_date=2024-06-30")
                assert response.status_code == 200

    def test_factor_analysis_invalid_date(self):
        response = client.get("/api/backtest/factor_analysis?start_date=bad-date&end_date=2024-06-30")
        assert response.status_code == 422