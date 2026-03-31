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
        assert stock.quality_score >= 0  # v14新增质量分
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
        # 验证v14新增字段
        assert 'quality_score' in d
        assert 'growth_score' in d
        assert 'value_score' in d
        assert 'momentum_score' in d
        assert 'peg' in d


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


class TestCPEngineAdvanced:
    """测试CPEngine高级功能"""

    def test_get_by_code(self):
        """测试根据代码获取股票"""
        engine = CPEngine()
        stocks = [
            StockCP('600519', '贵州茅台', 1800.0, 45.0, 30.0, 20.0, 15.0, 2.5),
            StockCP('000858', '五粮液', 200.0, 30.0, 25.0, 25.0, 20.0, 3.0),
            StockCP('600036', '招商银行', 40.0, 10.0, 18.0, 15.0, 10.0, 1.0),
        ]
        for stock in stocks:
            engine.add_stock(stock)

        found = engine.get_by_code('000858')
        assert found is not None
        assert found.name == '五粮液'

        not_found = engine.get_by_code('999999')
        assert not_found is None

    def test_empty_engine(self):
        """测试空引擎"""
        engine = CPEngine()
        assert len(engine.stocks) == 0
        result = engine.calculate_all()
        assert result == []

        top = engine.get_top(5)
        assert top == []
        bottom = engine.get_bottom(3)
        assert bottom == []
        assert engine.get_by_code('600519') is None

    def test_single_stock(self):
        """测试单只股票"""
        engine = CPEngine()
        stock = StockCP('600519', '贵州茅台', 1800.0, 45.0, 30.0, 20.0, 15.0, 2.5)
        engine.add_stock(stock)
        engine.calculate_all()

        assert len(engine.get_top(5)) == 1
        assert len(engine.get_bottom(3)) == 1

    def test_to_dataframe(self):
        """测试转换为DataFrame"""
        engine = CPEngine()
        stocks = [
            StockCP('600519', '贵州茅台', 1800.0, 45.0, 30.0, 20.0, 15.0, 2.5),
            StockCP('000858', '五粮液', 200.0, 30.0, 25.0, 25.0, 20.0, 3.0),
        ]
        for stock in stocks:
            engine.add_stock(stock)

        engine.calculate_all()
        df = engine.to_dataframe()

        assert len(df) == 2
        assert 'total_cp' in df.columns
        assert 'code' in df.columns
        # 验证排序
        assert df.iloc[0]['total_cp'] >= df.iloc[1]['total_cp']


class TestStockCPQualityScore:
    """测试质量分数计算"""

    def test_high_quality_stock(self):
        """测试高质量股票（高现金流+高毛利+低负债）"""
        stock = StockCP(
            code='600519',
            name='贵州茅台',
            price=1800.0,
            pe=45.0,
            roe=30.0,
            net_profit_growth=20.0,
            revenue_growth=15.0,
            change_pct=2.5,
            cashflow=100.0,
            gross_margin=90.0,
            debt_ratio=30.0
        )

        assert stock.quality_score > 0
        assert stock.cashflow > 0
        assert stock.gross_margin > 30

    def test_low_quality_stock(self):
        """测试低质量股票（低现金流+负毛利+高负债）"""
        stock = StockCP(
            code='600519',
            name='问题股',
            price=100.0,
            pe=50.0,
            roe=5.0,
            net_profit_growth=-10.0,
            revenue_growth=-5.0,
            change_pct=5.0,
            cashflow=-10.0,
            gross_margin=-5.0,
            debt_ratio=85.0
        )

        assert stock.quality_score < 20

    def test_peg_calculation(self):
        """测试PEG计算"""
        # PEG = PE / Growth
        stock = StockCP(
            code='600519',
            name='贵州茅台',
            price=1800.0,
            pe=30.0,
            roe=30.0,
            net_profit_growth=30.0,  # 30%增长
            revenue_growth=15.0,
            change_pct=2.5
        )

        assert stock.peg > 0
        assert stock.peg == 1.0  # PEG = 30/30

    def test_negative_pe_stock(self):
        """测试负PE（亏损股）"""
        stock = StockCP(
            code='600519',
            name='亏损股',
            price=10.0,
            pe=-5.0,
            roe=-10.0,
            net_profit_growth=-50.0,
            revenue_growth=-20.0,
            change_pct=5.0
        )

        assert stock.pe < 0
        assert stock.risk_score > 30  # 应该有较高风险

    def test_quality_score_components(self):
        """测试质量分各组成部分"""
        # 测试现金流得分
        stock_positive_cf = StockCP(
            code='1', name='正现金流', price=100.0,
            pe=20.0, roe=20.0, net_profit_growth=20.0,
            revenue_growth=10.0, change_pct=1.0,
            cashflow=50.0, gross_margin=30.0, debt_ratio=40.0
        )
        assert stock_positive_cf.quality_score > 0

        # 测试负现金流但正ROE的情况（应扣分）
        stock_negative_cf = StockCP(
            code='2', name='负现金流', price=100.0,
            pe=20.0, roe=20.0, net_profit_growth=20.0,
            revenue_growth=10.0, change_pct=1.0,
            cashflow=-10.0, gross_margin=30.0, debt_ratio=40.0
        )
        # 负现金流应该导致质量分较低
        assert stock_negative_cf.quality_score < stock_positive_cf.quality_score

    def test_quality_score_margins(self):
        """测试毛利率对质量分的影响"""
        stock_high_margin = StockCP(
            code='1', name='高毛利', price=100.0,
            pe=20.0, roe=20.0, net_profit_growth=20.0,
            revenue_growth=10.0, change_pct=1.0,
            cashflow=50.0, gross_margin=50.0, debt_ratio=40.0
        )
        stock_low_margin = StockCP(
            code='2', name='低毛利', price=100.0,
            pe=20.0, roe=20.0, net_profit_growth=20.0,
            revenue_growth=10.0, change_pct=1.0,
            cashflow=50.0, gross_margin=10.0, debt_ratio=40.0
        )
        # 高毛利应该有更高的质量分
        assert stock_high_margin.quality_score > stock_low_margin.quality_score


class TestRiskLevels:
    """测试风险等级"""

    def test_risk_levels(self):
        """测试各风险等级"""
        # 高风险
        high_risk = StockCP(
            code='1', name='高风险', price=100.0,
            pe=150.0, roe=-5.0, net_profit_growth=-60.0,
            revenue_growth=-40.0, change_pct=10.0
        )
        assert high_risk.get_risk_level() == '高风险'
        assert high_risk.risk_score >= 60

        # 中等风险 - 需要更高的波动或PE来触发
        mid_risk = StockCP(
            code='2', name='中等风险', price=100.0,
            pe=60.0, roe=8.0, net_profit_growth=-20.0,
            revenue_growth=-10.0, change_pct=6.0
        )
        assert mid_risk.get_risk_level() in ['中等', '较低']
        assert 20 < mid_risk.risk_score < 60

        # 较低风险
        low_risk = StockCP(
            code='3', name='较低风险', price=100.0,
            pe=15.0, roe=15.0, net_profit_growth=15.0,
            revenue_growth=10.0, change_pct=1.0
        )
        assert low_risk.get_risk_level() in ['较低', '中等']
        assert low_risk.risk_score < 40


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
