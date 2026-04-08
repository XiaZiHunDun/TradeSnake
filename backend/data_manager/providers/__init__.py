"""
数据源提供者模块
================

提供统一接口访问不同数据源:
- Tushare: 专业级数据API (2000积分)
- AkShare: 免费开源数据
- EastMoney: 东方财富
- Baostock: Baostock

使用示例:
    from data_manager.providers import get_tushare_provider

    provider = get_tushare_provider()
    stock_list = provider.get_stock_list()
    klines = provider.get_daily_kline('000001', '20240101', '20240401')
"""

from .base import BaseDataProvider, ProviderConfig
from .tushare import TushareProvider, get_tushare_provider, INTERFACE_COSTS

# 默认导出
__all__ = [
    'BaseDataProvider',
    'ProviderConfig',
    'TushareProvider',
    'get_tushare_provider',
    'INTERFACE_COSTS',
]
