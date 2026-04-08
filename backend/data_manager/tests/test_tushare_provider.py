"""
Tushare Provider 单元测试
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_manager.providers.tushare import (
    TushareProvider,
    get_tushare_provider,
    INTERFACE_COSTS,
)


class TestTushareProvider:
    """Tushare数据源提供者测试"""

    def setup_method(self):
        """每个测试前执行"""
        self.provider = TushareProvider()

    def test_initialization(self):
        """测试初始化"""
        assert self.provider is not None
        assert self.provider.config.name == 'tushare'
        assert self.provider.config.enabled == True

    def test_to_ts_code(self):
        """测试股票代码转换"""
        # 上海市场
        assert self.provider._to_ts_code('600000') == '600000.SH'
        assert self.provider._to_ts_code('sh600000') == '600000.SH'

        # 深圳市场
        assert self.provider._to_ts_code('000001') == '000001.SZ'
        assert self.provider._to_ts_code('sz000001') == '000001.SZ'
        assert self.provider._to_ts_code('3') == '3.SZ'  # 创业板

        # 已经是Tushare格式
        assert self.provider._to_ts_code('600000.SH') == '600000.SH'

    def test_health_check(self):
        """测试健康检查"""
        result = self.provider.health_check()
        # 如果Tushare可用则返回True
        assert isinstance(result, bool)

    def test_get_stock_list(self):
        """测试获取股票列表"""
        stock_list = self.provider.get_stock_list()
        # 如果获取成功，应该有数据
        if stock_list:
            assert isinstance(stock_list, list)
            if len(stock_list) > 0:
                assert 'ts_code' in stock_list[0]
                assert 'symbol' in stock_list[0]

    def test_interface_costs(self):
        """测试接口消耗定义"""
        assert INTERFACE_COSTS['stock_basic'] == 0
        assert INTERFACE_COSTS['daily'] == 5
        assert INTERFACE_COSTS['daily_basic'] == 100
        assert INTERFACE_COSTS['income'] == 300

    def test_get_stats(self):
        """测试获取统计信息"""
        stats = self.provider.get_stats()
        assert 'name' in stats
        assert stats['name'] == 'tushare'
        assert 'tushare_stats' in stats


class TestTushareKline:
    """Tushare K线数据测试"""

    def setup_method(self):
        """每个测试前执行"""
        self.provider = TushareProvider()

    def test_get_daily_kline(self):
        """测试获取日K线"""
        # 获取平安银行最近60天的数据
        klines = self.provider.get_daily_kline(
            '000001',
            start_date='20240101',
            end_date='20240401'
        )

        if klines:  # 如果Tushare可用
            assert isinstance(klines, list)
            if len(klines) > 0:
                kline = klines[0]
                assert 'ts_code' in kline
                assert 'trade_date' in kline
                assert 'close' in kline
                assert 'volume' in kline

    def test_get_weekly_kline(self):
        """测试获取周K线"""
        klines = self.provider.get_weekly_kline(
            '000001',
            start_date='20230101',
            end_date='20240401'
        )

        if klines:
            assert isinstance(klines, list)

    def test_get_monthly_kline(self):
        """测试获取月K线"""
        klines = self.provider.get_monthly_kline(
            '000001',
            start_date='20220101',
            end_date='20240401'
        )

        if klines:
            assert isinstance(klines, list)


class TestTushareFinancial:
    """Tushare财务数据测试"""

    def setup_method(self):
        """每个测试前执行"""
        self.provider = TushareProvider()

    def test_get_financial_data(self):
        """测试获取财务数据"""
        data = self.provider.get_financial_data('000001')

        if data:  # 如果获取成功
            assert isinstance(data, dict)
            # 可能包含的字段
            possible_fields = ['revenue', 'oper_profit', 'net_profit', 'net_profit_growth']
            # 至少有一些字段
            has_any = any(field in data for field in possible_fields)
            assert has_any or len(data) == 0


class TestInterfaceCosts:
    """接口消耗测试"""

    def test_costs_defined(self):
        """测试各接口消耗已定义"""
        required_interfaces = [
            'stock_basic', 'daily', 'daily_basic',
            'income', 'balancesheet', 'cashflow'
        ]
        for interface in required_interfaces:
            assert interface in INTERFACE_COSTS

    def test_costs_reasonable(self):
        """测试消耗值合理"""
        for name, cost in INTERFACE_COSTS.items():
            assert cost >= 0
            assert cost <= 500  # 单次调用不超过500分


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
