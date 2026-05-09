"""Risk域路由单元测试"""

from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
import pytest


@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    yield


with patch('backend.api.main.lifespan', mock_lifespan):
    from fastapi.testclient import TestClient
    from backend.api.routers import risk as risk_router

test_app = FastAPI()
test_app.include_router(risk_router.router)
client = TestClient(test_app)


class TestRiskReport:
    def test_risk_report_normal(self):
        mock_ce = MagicMock()
        mock_ce.stocks = [MagicMock() for _ in range(5)]

        mock_portfolio = MagicMock()
        mock_portfolio.get_holdings.return_value = [
            {'code': '600519', 'quantity': 100}
        ]

        mock_account = MagicMock()
        mock_account.cash = 10000

        mock_db = MagicMock()

        mock_ra_class = MagicMock()
        mock_ra_class.get_market_cp.return_value = 50
        mock_ra_class.generate_risk_report.return_value = {
            'portfolio_risk': 'medium',
            'var_95': 2000,
            'positions': []
        }

        with patch('backend.api.routers.risk.cp_engine', mock_ce):
            with patch('backend.api.routers.risk._portfolio', mock_portfolio):
                with patch('backend.api.routers.risk.account', mock_account):
                    with patch('backend.api.routers.risk.db', mock_db):
                        with patch('backend.api.routers.risk.RiskAnalyzer', mock_ra_class):
                            response = client.get("/api/risk/report")
                            assert response.status_code == 200
                            data = response.json()
                            assert 'portfolio_risk' in data


class TestBreakEven:
    def test_break_even_normal(self):
        mock_trader = MagicMock()
        mock_trader.get_position.return_value = {'cost_price': 100, 'current_price': 80}

        mock_ra_class = MagicMock()
        mock_ra_class.calculate_break_even.return_value = {'break_even_pct': 25.0}

        with patch('backend.api.routers.risk.trader', mock_trader):
            with patch('backend.api.routers.risk.RiskAnalyzer', mock_ra_class):
                response = client.get("/api/risk/break-even/600519")
                assert response.status_code == 200

    def test_break_even_no_position(self):
        mock_trader = MagicMock()
        mock_trader.get_position.return_value = None

        with patch('backend.api.routers.risk.trader', mock_trader):
            response = client.get("/api/risk/break-even/999999")
            assert response.status_code == 404

    def test_break_even_zero_price(self):
        mock_trader = MagicMock()
        mock_trader.get_position.return_value = {'cost_price': 100, 'current_price': 0}

        mock_ra_class = MagicMock()
        mock_ra_class.calculate_break_even.return_value = {'break_even_pct': 0}

        with patch('backend.api.routers.risk.trader', mock_trader):
            with patch('backend.api.routers.risk.RiskAnalyzer', mock_ra_class):
                response = client.get("/api/risk/break-even/600519")
                assert response.status_code == 200