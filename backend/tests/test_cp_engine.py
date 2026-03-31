"""
战力引擎单元测试
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cp_engine import StockCP, CPEngine, create_stock_from_raw


class TestStockCP:
    """测试StockCP类"""

    def test_stock_creation(self):
        """测试股票创建"""
        stock = StockCP(
            code='600519',
            name='贵州茅台',
            price=1800.0,
            pe=45.0,
            roe=30.0,
            net_profit_growth=20.0,
            revenue_growth=15.0,
            change_pct=2.5
        )

        assert stock.code == '600519'
        assert stock.name == '贵州茅台'
        assert stock.price == 1800.0

    def test_scores_calculation(self):
        """测试分数计算"""
        stock = StockCP(
            code='600519',
            name='贵州茅台',
            price=1800.0,
            pe=45.0,
            roe=30.0,
            net_profit_growth=20.0,
            revenue_growth=15.0,
            change_pct=2.5
        )

        # 检查各分数是否已计算
        assert stock.growth_score >= 0
        assert stock.value_score >= 0
        assert stock.momentum_score >= 0
        assert stock.total_cp >= 0

    def test_risk_calculation(self):
        """测试风险分数计算"""
        # 高风险股票（高PE、负ROE）
        high_risk = StockCP(
            code='600519',
            name='高风险股',
            price=100.0,
            pe=150.0,  # 极高PE
            roe=-10.0,  # 负ROE
            net_profit_growth=-60.0,  # 大幅下降
            revenue_growth=-40.0,
            change_pct=10.0  # 高波动
        )

        # 低风险股票（正常PE、正ROE）
        low_risk = StockCP(
            code='600000',
            name='低风险股',
            price=10.0,
            pe=15.0,  # 正常PE
            roe=15.0,  # 正ROE
            net_profit_growth=20.0,  # 正增长
            revenue_growth=10.0,
            change_pct=1.0  # 低波动
        )

        assert high_risk.risk_score > low_risk.risk_score
        assert high_risk.get_risk_level() == '高风险'
        assert low_risk.get_risk_level() in ['较低', '中等']

    def test_to_dict(self):
        """测试转换为字典"""
        stock = StockCP(
            code='600519',
            name='贵州茅台',
            price=1800.0,
            pe=45.0,
            roe=30.0,
            net_profit_growth=20.0,
            revenue_growth=15.0,
            change_pct=2.5,
            market_cap=500.0,
            high=1850.0,
            low=1750.0,
            data_quality='high'
        )

        d = stock.to_dict()
        assert 'code' in d
        assert 'name' in d
        assert 'total_cp' in d
        assert 'risk_score' in d
        assert 'risk_level' in d
        assert 'market_cap' in d
        assert d['market_cap'] == 500.0
        assert d['high'] == 1850.0
        assert d['low'] == 1750.0
        assert d['data_quality'] == 'high'


class TestCPEngine:
    """测试CPEngine类"""

    def test_add_stock(self):
        """测试添加股票"""
        engine = CPEngine()
        stock = StockCP(
            code='600519',
            name='贵州茅台',
            price=1800.0,
            pe=45.0,
            roe=30.0,
            net_profit_growth=20.0,
            revenue_growth=15.0,
            change_pct=2.5
        )

        engine.add_stock(stock)
        assert len(engine.stocks) == 1

    def test_calculate_all(self):
        """测试计算所有股票"""
        engine = CPEngine()

        # 添加多只股票
        stocks = [
            StockCP('600519', '贵州茅台', 1800.0, 45.0, 30.0, 20.0, 15.0, 2.5),
            StockCP('000858', '五粮液', 200.0, 30.0, 25.0, 25.0, 20.0, 3.0),
            StockCP('600036', '招商银行', 40.0, 10.0, 18.0, 15.0, 10.0, 1.0),
        ]

        for stock in stocks:
            engine.add_stock(stock)

        engine.calculate_all()

        # 检查所有股票的total_cp是否已计算
        for stock in engine.stocks:
            assert stock.total_cp >= 0

        # 检查get_top返回的是正确的排序
        top_stocks = engine.get_top(3)
        for i in range(len(top_stocks) - 1):
            assert top_stocks[i].total_cp >= top_stocks[i+1].total_cp

    def test_get_top(self):
        """测试获取TOP N"""
        engine = CPEngine()

        # 添加多只股票
        for i in range(10):
            stock = StockCP(
                code=f'60000{i}',
                name=f'股票{i}',
                price=10.0 + i,
                pe=10.0 + i,
                roe=10.0 + i,
                net_profit_growth=10.0 + i,
                revenue_growth=10.0 + i,
                change_pct=1.0 + i
            )
            engine.add_stock(stock)

        engine.calculate_all()
        top5 = engine.get_top(5)

        assert len(top5) == 5
        # 检查是否按战力降序排列
        for i in range(len(top5) - 1):
            assert top5[i].total_cp >= top5[i+1].total_cp

    def test_get_bottom(self):
        """测试获取BOTTOM N"""
        engine = CPEngine()

        for i in range(10):
            stock = StockCP(
                code=f'60000{i}',
                name=f'股票{i}',
                price=10.0 + i,
                pe=10.0 + i,
                roe=10.0 + i,
                net_profit_growth=10.0 + i,
                revenue_growth=10.0 + i,
                change_pct=1.0 + i
            )
            engine.add_stock(stock)

        engine.calculate_all()
        bottom3 = engine.get_bottom(3)

        assert len(bottom3) == 3


class TestCreateStockFromRaw:
    """测试create_stock_from_raw函数"""

    def test_create_stock(self):
        """测试从原始数据创建股票"""
        data = {
            'code': '600519',
            'name': '贵州茅台',
            'price': 1800.0,
            'pe': 45.0,
            'roe': 30.0,
            'net_profit_growth': 20.0,
            'revenue_growth': 15.0,
            'change_pct': 2.5
        }

        stock = create_stock_from_raw(**data)

        assert stock.code == '600519'
        assert stock.name == '贵州茅台'
        assert stock.price == 1800.0
        # 创建时component scores已计算
        assert stock.growth_score > 0
        assert stock.value_score > 0

    def test_create_stock_with_new_fields(self):
        """测试从原始数据创建股票（含新字段）"""
        data = {
            'code': '600519',
            'name': '贵州茅台',
            'price': 1800.0,
            'pe': 45.0,
            'roe': 30.0,
            'net_profit_growth': 20.0,
            'revenue_growth': 15.0,
            'change_pct': 2.5,
            'market_cap': 500.0,
            'high': 1850.0,
            'low': 1750.0,
            'data_quality': 'high',
            'dividend_yield': 1.5,
            'gross_margin': 90.0,
            'cashflow': 100.0,
            'debt_ratio': 30.0
        }

        stock = create_stock_from_raw(**data)

        assert stock.code == '600519'
        assert stock.market_cap == 500.0
        assert stock.high == 1850.0
        assert stock.low == 1750.0
        assert stock.data_quality == 'high'
        assert stock.dividend_yield == 1.5
        assert stock.gross_margin == 90.0
        assert stock.cashflow == 100.0
        assert stock.debt_ratio == 30.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
