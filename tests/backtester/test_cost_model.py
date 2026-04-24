import pytest
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.backtester.cost_model import CostModel, calculate_total_cost, CostResult


def test_buy_commission():
    """买入时收取佣金"""
    cost = calculate_total_cost(amount=100000, action='buy')
    assert cost.commission == 10.0  # 万1 = 10元
    assert cost.stamp_tax == 0
    assert cost.slippage == 100.0  # 0.1% = 100元


def test_sell_commission_and_stamp_tax():
    """卖出时收取佣金+印花税+滑点"""
    cost = calculate_total_cost(amount=100000, action='sell')
    assert cost.commission == 10.0  # 万1
    assert cost.stamp_tax == 50.0   # 千0.5 = 50元
    assert cost.slippage == 100.0   # 0.1%


def test_minimum_commission():
    """最低佣金5元"""
    cost = calculate_total_cost(amount=10000, action='buy')
    assert cost.commission == 5.0  # 万1=1元，但最低5元


def test_slippage_calculation():
    """滑点按金额比例计算"""
    cost = calculate_total_cost(amount=50000, action='buy')
    assert cost.slippage == 50.0  # 0.1% of 50000


def test_transfer_fee_shanghai():
    """沪市过户费"""
    cost = calculate_total_cost(amount=100000, action='buy', is_shanghai=True)
    assert cost.transfer_fee == 1.0  # 千0.01 = 1元


def test_transfer_fee_shenzhen():
    """深市免过户费"""
    cost = calculate_total_cost(amount=100000, action='buy', is_shanghai=False)
    assert cost.transfer_fee == 0.0


def test_total_cost_calculation():
    """总成本计算"""
    # 买入：佣金10 + 过户费1 + 滑点100 = 111
    cost = calculate_total_cost(amount=100000, action='buy', is_shanghai=True)
    assert cost.total_cost == 111.0

    # 卖出：佣金10 + 印花税50 + 过户费1 + 滑点100 = 161
    cost = calculate_total_cost(amount=100000, action='sell', is_shanghai=True)
    assert cost.total_cost == 161.0


def test_cost_result_total():
    """CostResult.total()方法"""
    cost = calculate_total_cost(amount=100000, action='buy')
    assert cost.total() == cost.total_cost