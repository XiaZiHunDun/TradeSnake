import pytest
from backend.backtester.strategy_comparator import StrategyComparator, BacktestConfig, StrategyComparisonResult

def test_backtest_config_defaults():
    config = BacktestConfig()
    assert config.top_n == 6
    assert config.stop_loss == -0.10
    assert config.max_holding_days == 5
    assert config.initial_capital == 1000000

def test_comparator_init():
    comparator = StrategyComparator()
    assert len(comparator.strategies) >= 7  # 7 strategies
    assert 'TopNStrategy' in comparator.strategies
    assert 'MultiFactorStrategy' in comparator.strategies

def test_get_best_strategy():
    comparator = StrategyComparator()
    results = {
        'StrategyA': StrategyComparisonResult(
            strategy_name='StrategyA', annual_return=15.0, max_drawdown=10.0,
            excess_return=5.0, information_ratio=0.5, sharpe_ratio=1.2,
            calmar_ratio=1.5, win_rate=60.0, profit_loss_ratio=1.8, total_trades=100
        ),
        'StrategyB': StrategyComparisonResult(
            strategy_name='StrategyB', annual_return=12.0, max_drawdown=8.0,
            excess_return=2.0, information_ratio=0.3, sharpe_ratio=1.0,
            calmar_ratio=1.5, win_rate=55.0, profit_loss_ratio=1.5, total_trades=100
        ),
    }
    best = comparator.get_best_strategy(results)
    assert best == 'StrategyA'  # Higher score
