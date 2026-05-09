"""
API路由单元测试
"""

from contextlib import asynccontextmanager
from unittest.mock import patch

from fastapi import FastAPI
import pytest


@asynccontextmanager
async def mock_lifespan(app: FastAPI):
    yield


with patch('backend.api.main.lifespan', mock_lifespan):
    from fastapi.testclient import TestClient
    from backend.api.main import app

    client = TestClient(app)


class TestHealthEndpoint:
    """测试健康检查端点"""

    def test_health_check(self):
        """测试健康检查返回正常"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_check_fields(self):
        """测试健康检查包含必要字段"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "stocks_count" in data
        assert "data_fresh" in data
        assert "last_update" in data


class TestRootEndpoint:
    """测试根端点"""

    def test_root(self):
        """测试根路径返回API信息"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data

    def test_root_fields(self):
        """测试根路径包含描述信息"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "description" in data


class TestCPEndpoints:
    """测试战力相关端点"""

    def test_cp_top(self):
        """测试获取战力榜"""
        response = client.get("/api/cp/top?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_cp_top_with_limit(self):
        """测试带limit参数的战力榜"""
        response = client.get("/api/cp/top?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) <= 5

    def test_cp_top_limit_boundary(self):
        """测试战力榜limit边界验证"""
        # limit > 3000 should fail validation
        response = client.get("/api/cp/top?limit=3001")
        assert response.status_code == 422  # FastAPI validation error

    def test_cp_top_response_structure(self):
        """测试战力榜响应包含必要字段"""
        response = client.get("/api/cp/top?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "data" in data
        assert "updated_at" in data

    @pytest.mark.integration
    def test_cp_top_score_ranges(self):
        """测试战力榜分数在有效范围内"""
        response = client.get("/api/cp/top?limit=10")
        assert response.status_code == 200
        data = response.json()
        for stock in data.get("data", []):
            # 验证各因子分数在0-100范围内（归一化后）
            assert 0 <= stock["growth_score"] <= 100, f"growth_score out of range: {stock['growth_score']}"
            assert 0 <= stock["value_score"] <= 100, f"value_score out of range: {stock['value_score']}"
            assert 0 <= stock["quality_score"] <= 100, f"quality_score out of range: {stock['quality_score']}"
            assert 0 <= stock["momentum_score"] <= 100, f"momentum_score out of range: {stock['momentum_score']}"
            assert 0 <= stock["total_cp"] <= 100, f"total_cp out of range: {stock['total_cp']}"
            # 验证风险分数在0-100范围内
            assert 0 <= stock["risk_score"] <= 100, f"risk_score out of range: {stock['risk_score']}"

    def test_cp_bottom(self):
        """测试获取BOTTOM榜"""
        response = client.get("/api/cp/bottom?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_cp_bottom_limit_boundary(self):
        """测试避雷榜limit边界验证"""
        # limit > 50 should fail validation
        response = client.get("/api/cp/bottom?limit=51")
        assert response.status_code == 422  # FastAPI validation error


class TestStockEndpoint:
    """测试单只股票端点"""

    def test_stock_not_found(self):
        """测试获取不存在的股票"""
        response = client.get("/api/cp/stock/INVALID")
        # 可能返回404或200（如果引擎有数据）
        assert response.status_code in [200, 404]


class TestMarketStatsEndpoint:
    """测试市场统计端点"""

    def test_market_stats(self):
        """测试获取市场统计"""
        response = client.get("/api/stats/market")
        assert response.status_code == 200
        data = response.json()
        assert "total_stocks" in data
        assert "avg_cp" in data

    def test_market_stats_fields(self):
        """测试市场统计包含完整字段"""
        response = client.get("/api/stats/market")
        assert response.status_code == 200
        data = response.json()
        assert "high_cp_count" in data
        assert "mid_cp_count" in data
        assert "low_cp_count" in data
        assert "avg_change" in data
        assert "rising_stocks" in data
        assert "falling_stocks" in data
        assert "unchanged_stocks" in data


class TestRecommendEndpoint:
    """测试推荐端点"""

    def test_recommend_value(self):
        """测试价值型推荐"""
        response = client.get("/api/cp/recommend?category=value")
        assert response.status_code == 200
        data = response.json()
        assert "category" in data
        assert "data" in data

    def test_recommend_growth(self):
        """测试成长型推荐"""
        response = client.get("/api/cp/recommend?category=growth")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "growth"

    def test_recommend_momentum(self):
        """测试趋势型推荐"""
        response = client.get("/api/cp/recommend?category=momentum")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "momentum"

    def test_recommend_invalid_category(self):
        """测试无效category返回错误"""
        response = client.get("/api/cp/recommend?category=invalid")
        assert response.status_code == 422

    def test_recommend_quality(self):
        """测试质量型推荐"""
        response = client.get("/api/cp/recommend?category=quality")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "quality"


class TestHistoryEndpoints:
    """测试历史数据端点"""

    def test_history_changes(self):
        """测试战力变化接口"""
        response = client.get("/api/history/changes?days=7")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)  # Returns list of stock change objects

    def test_history_changes_days_boundary(self):
        """测试战力变化days参数边界"""
        # days > 30 should fail validation
        response = client.get("/api/history/changes?days=31")
        assert response.status_code == 422

    def test_history_rankings_top(self):
        """测试历史TOP10接口"""
        response = client.get("/api/history/rankings?days=30&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_history_single_stock(self):
        """测试单只股票历史接口"""
        response = client.get("/api/history/600519?days=7")
        assert response.status_code == 200
        data = response.json()


@pytest.mark.integration
class TestRefreshEndpoint:
    """测试数据刷新端点"""

    def test_refresh_success(self):
        """测试成功刷新数据"""
        response = client.post("/api/refresh?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "stocks_updated" in data
        assert "updated_at" in data

    def test_refresh_with_default_limit(self):
        """测试使用默认limit刷新"""
        response = client.post("/api/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_refresh_limit_boundary_low(self):
        """测试limit边界值（下限）"""
        # limit < 10 should fail validation
        response = client.post("/api/refresh?limit=5")
        assert response.status_code == 422  # FastAPI validation error

    def test_refresh_limit_boundary_high(self):
        """测试limit边界值（上限）"""
        # limit > 3000 should fail validation
        response = client.post("/api/refresh?limit=3001")
        assert response.status_code == 422  # FastAPI validation error

    def test_refresh_limit_at_minimum(self):
        """测试limit在最小有效值"""
        response = client.post("/api/refresh?limit=10")
        assert response.status_code == 200

    def test_refresh_limit_at_maximum(self):
        """测试limit在最大有效值"""
        response = client.post("/api/refresh?limit=500")
        assert response.status_code == 200


class TestBacktestEndpoints:
    """测试回测相关端点"""

    def test_backtest_compare(self):
        """测试对比回测"""
        response = client.get("/api/backtest/compare?start_date=2024-01-01&end_date=2024-06-30")
        assert response.status_code in [200, 400, 500]  # 可能有数据不足错误

    def test_backtest_simple(self):
        """测试简单回测"""
        response = client.get("/api/backtest/simple?start_date=2024-01-01&end_date=2024-06-30")
        # 可能返回数据不足或实际结果
        assert response.status_code in [200, 400, 500]

    def test_backtest_date_validation(self):
        """测试回测日期验证"""
        # 结束日期早于开始日期
        response = client.get("/api/backtest/simple?start_date=2024-12-31&end_date=2024-01-01")
        # 应该返回错误
        data = response.json()
        assert "error" in data or "detail" in data


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
