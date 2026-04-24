import pytest
import numpy as np
from backend.backtester.factor_attributor import FactorAttributor, ICResult

def test_ic_calculation():
    attr = FactorAttributor()
    factors = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    returns = np.array([1.1, 2.2, 3.3, 4.4, 5.5])
    ic, p_value = attr._compute_ic(factors, returns)
    assert ic > 0.9  # 高度相关

def test_group_returns():
    attr = FactorAttributor(n_groups=3)
    # 模拟分组收益
    groups = {
        'Q1': ([1.0, 1.2], [2.0, 2.1]),
        'Q2': ([3.0, 3.2], [4.0, 4.1]),
        'Q3': ([5.0, 5.2], [6.0, 6.1])
    }
    result = attr._check_monotonicity([
        type('G', (), {'group': 'Q1', 'avg_return': 2.05})(),
        type('G', (), {'group': 'Q2', 'avg_return': 4.05})(),
        type('G', (), {'group': 'Q3', 'avg_return': 6.05})()
    ])
    assert result['monotonic'] == True