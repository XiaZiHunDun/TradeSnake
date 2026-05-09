import pytest


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "integration: requires real data or network")
