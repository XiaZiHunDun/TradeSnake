"""Simulator域路由单元测试"""

from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
import pytest


@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    yield


with patch('backend.api.main.lifespan', mock_lifespan):
    from fastapi.testclient import TestClient
    from backend.api.routers import simulator as sim_router

test_app = FastAPI()
test_app.include_router(sim_router.router)
client = TestClient(test_app)


class TestAccount:
    def test_account_returns_cash_and_assets(self):
        mock_db = MagicMock()
        mock_db.get_account.return_value = {'cash': 10000, 'initial_cash': 20000}
        mock_db.get_holdings.return_value = []
        mock_db.get_stock.return_value = {'price': 0}

        with patch('backend.api.routers.simulator.db', mock_db):
            response = client.get("/api/account")
            assert response.status_code == 200
            data = response.json()
            assert 'cash' in data
            assert 'total_assets' in data

    def test_account_with_holdings(self):
        mock_db = MagicMock()
        mock_db.get_account.return_value = {'cash': 5000, 'initial_cash': 20000}
        mock_db.get_holdings.return_value = [{'code': 'sh600519', 'name': '贵州茅台', 'total_quantity': 100, 'avg_cost_price': 1500}]
        mock_db.get_stock.return_value = {'price': 1800}
        mock_db.get_today_bought_quantity.return_value = 0

        with patch('backend.api.routers.simulator.db', mock_db):
            response = client.get("/api/account")
            assert response.status_code == 200
            data = response.json()
            assert data['total_market_value'] > 0


class TestPortfolio:
    def test_portfolio_empty_holdings(self):
        mock_db = MagicMock()
        mock_db.get_holdings.return_value = []
        mock_db.get_account.return_value = {'cash': 20000}
        mock_db.get_stock.return_value = None

        with patch('backend.api.routers.simulator.db', mock_db):
            response = client.get("/api/portfolio")
            assert response.status_code == 200
            data = response.json()
            assert data['holdings'] == []

    def test_portfolio_with_holdings(self):
        mock_db = MagicMock()
        mock_db.get_holdings.return_value = [
            {'code': 'sh600519', 'name': '贵州茅台', 'total_quantity': 100, 'avg_cost_price': 1500, 'latest_bought_at': ''}
        ]
        mock_db.get_account.return_value = {'cash': 5000}
        mock_db.get_stock.return_value = {'price': 1800}
        mock_db.get_today_bought_quantity.return_value = 0

        with patch('backend.api.routers.simulator.db', mock_db):
            response = client.get("/api/portfolio")
            assert response.status_code == 200
            data = response.json()
            assert len(data['holdings']) == 1


class TestTrade:
    def test_buy_success(self):
        mock_trader = MagicMock()
        mock_trader.buy.return_value = {
            'success': True, 'code': '600519', 'name': '贵州茅台',
            'quantity': 100, 'price': 1800, 'commission': 5,
            'transfer_fee': 1, 'total_cost': 180806, 'remaining_cash': 8194
        }
        mock_db = MagicMock()
        mock_db.get_account.return_value = {'cash': 10000, 'initial_cash': 20000}
        mock_db.get_holdings.return_value = []
        mock_db.get_stock.return_value = {'price': 1800}
        mock_db.get_today_bought_quantity.return_value = 0

        with patch('backend.api.routers.simulator.trader', mock_trader):
            with patch('backend.api.routers.simulator.db', mock_db):
                response = client.post("/api/trade/buy", json={'code': '600519', 'quantity': 100, 'price': 1800})
                assert response.status_code == 200
                data = response.json()
                assert data['success'] is True

    def test_buy_failure_insufficient_cash(self):
        mock_trader = MagicMock()
        mock_trader.buy.return_value = {'success': False, 'error': '余额不足'}

        with patch('backend.api.routers.simulator.trader', mock_trader):
            response = client.post("/api/trade/buy", json={'code': '600519', 'quantity': 100, 'price': 1800})
            assert response.status_code == 400

    def test_sell_success(self):
        mock_trader = MagicMock()
        mock_trader.sell.return_value = {
            'success': True, 'code': '600519', 'name': '贵州茅台',
            'quantity': 100, 'price': 1800, 'commission': 3, 'stamp_tax': 9,
            'transfer_fee': 1, 'sell_value': 180000, 'total_proceeds': 179887, 'remaining_cash': 18994
        }
        mock_db = MagicMock()
        mock_db.get_account.return_value = {'cash': 10000, 'initial_cash': 20000}
        mock_db.get_holdings.return_value = []
        mock_db.get_stock.return_value = {'price': 1800}
        mock_db.get_today_bought_quantity.return_value = 0

        with patch('backend.api.routers.simulator.trader', mock_trader):
            with patch('backend.api.routers.simulator.db', mock_db):
                response = client.post("/api/trade/sell", json={'code': '600519', 'quantity': 100, 'price': 1800})
                assert response.status_code == 200
                data = response.json()
                assert data['success'] is True

    def test_sell_failure_no_holding(self):
        mock_trader = MagicMock()
        mock_trader.sell.return_value = {'success': False, 'error': '无持仓'}

        with patch('backend.api.routers.simulator.trader', mock_trader):
            response = client.post("/api/trade/sell", json={'code': '600519', 'quantity': 100, 'price': 1800})
            assert response.status_code == 400


class TestUserProfile:
    def test_get_user_profile(self):
        mock_db = MagicMock()
        mock_db.get_user_profile.return_value = {'theme': 'dark', 'default_top_n': 20}

        with patch('backend.api.routers.simulator.db', mock_db):
            response = client.get("/api/user/profile")
            assert response.status_code == 200
            data = response.json()
            assert 'profile' in data

    def test_update_user_profile(self):
        mock_db = MagicMock()
        mock_db.get_user_profile.return_value = {}
        mock_db.save_user_profile.return_value = True

        with patch('backend.api.routers.simulator.db', mock_db):
            response = client.put("/api/user/profile", json={'theme': 'light'})
            assert response.status_code == 200


class TestTradeHistory:
    def test_get_trades(self):
        mock_trader = MagicMock()
        mock_trader.get_trade_history.return_value = [
            {'id': 1, 'code': '600519', 'name': '贵州茅台', 'action': 'buy',
             'quantity': 100, 'price': 1800, 'commission': 5, 'stamp_tax': 0,
             'transfer_fee': 1, 'total_amount': 180000, 'recorded_at': '2024-01-01'}
        ]

        with patch('backend.api.routers.simulator.trader', mock_trader):
            response = client.get("/api/trades")
            assert response.status_code == 200
            data = response.json()
            assert 'trades' in data