"""
模拟炒股模块单元测试 - Simulator Tests v19.7
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAccount:
    """账户模块测试"""

    def test_calculate_freeze(self):
        """测试冻结金额计算"""
        from backend.simulator.account import Account, COMMISSION_RATE, MIN_COMMISSION, TRANSFER_FEE_RATE

        account = Account()

        # 测试买入冻结计算
        # 100股 × 10元 = 1000元
        # 佣金 = max(1000 × 0.0003, 5) = 5元
        # 过户费 = 1000 × 0.00001 = 0.01元
        # 冻结总额 ≈ 1005.01元
        freeze = account.calculate_freeze(quantity=100, price=10.0, is_buy=True)
        expected = 1000 + max(1000 * COMMISSION_RATE, MIN_COMMISSION) + 1000 * TRANSFER_FEE_RATE
        assert abs(freeze - expected) < 0.01

    def test_can_buy_insufficient_cash(self):
        """测试资金不足时无法买入"""
        from backend.simulator.account import Account

        account = Account()

        # 假设账户现金为0，应该无法买入
        result, reason = account.can_buy(price=10.0, quantity=100)
        assert result == False
        assert "资金不足" in reason or "需要" in reason

    def test_can_buy_invalid_quantity(self):
        """测试无效数量无法买入"""
        from backend.simulator.account import Account

        account = Account()

        result, reason = account.can_buy(price=10.0, quantity=0)
        assert result == False
        assert "必须大于0" in reason

        result, reason = account.can_buy(price=10.0, quantity=-100)
        assert result == False


class TestPortfolio:
    """持仓模块测试"""

    def test_get_holdings_empty(self):
        """测试空持仓"""
        from backend.simulator.portfolio import Portfolio

        portfolio = Portfolio()
        holdings = portfolio.get_holdings()
        assert isinstance(holdings, list)

    def test_get_holding_profit_no_holding(self):
        """测试未持仓股票的盈亏计算"""
        from backend.simulator.portfolio import Portfolio

        portfolio = Portfolio()
        profit_info = portfolio.get_holding_profit("NONEXISTENT", 10.0)
        assert profit_info['profit'] == 0
        assert profit_info['profit_rate'] == 0


class TestTrader:
    """交易模块测试"""

    def test_order_error_exception(self):
        """测试订单异常类"""
        from backend.simulator.trader import OrderError

        error = OrderError("测试错误")
        assert str(error) == "测试错误"
        assert isinstance(error, Exception)

    def test_get_market_price_no_stock(self):
        """测试获取不存在股票的价格

        注意：此测试需要完整的data_manager模块，已跳过。
        集成测试应在后端服务运行时通过API进行。
        """
        pytest.skip("需要完整的data_manager模块，集成测试通过API进行")


class TestRiskControl:
    """风控模块测试"""

    def test_check_all_invalid_quantity(self):
        """测试无效交易数量被拦截"""
        from backend.simulator.risk_control import RiskControl

        result, reason = RiskControl.check_all(
            action='buy',
            code='000001',
            quantity=0,
            price=10.0,
            account=MagicMock(),
            portfolio=MagicMock()
        )
        assert result == False
        assert "必须大于0" in reason

    def test_check_all_invalid_unit(self):
        """测试非整手数量被拦截"""
        from backend.simulator.risk_control import RiskControl

        result, reason = RiskControl.check_all(
            action='buy',
            code='000001',
            quantity=150,  # 不是100的整数倍
            price=10.0,
            account=MagicMock(),
            portfolio=MagicMock()
        )
        assert result == False
        assert "整数倍" in reason


class TestStats:
    """统计模块测试"""

    def test_empty_summary(self):
        """测试空统计返回"""
        from backend.simulator.stats import Stats

        stats = Stats()
        summary = stats._empty_summary()

        assert summary['total_trades'] == 0
        assert summary['winning_trades'] == 0
        assert summary['losing_trades'] == 0
        assert summary['win_rate'] == 0
        assert summary['total_profit'] == 0

    def test_get_summary_no_trades(self):
        """测试无交易时的统计"""
        from backend.simulator.stats import Stats

        stats = Stats()
        summary = stats.get_summary()

        assert 'total_trades' in summary
        assert 'win_rate' in summary
        assert 'max_drawdown' in summary

    def test_get_fifo_buy_cost_no_batches(self):
        """测试无买入批次时的成本计算"""
        from backend.simulator.stats import Stats

        stats = Stats()
        cost = stats._get_fifo_buy_cost("NONEXISTENT", datetime.now().isoformat(), 100)
        assert cost == 0


class TestDatabase:
    """数据库模块测试"""

    def test_get_db_singleton(self):
        """测试数据库单例"""
        from backend.simulator.database import get_db

        db1 = get_db()
        db2 = get_db()
        assert db1 is db2

    def test_get_account(self):
        """测试获取账户"""
        from backend.simulator.database import get_db

        db = get_db()
        account = db.get_account()
        assert 'cash' in account
        assert 'initial_cash' in account

    def test_init_account(self):
        """测试初始化账户"""
        from backend.simulator.database import get_db

        db = get_db()
        db.init_account()  # 应该不会报错
        account = db.get_account()
        assert account['initial_cash'] == 20000

    def test_get_today_date(self):
        """测试获取今日日期"""
        from backend.simulator.database import get_db

        db = get_db()
        today = db.get_today_date()
        assert today == datetime.now().strftime("%Y-%m-%d")

    def test_get_pending_orders_empty(self):
        """测试空待成交委托"""
        from backend.simulator.database import get_db

        db = get_db()
        orders = db.get_pending_orders()
        assert isinstance(orders, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
