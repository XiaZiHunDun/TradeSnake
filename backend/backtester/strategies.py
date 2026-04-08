"""
策略定义 - Strategy Definitions v19.3
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Callable, Optional


@dataclass
class StockFactor:
    """股票因子数据"""
    code: str
    name: str
    date: str                      # 日期
    close: float                  # 收盘价
    change_pct: float             # 涨跌幅%
    total_cp: float               # 战力总分
    growth_score: float           # 成长分
    value_score: float            # 价值分
    momentum_score: float          # 动量分
    quality_score: float          # 质量分
    is_limit_up: bool             # 是否涨停
    is_limit_down: bool           # 是否跌停
    is_suspended: bool            # 是否停牌

    @classmethod
    def from_dict(cls, data: Dict) -> 'StockFactor':
        """从字典创建 StockFactor"""
        return cls(
            code=data.get('code', ''),
            name=data.get('name', ''),
            date=data.get('date', ''),
            close=data.get('close', 0),
            change_pct=data.get('change_pct', 0),
            total_cp=data.get('total_cp', 0),
            growth_score=data.get('growth_score', 0),
            value_score=data.get('value_score', 0),
            momentum_score=data.get('momentum_score', 0),
            quality_score=data.get('quality_score', 0),
            is_limit_up=data.get('is_limit_up', False),
            is_limit_down=data.get('is_limit_down', False),
            is_suspended=data.get('is_suspended', False),
        )


class Strategy(ABC):
    """策略基类 v19.3"""

    @abstractmethod
    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int) -> List[str]:
        """根据日期和股票因子数据返回应持仓的股票代码

        Args:
            date: 信号日 (T日)
            stock_factors: {code: StockFactor} 历史战力因子数据
            rank: 最大持仓数量

        Returns:
            目标持仓股票代码列表
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    def max_position_days(self) -> int:
        """最大持仓天数（交易日），默认5天"""
        return 5

    @property
    def max_positions(self) -> int:
        """最大持仓数量，默认10只"""
        return 10


class TopNStrategy(Strategy):
    """战力榜TOP N策略"""

    def __init__(self, n: int = 10, max_days: int = 5):
        self.n = n
        self._max_days = max_days

    @property
    def name(self) -> str:
        return f"战力TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """按战力总分排序取TOP N"""
        n = rank or self.n
        # 过滤停牌股票
        valid_stocks = {
            code: factor for code, factor in stock_factors.items()
            if not factor.is_suspended
        }
        # 按战力排序
        sorted_stocks = sorted(
            valid_stocks.items(),
            key=lambda x: x[1].total_cp,
            reverse=True
        )
        return [code for code, _ in sorted_stocks[:n]]


class ValueStrategy(Strategy):
    """价值型策略 - 按价值分排序"""

    def __init__(self, n: int = 10, max_days: int = 5):
        self.n = n
        self._max_days = max_days

    @property
    def name(self) -> str:
        return f"价值TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """按价值分排序取TOP N"""
        n = rank or self.n
        valid_stocks = {
            code: factor for code, factor in stock_factors.items()
            if not factor.is_suspended
        }
        sorted_stocks = sorted(
            valid_stocks.items(),
            key=lambda x: x[1].value_score,
            reverse=True
        )
        return [code for code, _ in sorted_stocks[:n]]


class GrowthStrategy(Strategy):
    """成长型策略 - 按成长分排序"""

    def __init__(self, n: int = 10, max_days: int = 5):
        self.n = n
        self._max_days = max_days

    @property
    def name(self) -> str:
        return f"成长TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """按成长分排序取TOP N"""
        n = rank or self.n
        valid_stocks = {
            code: factor for code, factor in stock_factors.items()
            if not factor.is_suspended
        }
        sorted_stocks = sorted(
            valid_stocks.items(),
            key=lambda x: x[1].growth_score,
            reverse=True
        )
        return [code for code, _ in sorted_stocks[:n]]


class MomentumStrategy(Strategy):
    """动量策略 - 按动量分排序"""

    def __init__(self, n: int = 10, max_days: int = 5):
        self.n = n
        self._max_days = max_days

    @property
    def name(self) -> str:
        return f"动量TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """按动量分排序取TOP N"""
        n = rank or self.n
        valid_stocks = {
            code: factor for code, factor in stock_factors.items()
            if not factor.is_suspended
        }
        sorted_stocks = sorted(
            valid_stocks.items(),
            key=lambda x: x[1].momentum_score,
            reverse=True
        )
        return [code for code, _ in sorted_stocks[:n]]


class CustomStrategy(Strategy):
    """自定义策略"""

    def __init__(self, select_func: Callable, name: str = "自定义策略",
                 n: int = 10, max_days: int = 5):
        """自定义策略构造函数

        Args:
            select_func: 选股函数，签名 (date: str, stock_factors: Dict[str, StockFactor], rank: int) -> List[str]
            name: 策略名称
            n: 最大持仓数量
            max_days: 最大持仓天数
        """
        self._select_func = select_func
        self._name = name
        self.n = n
        self._max_days = max_days

    @property
    def name(self) -> str:
        return self._name

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        return self._select_func(date, stock_factors, rank or self.n)


class MultiFactorStrategy(Strategy):
    """多因子融合策略"""

    def __init__(self, n: int = 10, max_days: int = 5,
                 weights: Optional[Dict[str, float]] = None):
        """
        多因子融合策略

        Args:
            n: 最大持仓数量
            max_days: 最大持仓天数
            weights: 因子权重，如 {'growth': 0.4, 'value': 0.3, 'momentum': 0.2, 'quality': 0.1}
        """
        self.n = n
        self._max_days = max_days
        self.weights = weights or {
            'growth': 0.3,
            'value': 0.25,
            'momentum': 0.25,
            'quality': 0.2
        }

    @property
    def name(self) -> str:
        return f"多因子TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """多因子加权评分后取TOP N"""
        n = rank or self.n

        # 计算综合评分
        scored = []
        for code, factor in stock_factors.items():
            if factor.is_suspended:
                continue

            composite_score = (
                factor.growth_score * self.weights.get('growth', 0) +
                factor.value_score * self.weights.get('value', 0) +
                factor.momentum_score * self.weights.get('momentum', 0) +
                factor.quality_score * self.weights.get('quality', 0)
            )
            scored.append((code, composite_score))

        # 按综合评分排序
        scored.sort(key=lambda x: x[1], reverse=True)
        return [code for code, _ in scored[:n]]
