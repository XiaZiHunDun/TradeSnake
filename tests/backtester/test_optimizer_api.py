"""Tests for async optimizer API"""

import pytest
from unittest.mock import MagicMock, patch
import uuid


class TestOptimizationTasks:
    """Test optimization tasks dictionary and helpers"""

    def test_optimization_tasks_is_dict(self):
        """Verify _optimization_tasks is a dict"""
        pytest.importorskip("fastapi", reason="FastAPI required for router import")
        from backend.api.router import _optimization_tasks
        assert isinstance(_optimization_tasks, dict)

    def test_optimize_strategy_returns_task_id(self):
        """Test that optimize_strategy returns task_id and status"""
        fastapi = pytest.importorskip("fastapi", reason="FastAPI required")
        from fastapi.testclient import TestClient

        # Skip if router can't be loaded (missing dependencies)
        try:
            from backend.api.main import app
            client = TestClient(app)
        except Exception:
            pytest.skip("Cannot load app (missing dependencies)")

        # Mock the async task to avoid actually running optimization
        with patch('asyncio.create_task') as mock_task:
            response = client.post(
                "/api/backtest/optimize",
                json={"start_date": "2024-01-01", "end_date": "2024-12-31"}
            )
            assert response.status_code == 200
            data = response.json()
            assert 'task_id' in data
            assert data['status'] == 'running'
            # Verify create_task was called
            mock_task.assert_called_once()

    def test_get_optimization_status_not_found(self):
        """Test that status endpoint returns 404 for unknown task"""
        fastapi = pytest.importorskip("fastapi", reason="FastAPI required")
        from fastapi.testclient import TestClient

        try:
            from backend.api.main import app
            client = TestClient(app)
        except Exception:
            pytest.skip("Cannot load app (missing dependencies)")

        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/backtest/status/{fake_id}")
        assert response.status_code == 404

    def test_factor_analysis_endpoint(self):
        """Test factor analysis endpoint"""
        fastapi = pytest.importorskip("fastapi", reason="FastAPI required")
        from fastapi.testclient import TestClient

        try:
            from backend.api.main import app
            client = TestClient(app)
        except Exception:
            pytest.skip("Cannot load app (missing dependencies)")

        response = client.get(
            "/api/backtest/factor_analysis",
            params={"start_date": "2024-01-01", "end_date": "2024-12-31"}
        )
        assert response.status_code == 200
        data = response.json()
        assert 'ic_analysis' in data
        assert 'group_returns' in data
