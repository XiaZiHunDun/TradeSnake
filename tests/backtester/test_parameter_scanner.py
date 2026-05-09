import pytest
from backend.backtester.parameter_scanner import ParameterScanner, ParameterSpace, ScanResult

def test_parameter_space():
    space = ParameterSpace()
    assert space.stop_loss_range == [-0.15, -0.10, -0.08, -0.07, -0.05]
    assert space.max_holding_days_range == [3, 5, 7, 10]
    assert space.top_n_range == [5, 6, 8]

def test_parameter_scanner_init():
    scanner = ParameterScanner()
    assert scanner.n_trials == 30
    assert scanner.comparator is not None

def test_random_sample_params():
    scanner = ParameterScanner()
    params = scanner._random_sample_params()
    assert 'stop_loss' in params
    assert 'max_holding_days' in params
    assert 'top_n' in params
    assert params['stop_loss'] in scanner.space.stop_loss_range
    assert params['max_holding_days'] in scanner.space.max_holding_days_range