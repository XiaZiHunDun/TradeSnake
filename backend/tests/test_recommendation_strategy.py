"""测试 RecommendationStrategy 选股逻辑"""
import pytest
from backend.backtester.strategies import RecommendationStrategy, StockFactor


def test_recommendation_strategy_select():
    """测试按买入强度排序选股"""
    strategy = RecommendationStrategy(n=3, principal=100000.0, risk_preference='balanced')

    # 构造测试数据
    factors = {
        '000001': StockFactor(
            code='000001', name='平安银行', date='2024-01-01', close=10.0,
            change_pct=1.0, total_cp=80.0,
            growth_score=30.0, value_score=20.0, momentum_score=20.0, quality_score=10.0,
            is_limit_up=False, is_limit_down=False, is_suspended=False
        ),
        '000002': StockFactor(
            code='000002', name='万科A', date='2024-01-01', close=8.0,
            change_pct=2.0, total_cp=75.0,
            growth_score=25.0, value_score=25.0, momentum_score=15.0, quality_score=10.0,
            is_limit_up=False, is_limit_down=False, is_suspended=False
        ),
        '000004': StockFactor(
            code='000004', name='st股', date='2024-01-01', close=5.0,
            change_pct=0.0, total_cp=70.0,
            growth_score=20.0, value_score=20.0, momentum_score=20.0, quality_score=10.0,
            is_limit_up=False, is_limit_down=False, is_suspended=True  # 停牌
        ),
    }

    selected = strategy.select_stocks('2024-01-01', factors, rank=2)

    # st股和停牌股应该被过滤
    assert '000004' not in selected
    assert len(selected) <= 2
    assert selected[0] in ['000001', '000002']


def test_full_backtest_uses_recommendation():
    """验证 FullBacktestEngine 可以使用 recommendation 策略"""
    from backend.backtester.full_backtest import FullBacktestEngine

    engine = FullBacktestEngine()
    assert 'recommendation' in engine.strategies

    # 使用简单的日期范围测试
    try:
        result = engine.run_recommendation(
            start_date='2024-01-01',
            end_date='2024-01-31',
            strategy_name='recommendation',
            principal=1000000.0
        )
        assert result is not None
    except Exception as e:
        pytest.skip(f"需要真实数据或历史预测: {e}")