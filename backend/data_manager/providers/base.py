"""
数据源提供者基类
====================
为不同数据源提供统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ProviderConfig:
    """提供者配置"""
    name: str
    enabled: bool = True
    priority: int = 100  # 优先级，数字越小越优先
    timeout: float = 30.0  # 超时时间（秒）


class BaseDataProvider(ABC):
    """数据源提供者基类"""

    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or ProviderConfig(name=self.__class__.__name__)

    @abstractmethod
    def get_stock_list(self, force_refresh: bool = False) -> List[Dict]:
        """获取股票列表"""
        pass

    @abstractmethod
    def get_market_data(self, codes: List[str]) -> List[Dict]:
        """获取实时行情"""
        pass

    @abstractmethod
    def get_daily_kline(self, code: str, start_date: str, end_date: str) -> List[Dict]:
        """获取日K线数据"""
        pass

    @abstractmethod
    def get_financial_data(self, code: str) -> Dict:
        """获取财务数据"""
        pass

    def health_check(self) -> bool:
        """健康检查"""
        return True

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'name': self.config.name,
            'enabled': self.config.enabled,
            'priority': self.config.priority,
        }
