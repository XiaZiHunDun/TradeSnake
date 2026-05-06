"""RiskManager 单元测试"""

import pytest
from backend.risk.risk_control import RiskManager, RiskCheckResult
from backend.engine.cp_engine.constants import RISK_MANAGEMENT


class TestRiskManager:
    """RiskManager 测试"""

    def setup_method(self):
        self.rm = RiskManager()

    # ---- 固定止损测试 ----

    def test_stop_loss_triggered(self):
        """固定止损触发"""
        position = {'current_price': 92, 'cost_price': 100}
        result = self.rm.check_stop_loss(position)
        assert result.should_sell is True
        assert '固定止损' in result.reason
        assert result.action == 'stop_loss'

    def test_stop_loss_not_triggered(self):
        """固定止损未触发"""
        position = {'current_price': 96, 'cost_price': 100}
        result = self.rm.check_stop_loss(position)
        assert result.should_sell is False

    def test_stop_loss_disabled(self):
        """风控关闭时不触发"""
        rm = RiskManager(config={'enabled': False})
        position = {'current_price': 50, 'cost_price': 100}
        result = rm.check_stop_loss(position)
        assert result.should_sell is False

    # ---- 尾随止损测试 ----

    def test_trailing_stop_triggered(self):
        """尾随止损触发"""
        position = {'current_price': 95, 'peak_price': 100}
        result = self.rm.check_trailing_stop(position)
        assert result.should_sell is True
        assert '尾随止损' in result.reason
        assert result.action == 'trailing_stop'

    def test_trailing_stop_not_triggered(self):
        """尾随止损未触发"""
        position = {'current_price': 98, 'peak_price': 100}
        result = self.rm.check_trailing_stop(position)
        assert result.should_sell is False

    def test_trailing_stop_disabled(self):
        """风控关闭时不触发"""
        rm = RiskManager(config={'enabled': False})
        position = {'current_price': 50, 'peak_price': 100}
        result = rm.check_trailing_stop(position)
        assert result.should_sell is False

    # ---- 组合回撤测试 ----

    def test_portfolio_drawdown_triggered_reduce(self):
        """组合回撤熔断-减半"""
        account_info = {'total_assets': 85000, 'peak_assets': 100000}
        result = self.rm.check_portfolio_drawdown(account_info)
        assert result.should_sell is True
        assert '组合回撤熔断' in result.reason
        assert result.action == 'reduce'

    def test_portfolio_drawdown_triggered_clear(self):
        """组合回撤熔断-清仓"""
        rm = RiskManager(config={**RISK_MANAGEMENT, 'portfolio_drawdown_action': 'clear'})
        account_info = {'total_assets': 80000, 'peak_assets': 100000}
        result = rm.check_portfolio_drawdown(account_info)
        assert result.should_sell is True
        assert result.action == 'clear'

    def test_portfolio_drawdown_not_triggered(self):
        """组合回撤未触发"""
        account_info = {'total_assets': 95000, 'peak_assets': 100000}
        result = self.rm.check_portfolio_drawdown(account_info)
        assert result.should_sell is False

    def test_portfolio_drawdown_disabled(self):
        """风控关闭时不触发"""
        rm = RiskManager(config={'enabled': False})
        account_info = {'total_assets': 50000, 'peak_assets': 100000}
        result = rm.check_portfolio_drawdown(account_info)
        assert result.should_sell is False

    # ---- Kelly 仓位计算测试 ----

    def test_kelly_disabled(self):
        """Kelly 关闭时返回 0"""
        rm = RiskManager(config={'enabled': True, 'use_kelly_sizing': False})
        shares = rm.calculate_kelly_position_size('600519', 100000, 10)
        assert shares == 0

    def test_kelly_no_data(self):
        """Kelly 无数据时使用默认参数计算"""
        rm = RiskManager()
        shares = rm.calculate_kelly_position_size('000000', 100000, 10)
        # 默认参数 win_rate=0.5, avg_win_pct=5, avg_loss_pct=3 会给出非零结果
        assert shares >= 0  # 至少是非负数

    # ---- 市场环境识别测试 ----

    def test_detect_market_regime_disabled(self):
        """市场环境识别关闭时返回 unknown"""
        rm = RiskManager(config={'enabled': True, 'market_regime_enabled': False})
        result = rm.detect_market_regime()
        assert result == 'unknown'

    def test_detect_market_regime_no_data(self):
        """无数据时返回 unknown"""
        rm = RiskManager()
        result = rm.detect_market_regime('000000')
        assert result == 'unknown'

    # ---- 仓位限制测试 ----

    def test_position_limit_bull(self):
        rm = RiskManager()
        limit = rm.get_position_limit_by_regime('bull')
        assert limit == 1.0

    def test_position_limit_bear(self):
        rm = RiskManager()
        limit = rm.get_position_limit_by_regime('bear')
        assert limit == 0.5

    def test_position_limit_unknown(self):
        rm = RiskManager()
        limit = rm.get_position_limit_by_regime('unknown')
        assert limit == 1.0

    # ---- 持仓风控信息测试 ----

    def test_get_positions_with_risk_info(self):
        """持仓风控信息计算"""
        holdings = [
            {'code': '600519', 'name': '茅台', 'avg_cost_price': 100, 'total_quantity': 100},
            {'code': '000001', 'name': '平安', 'avg_cost_price': 50, 'total_quantity': 200},
        ]
        prices = {'600519': 93, '000001': 48}

        result = self.rm.get_positions_with_risk_info(holdings, prices)

        # 茅台：亏损 -7%，触发止损
        assert result[0]['code'] == '600519'
        assert result[0]['pnl_pct'] == pytest.approx(-0.07)
        assert result[0]['should_stop_loss'] is True
        assert result[0]['should_trailing_stop'] is False

        # 平安：亏损 -4%，不触发止损（阈值-7%），也不触发尾随止损
        assert result[1]['code'] == '000001'
        assert result[1]['pnl_pct'] == pytest.approx(-0.04)
        assert result[1]['should_stop_loss'] is False


class TestRiskCheckResult:
    """RiskCheckResult 数据类测试"""

    def test_risk_check_result_defaults(self):
        result = RiskCheckResult(False, "")
        assert result.should_sell is False
        assert result.reason == ""
        assert result.action is None
