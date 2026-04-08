"""
战力历史记录单元测试
"""

import pytest
import sys
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engine.history import (
    save_history,
    load_history,
    get_stock_history,
    get_cp_changes,
    get_historical_rankings,
    get_ranking_changes,
    ensure_dir
)


def _create_sample_stocks():
    """创建示例股票数据"""
    return [
        {
            "code": "600519",
            "name": "贵州茅台",
            "price": 1800.0,
            "total_cp": 85.5,
            "growth_score": 30.0,
            "value_score": 25.0,
            "quality_score": 20.0,
            "momentum_score": 10.5
        },
        {
            "code": "000858",
            "name": "五粮液",
            "price": 200.0,
            "total_cp": 75.0,
            "growth_score": 25.0,
            "value_score": 20.0,
            "quality_score": 18.0,
            "momentum_score": 12.0
        },
        {
            "code": "600036",
            "name": "招商银行",
            "price": 40.0,
            "total_cp": 65.0,
            "growth_score": 20.0,
            "value_score": 22.0,
            "quality_score": 15.0,
            "momentum_score": 8.0
        }
    ]


class TestHistoryModule:
    """测试history模块"""

    def setup_method(self):
        """每个测试方法前设置临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, 'cp_history.json')

    def teardown_method(self):
        """每个测试方法后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _with_temp_path(self, func):
        """在临时路径下执行函数"""
        with patch('core.history.HISTORY_DIR', self.temp_dir), \
             patch('core.history.HISTORY_FILE', self.temp_file):
            return func()

    def test_save_and_load_history(self):
        """测试保存和加载历史记录"""
        stocks = _create_sample_stocks()
        today = datetime.now().strftime("%Y-%m-%d")

        def run():
            result = save_history(stocks)
            assert result is True

            history = load_history()
            assert today in history
            assert "stocks" in history[today]
            assert "600519" in history[today]["stocks"]
            assert history[today]["stocks"]["600519"]["name"] == "贵州茅台"

        self._with_temp_path(run)

    def test_load_history_nonexistent_file(self):
        """测试加载不存在的历史文件"""
        def run():
            history = load_history()
            assert history == {}

        self._with_temp_path(run)

    def test_load_history_with_days_limit(self):
        """测试加载历史记录时限制天数"""
        stocks = _create_sample_stocks()

        def run():
            # 保存今天的数据
            save_history(stocks)

            # 手动创建旧日期数据（模拟）
            if os.path.exists(self.temp_file):
                with open(self.temp_file, 'r') as f:
                    history = json.load(f)

                # 添加一个旧日期
                old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
                history[old_date] = history.pop(list(history.keys())[0])

                with open(self.temp_file, 'w') as f:
                    json.dump(history, f)

            # 只加载7天数据
            history = load_history(days=7)
            dates = list(history.keys())
            assert len(dates) <= 7

        self._with_temp_path(run)

    def test_get_stock_history(self):
        """测试获取单只股票历史"""
        stocks = _create_sample_stocks()

        def run():
            save_history(stocks)

            history = get_stock_history("600519", days=7)
            assert len(history) >= 1
            assert "total_cp" in history[-1]

        self._with_temp_path(run)

    def test_get_stock_history_not_found(self):
        """测试获取不存在的股票历史"""
        def run():
            history = get_stock_history("999999", days=7)
            assert history == []

        self._with_temp_path(run)

    def test_get_cp_changes(self):
        """测试获取战力变化"""
        stocks = _create_sample_stocks()

        def run():
            save_history(stocks)

            # 修改数据模拟变化
            if os.path.exists(self.temp_file):
                with open(self.temp_file, 'r') as f:
                    history = json.load(f)

                # 修改数据
                for code in history:
                    if "stocks" in history[code]:
                        for stock in history[code]["stocks"].values():
                            stock["total_cp"] = stock.get("total_cp", 0) * 1.1

                with open(self.temp_file, 'w') as f:
                    json.dump(history, f)

            changes = get_cp_changes(days=7)
            assert isinstance(changes, list)

        self._with_temp_path(run)

    def test_get_cp_changes_single_day(self):
        """测试单日数据时返回空列表"""
        stocks = _create_sample_stocks()

        def run():
            save_history(stocks)

            changes = get_cp_changes(days=1)
            assert changes == []

        self._with_temp_path(run)

    def test_get_historical_rankings(self):
        """测试获取历史榜单"""
        stocks = _create_sample_stocks()

        def run():
            save_history(stocks)

            rankings = get_historical_rankings(days=30, limit=10)
            assert isinstance(rankings, list)

            # 如果有数据
            if rankings:
                assert "date" in rankings[0]
                assert "top10" in rankings[0]
                assert len(rankings[0]["top10"]) <= 10

        self._with_temp_path(run)

    def test_get_historical_rankings_empty(self):
        """测试空数据时返回空列表"""
        def run():
            rankings = get_historical_rankings(days=30, limit=10)
            assert rankings == []

        self._with_temp_path(run)

    def test_get_ranking_changes(self):
        """测试获取排名变化"""
        stocks = _create_sample_stocks()

        def run():
            save_history(stocks)

            # 模拟多日数据变化
            if os.path.exists(self.temp_file):
                with open(self.temp_file, 'r') as f:
                    history = json.load(f)

                # 添加旧日期数据
                old_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
                old_stocks = {
                    "600036": {"code": "600036", "name": "招商银行", "total_cp": 80.0},
                    "000858": {"code": "000858", "name": "五粮液", "total_cp": 70.0},
                    "600000": {"code": "600000", "name": "浦发银行", "total_cp": 60.0},
                }
                history[old_date] = {"stocks": old_stocks, "saved_at": datetime.now().isoformat()}

                with open(self.temp_file, 'w') as f:
                    json.dump(history, f)

            changes = get_ranking_changes(days=30)
            assert isinstance(changes, list)
            # 应该包含new或drop类型的记录
            for change in changes:
                assert "type" in change
                assert change["type"] in ["new", "drop"]

        self._with_temp_path(run)

    def test_get_ranking_changes_single_day(self):
        """测试单日数据时返回空列表"""
        stocks = _create_sample_stocks()

        def run():
            save_history(stocks)

            changes = get_ranking_changes(days=1)
            assert changes == []

        self._with_temp_path(run)

    def test_save_history_cleanup_old_data(self):
        """测试保存时清理旧数据（超过30天）"""
        stocks = _create_sample_stocks()

        def run():
            # 手动创建超过30天的数据
            history = {}

            # 添加35天前的数据
            for i in range(35):
                old_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                history[old_date] = {
                    "stocks": {s["code"]: s for s in stocks},
                    "saved_at": datetime.now().isoformat()
                }

            with open(self.temp_file, 'w') as f:
                json.dump(history, f)

            # 保存新数据（应该触发清理）
            save_history(stocks)

            # 验证
            history = load_history(days=60)  # 请求更多天数
            dates = sorted(history.keys())
            assert len(dates) <= 30  # 应该只保留30天

        self._with_temp_path(run)


class TestHistoryEdgeCases:
    """测试历史模块边界情况"""

    def setup_method(self):
        """每个测试方法前设置临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, 'cp_history.json')

    def teardown_method(self):
        """每个测试方法后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _with_temp_path(self, func):
        """在临时路径下执行函数"""
        with patch('core.history.HISTORY_DIR', self.temp_dir), \
             patch('core.history.HISTORY_FILE', self.temp_file):
            return func()

    def test_empty_stock_list(self):
        """测试保存空股票列表"""
        def run():
            result = save_history([])
            assert result is True

            history = load_history()
            assert len(history) == 1  # 今天的数据

        self._with_temp_path(run)

    def test_corrupted_json_file(self):
        """测试损坏的JSON文件"""
        # 写入损坏的数据
        with open(self.temp_file, 'w') as f:
            f.write("{ invalid json }")

        def run():
            # 应该返回空字典而不是崩溃
            history = load_history()
            assert history == {}

        self._with_temp_path(run)

    def test_get_cp_changes_zero_old_cp(self):
        """测试旧CP为0时的情况"""
        def run():
            stocks = [
                {"code": "600519", "name": "贵州茅台", "total_cp": 0},
                {"code": "000858", "name": "五粮液", "total_cp": 50.0},
            ]
            save_history(stocks)

            # 修改数据
            if os.path.exists(self.temp_file):
                with open(self.temp_file, 'r') as f:
                    history = json.load(f)

                # 再次保存以创建多个日期
                save_history([{"code": "600519", "name": "贵州茅台", "total_cp": 80.0}])

                with open(self.temp_file, 'r') as f:
                    history = json.load(f)

                # 修改600519的旧数据为0
                for date in history:
                    if "600519" in history[date]["stocks"]:
                        history[date]["stocks"]["600519"]["total_cp"] = 0

                with open(self.temp_file, 'w') as f:
                    json.dump(history, f)

            changes = get_cp_changes(days=7)
            # 0作为分母时change_pct应该为0
            for change in changes:
                if change["old_cp"] == 0:
                    assert change["change_pct"] == 0

        self._with_temp_path(run)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
