import pytest
from backend.backtester.strategies import (
    LowVolatilityStrategy, HighDividendStrategy, ValueGrowthBalancedStrategy,
    StockFactor, MultiFactorStrategy
)


def test_value_growth_balanced_strategy():
    """ValueGrowthBalancedStrategy: balanced weights"""
    strategy = ValueGrowthBalancedStrategy(n=5)
    assert strategy.name == "价值成长平衡TOP5"
    assert strategy.weights == {'growth': 0.25, 'value': 0.25, 'quality': 0.3, 'momentum': 0.2}


def test_value_growth_balanced_select():
    """ValueGrowthBalancedStrategy: selects stocks"""
    strategy = ValueGrowthBalancedStrategy(n=3)
    factors = {
        '001': StockFactor(code='001', name='A', date='2024-01-01', close=10,
                          change_pct=0, total_cp=80, growth_score=80,
                          value_score=80, momentum_score=80, quality_score=80,
                          is_limit_up=False, is_limit_down=False, is_suspended=False),
        '002': StockFactor(code='002', name='B', date='2024-01-01', close=10,
                          change_pct=0, total_cp=60, growth_score=60,
                          value_score=60, momentum_score=60, quality_score=60,
                          is_limit_up=False, is_limit_down=False, is_suspended=False),
    }
    result = strategy.select_stocks('2024-01-01', factors, 2)
    assert len(result) == 2
    assert '001' in result  # Higher scores should be selected first


def test_low_volatility_strategy_missing_field():
    """LowVolatilityStrategy: handles missing volatility_score gracefully"""
    strategy = LowVolatilityStrategy(n=2)
    factors = {
        '001': StockFactor(code='001', name='A', date='2024-01-01', close=10,
                          change_pct=0, total_cp=80, growth_score=80,
                          value_score=80, momentum_score=80, quality_score=80,
                          is_limit_up=False, is_limit_down=False, is_suspended=False),
    }
    # Should not crash even without volatility_score
    result = strategy.select_stocks('2024-01-01', factors, 2)
    assert '001' in result  # Falls back to treating as lowest priority


def test_low_volatility_strategy_with_volatility():
    """LowVolatilityStrategy: selects lowest volatility stocks"""
    strategy = LowVolatilityStrategy(n=2)

    factors = {
        '001': StockFactor(code='001', name='A', date='2024-01-01', close=10,
                          change_pct=0, total_cp=80, growth_score=80,
                          value_score=80, momentum_score=80, quality_score=80,
                          is_limit_up=False, is_limit_down=False, is_suspended=False),
        '002': StockFactor(code='002', name='B', date='2024-01-01', close=10,
                          change_pct=0, total_cp=80, growth_score=80,
                          value_score=80, momentum_score=80, quality_score=80,
                          is_limit_up=False, is_limit_down=False, is_suspended=False),
        '003': StockFactor(code='003', name='C', date='2024-01-01', close=10,
                          change_pct=0, total_cp=80, growth_score=80,
                          value_score=80, momentum_score=80, quality_score=80,
                          is_limit_up=False, is_limit_down=False, is_suspended=False),
    }
    # Set volatility_score after creation
    factors['001'].volatility_score = 30
    factors['002'].volatility_score = 10
    factors['003'].volatility_score = 20

    result = strategy.select_stocks('2024-01-01', factors, 2)
    assert len(result) == 2
    assert result[0] == '002'  # Lowest volatility (10) should be first
    assert result[1] == '003'  # Second lowest (20)


def test_high_dividend_strategy_missing_field():
    """HighDividendStrategy: handles missing dividend_yield gracefully"""
    strategy = HighDividendStrategy(n=2)
    factors = {
        '001': StockFactor(code='001', name='A', date='2024-01-01', close=10,
                          change_pct=0, total_cp=80, growth_score=80,
                          value_score=80, momentum_score=80, quality_score=80,
                          is_limit_up=False, is_limit_down=False, is_suspended=False),
    }
    # Should not crash even without dividend_yield
    result = strategy.select_stocks('2024-01-01', factors, 2)
    assert '001' in result


def test_high_dividend_strategy_with_yield():
    """HighDividendStrategy: selects highest dividend yield stocks"""
    strategy = HighDividendStrategy(n=2)

    factors = {
        '001': StockFactor(code='001', name='A', date='2024-01-01', close=10,
                          change_pct=0, total_cp=80, growth_score=80,
                          value_score=80, momentum_score=80, quality_score=80,
                          is_limit_up=False, is_limit_down=False, is_suspended=False),
        '002': StockFactor(code='002', name='B', date='2024-01-01', close=10,
                          change_pct=0, total_cp=80, growth_score=80,
                          value_score=80, momentum_score=80, quality_score=80,
                          is_limit_up=False, is_limit_down=False, is_suspended=False),
        '003': StockFactor(code='003', name='C', date='2024-01-01', close=10,
                          change_pct=0, total_cp=80, growth_score=80,
                          value_score=80, momentum_score=80, quality_score=80,
                          is_limit_up=False, is_limit_down=False, is_suspended=False),
    }
    # Set dividend_yield after creation
    factors['001'].dividend_yield = 2.5
    factors['002'].dividend_yield = 5.0
    factors['003'].dividend_yield = 3.5

    result = strategy.select_stocks('2024-01-01', factors, 2)
    assert len(result) == 2
    assert result[0] == '002'  # Highest dividend (5.0%) should be first
    assert result[1] == '003'  # Second highest (3.5%)


def test_value_growth_balanced_vs_multi_factor():
    """ValueGrowthBalancedStrategy: different weights from MultiFactorStrategy"""
    balanced = ValueGrowthBalancedStrategy(n=5)
    multi = MultiFactorStrategy(n=5)

    # Check that weights are different
    assert balanced.weights != multi.weights
    # Balanced strategy weights
    assert balanced.weights == {'growth': 0.25, 'value': 0.25, 'quality': 0.3, 'momentum': 0.2}
    # MultiFactor default weights
    assert multi.weights == {'growth': 0.3, 'value': 0.25, 'momentum': 0.25, 'quality': 0.2}
