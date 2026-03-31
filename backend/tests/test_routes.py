"""
API路由单元测试
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api.main import app


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
        # limit > 200 should fail validation
        response = client.get("/api/cp/top?limit=201")
        assert response.status_code == 422  # FastAPI validation error

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
        response = client.get("/api/stock/INVALID")
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


class TestRiskStatsEndpoint:
    """测试风险统计端点"""

    def test_risk_stats(self):
        """测试获取风险统计"""
        response = client.get("/api/stats/risk")
        assert response.status_code == 200
        data = response.json()
        assert "total_stocks" in data
        assert "high_risk_count" in data
        assert "medium_risk_count" in data
        assert "low_risk_count" in data
        assert "avg_risk_score" in data


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
        assert response.status_code == 400
        data = response.json()
        assert "无效的category类型" in data["detail"]

    def test_recommend_quality(self):
        """测试质量型推荐"""
        response = client.get("/api/cp/recommend?category=quality")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "quality"

    def test_recommend_allround(self):
        """测试综合型推荐"""
        response = client.get("/api/cp/recommend?category=allround")
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "allround"


class TestHistoryEndpoints:
    """测试历史数据端点"""

    def test_history_changes(self):
        """测试战力变化接口"""
        response = client.get("/api/history/changes?days=7")
        assert response.status_code == 200
        data = response.json()
        assert "days" in data

    def test_history_rankings_top(self):
        """测试历史TOP10接口"""
        response = client.get("/api/history/rankings/top?days=30")
        assert response.status_code == 200
        data = response.json()
        assert "days" in data

    def test_history_rankings_changes(self):
        """测试榜单变化接口"""
        response = client.get("/api/history/rankings/changes?days=30")
        assert response.status_code == 200
        data = response.json()
        assert "days" in data

    def test_history_single_stock(self):
        """测试单只股票历史接口"""
        response = client.get("/api/history/600519?days=7")
        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert "total" in data
        assert "data" in data


class TestBatchStocksEndpoint:
    """测试批量股票端点"""

    def test_batch_stocks(self):
        """测试批量获取股票"""
        response = client.post(
            "/api/stocks/batch",
            json=["600519", "000858"]
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "data" in data

    def test_batch_stocks_empty(self):
        """测试批量获取空列表"""
        response = client.post(
            "/api/stocks/batch",
            json=[]
        )
        assert response.status_code == 200

    def test_batch_stocks_exceed_limit(self):
        """测试批量获取超过限制时应返回错误"""
        # 创建超过50个股票代码的列表
        large_batch = [f"60{i:04d}" for i in range(1, 101)]
        response = client.post(
            "/api/stocks/batch",
            json=large_batch
        )
        assert response.status_code == 400
        data = response.json()
        assert "批量数量不能超过" in data["detail"]

    def test_batch_stocks_deduplication(self):
        """测试批量获取时自动去重"""
        # 发送包含重复代码的列表
        response = client.post(
            "/api/stocks/batch",
            json=["600519", "600519", "000858", "000858"]
        )
        assert response.status_code == 200
        data = response.json()
        # 应该只返回2个不同的股票，而不是4个
        assert data["total"] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
