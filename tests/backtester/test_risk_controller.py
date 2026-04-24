import pytest
from backend.backtester.risk_controller import RiskController, RiskConfig

def test_default_config():
    config = RiskConfig()
    assert config.stop_loss == -0.10
    assert config.max_daily_loss == -0.03
    assert config.consecutive_loss_days == 3
    assert config.market_filter_down == -0.02
    assert config.market_filter_exit == -0.04

def test_risk_controller_state():
    controller = RiskController()
    assert controller.is_normal()
    assert controller.consecutive_loss_count == 0

def test_market_filter_reduce():
    controller = RiskController()
    # 大盘跌-3%，应减半持仓
    # reduce zone is: -0.04 < x <= -0.02
    action = controller.check_market_filter(-0.03)
    assert action == 'reduce'

def test_market_filter_exit():
    controller = RiskController()
    # 大盘跌-5%，应空仓
    action = controller.check_market_filter(-5.0)
    assert action == 'exit'

def test_consecutive_loss_protection():
    controller = RiskController()
    # 连续3日亏损后触发保护
    for _ in range(3):
        controller.record_daily_return(-0.01)
    assert controller.should_protect()

def test_stop_loss_record():
    controller = RiskController()
    controller.record_trade_result(profit_pct=-0.12)
    assert controller.total_loss >= 0.12

def test_should_stop_loss():
    controller = RiskController()
    # 跌幅达到止损线
    assert controller.should_stop_loss(-0.10) is True
    # 跌幅未达止损线
    assert controller.should_stop_loss(-0.05) is False
    # 正收益不触发止损
    assert controller.should_stop_loss(0.05) is False

def test_reset():
    controller = RiskController()
    # 设置一些状态
    controller.record_daily_return(-0.01)
    controller.record_daily_return(-0.02)
    controller.activate_protection()
    controller.record_trade_result(profit_pct=-0.05)
    assert controller.consecutive_loss_count > 0
    assert controller.protection_active is True
    assert controller.total_loss > 0
    # 重置
    controller.reset()
    assert controller.consecutive_loss_count == 0
    assert controller.daily_returns == []
    assert controller.total_loss == 0.0
    assert controller.protection_active is False
    assert controller.protection_remaining_days == 0