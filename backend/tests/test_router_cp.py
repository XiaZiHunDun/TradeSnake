"""CP域路由单元测试"""

from contextlib import asynccontextmanager
from unittest.mock import patch, MagicMock
from datetime import datetime

from fastapi import FastAPI
import pytest


@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    yield


# Build a minimal test app for cp router
with patch('backend.api.main.lifespan', mock_lifespan):
    from fastapi.testclient import TestClient
    from backend.api.routers import cp as cp_router

test_app = FastAPI()
test_app.include_router(cp_router.router)

client = TestClient(test_app)


def mock_stock(code, name, total_cp=60, price=10):
    stock = MagicMock()
    stock.code = code
    stock.name = name
    stock.price = price
    stock.pe = 10
    stock.roe = 15.0
    stock.net_profit_growth = 10.0
    stock.revenue_growth = 12.0
    stock.change_pct = 1.5
    stock.growth_score = 70.0
    stock.value_score = 80.0
    stock.quality_score = 90.0
    stock.momentum_score = 60.0
    stock.total_cp = total_cp
    stock.risk_score = 30
    stock.get_risk_level.return_value = 'medium'
    stock.peg = 1.2
    stock.pb = 2.0
    stock.gross_margin = 80.0
    stock.revenue = 1e9
    stock.cashflow = 1e8
    stock.debt_ratio = 0.5
    stock.dividend_yield = 2.0
    stock.market_cap = 1e10
    stock.high = 12.0
    stock.low = 9.0
    stock.data_quality = 'good'
    stock.board_type = 'A'
    stock.board_name = '沪市主板'
    stock.sector = '白酒'
    stock.can_trade_newbie = True
    stock.trade_requirement = ''
    stock.current_ratio = 2.0
    stock.interest_coverage = 5.0
    stock.deducted_net_profit = 1e8
    stock.get_cp_explanation.return_value = {
        'code': '600519', 'name': '贵州茅台', 'total_cp': total_cp,
        'factors': [{'name': 'growth', 'score': 70}],
        'risk': {'score': 30, 'level': 'medium', 'items': [], 'adjustment': ''},
        'data_quality': 'high', 'summary': '战力优秀'
    }
    return stock


class TestCPTop:
    def test_cp_top_returns_list(self):
        mock_ce = MagicMock()
        mock_ce.stocks = [mock_stock('600519', '贵州茅台', 85), mock_stock('000001', '平安银行', 70)]
        mock_ce.get_top.return_value = mock_ce.stocks

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/cp/top?limit=10")
            assert response.status_code == 200
            data = response.json()
            assert 'data' in data
            assert 'total' in data
            assert len(data['data']) == 2

    def test_cp_top_empty_stocks(self):
        mock_ce = MagicMock()
        mock_ce.stocks = []

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/cp/top?limit=10")
            assert response.status_code == 200
            data = response.json()
            assert data['data'] == []
            assert data['total'] == 0

    def test_cp_top_limit_respected(self):
        mock_ce = MagicMock()
        mock_ce.stocks = [mock_stock(f'00{i}', f'股票{i}', 80 - i) for i in range(20)]
        mock_ce.get_top.return_value = mock_ce.stocks[:5]

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/cp/top?limit=5")
            assert response.status_code == 200
            data = response.json()
            assert len(data['data']) == 5


class TestCPSystem:
    def test_cp_bottom_returns_list(self):
        mock_ce = MagicMock()
        mock_ce.stocks = [mock_stock('600519', '贵州茅台', 85), mock_stock('000001', '平安银行', 30)]
        mock_ce.get_bottom.return_value = [mock_stock('000001', '平安银行', 30)]

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/cp/bottom?limit=5")
            assert response.status_code == 200
            data = response.json()
            assert len(data['data']) == 1

    def test_cp_bottom_empty(self):
        mock_ce = MagicMock()
        mock_ce.stocks = []

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/cp/bottom?limit=5")
            assert response.status_code == 200
            data = response.json()
            assert data['data'] == []


class TestMarketStats:
    def test_market_stats_normal(self):
        mock_ce = MagicMock()
        mock_ce.stocks = [
            mock_stock('600519', '贵州茅台', 85),
            mock_stock('000001', '平安银行', 30),
            mock_stock('000002', '万科A', 50),
        ]

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/stats/market")
            assert response.status_code == 200
            data = response.json()
            assert data['total_stocks'] == 3
            assert data['high_cp_count'] == 1  # >= 70
            assert data['mid_cp_count'] == 1   # 40-70
            assert data['low_cp_count'] == 1   # < 40

    def test_market_stats_empty(self):
        mock_ce = MagicMock()
        mock_ce.stocks = []

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/stats/market")
            assert response.status_code == 200
            data = response.json()
            assert data['total_stocks'] == 0


class TestSingleStock:
    def test_cp_stock_found(self):
        mock_ce = MagicMock()
        mock_stock_obj = mock_stock('600519', '贵州茅台', 85)
        mock_ce.get_by_code.return_value = mock_stock_obj

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/cp/stock/600519")
            assert response.status_code == 200
            data = response.json()
            assert data['code'] == '600519'
            assert data['name'] == '贵州茅台'

    def test_cp_stock_not_found(self):
        mock_ce = MagicMock()
        mock_ce.get_by_code.return_value = None

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/cp/stock/999999")
            assert response.status_code == 404


class TestCPExplain:
    def test_cp_explain_found(self):
        mock_ce = MagicMock()
        mock_stock_obj = mock_stock('600519', '贵州茅台', 85)
        mock_ce.get_by_code.return_value = mock_stock_obj

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/cp/explain/600519")
            assert response.status_code == 200
            data = response.json()
            assert data['code'] == '600519'
            assert data['name'] == '贵州茅台'
            assert 'factors' in data

    def test_cp_explain_not_found(self):
        mock_ce = MagicMock()
        mock_ce.get_by_code.return_value = None

        with patch('backend.api.routers.cp.cp_engine', mock_ce):
            response = client.get("/api/cp/explain/999999")
            assert response.status_code == 404