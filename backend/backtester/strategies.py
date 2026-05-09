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
    cp_change: float = 0.0        # 战力日变化（昨日战力 - 今日战力）

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
            'growth': 0.50,
            'value': 0.00,
            'momentum': 0.28,
            'quality': 0.05
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


class RisingCPStrategy(Strategy):
    """战力上升策略 - 选战力正在上升的股票 v1.0

    改进点：基于验证结果（战力上升组平均涨幅+0.39% vs 下降组-0.10%），
    优先选择战力相比昨日上升的股票。
    """

    def __init__(self, n: int = 10, max_days: int = 5, min_cp_change: float = 0.0):
        """
        Args:
            n: 最大持仓数量
            max_days: 最大持仓天数
            min_cp_change: 最小战力变化阈值（只选战力变化大于此值的股票）
        """
        self.n = n
        self._max_days = max_days
        self.min_cp_change = min_cp_change

    @property
    def name(self) -> str:
        return f"战力上升TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """选战力上升的TOP N股票

        排序规则：
        1. 只选 cp_change > 0 的股票（战力上升）
        2. 按 cp_change 降序排列
        3. 取TOP N
        """
        n = rank or self.n

        # 过滤条件：非停牌，且战力上升
        rising_stocks = [
            (code, factor) for code, factor in stock_factors.items()
            if not factor.is_suspended and factor.cp_change > self.min_cp_change
        ]

        # 按战力变化降序排序
        rising_stocks.sort(key=lambda x: x[1].cp_change, reverse=True)

        return [code for code, _ in rising_stocks[:n]]


class HybridRisingStrategy(Strategy):
    """混合策略 - 综合战力绝对值和战力变化 v1.0

    综合排名 = 战力绝对值排名 * 0.4 + 战力变化排名 * 0.6
    战力变化权重更高（根据验证结果）
    """

    def __init__(self, n: int = 10, max_days: int = 5,
                 abs_weight: float = 0.4, change_weight: float = 0.6):
        """
        Args:
            n: 最大持仓数量
            max_days: 最大持仓天数
            abs_weight: 战力绝对值权重
            change_weight: 战力变化权重
        """
        self.n = n
        self._max_days = max_days
        self.abs_weight = abs_weight
        self.change_weight = change_weight

    @property
    def name(self) -> str:
        return f"混合策略TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """综合战力绝对值和战力变化选股"""
        n = rank or self.n

        valid_stocks = [
            factor for code, factor in stock_factors.items()
            if not factor.is_suspended
        ]

        if not valid_stocks:
            return []

        # 计算排名
        valid_stocks.sort(key=lambda x: x.total_cp, reverse=True)
        cp_ranks = {s.code: i for i, s in enumerate(valid_stocks)}

        valid_stocks.sort(key=lambda x: x.cp_change, reverse=True)
        change_ranks = {s.code: i for i, s in enumerate(valid_stocks)}

        # 计算综合排名
        scored = []
        for code, factor in stock_factors.items():
            if factor.is_suspended:
                continue

            cp_rank = cp_ranks.get(code, len(valid_stocks))
            change_rank = change_ranks.get(code, len(valid_stocks))

            # 归一化（越小排名越高）
            n_stocks = len(valid_stocks)
            normalized_cp_rank = cp_rank / n_stocks
            normalized_change_rank = change_rank / n_stocks

            composite_score = (
                normalized_cp_rank * self.abs_weight +
                normalized_change_rank * self.change_weight
            )
            # 综合分数越高越好（排名越低越好）
            scored.append((code, -composite_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [code for code, _ in scored[:n]]


class LowVolatilityStrategy(Strategy):
    """低波动策略 - 选波动率最低的股票 v1.0

    波动率低的股票更稳定，适合防御性投资。
    按 volatility_score 升序排序（最低波动 = 最高优先级）。
    """

    def __init__(self, n: int = 10, max_days: int = 5):
        """
        Args:
            n: 最大持仓数量
            max_days: 最大持仓天数
        """
        self.n = n
        self._max_days = max_days

    @property
    def name(self) -> str:
        return f"低波动TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """按波动率升序排序取TOP N（波动率越低越靠前）"""
        n = rank or self.n

        valid_stocks = {
            code: factor for code, factor in stock_factors.items()
            if not factor.is_suspended
        }

        # 使用 getattr 安全获取 volatility_score，缺失时当作最低优先级（0）
        sorted_stocks = sorted(
            valid_stocks.items(),
            key=lambda x: getattr(x[1], 'volatility_score', 0) or float('inf'),
            reverse=False  # 升序：低波动在前
        )
        return [code for code, _ in sorted_stocks[:n]]


class HighDividendStrategy(Strategy):
    """高股息策略 - 选股息率最高的股票 v1.0

    高股息股票通常是成熟稳定的公司，适合防御性投资。
    按 dividend_yield 降序排序（最高股息率 = 最高优先级）。
    """

    def __init__(self, n: int = 10, max_days: int = 5):
        """
        Args:
            n: 最大持仓数量
            max_days: 最大持仓天数
        """
        self.n = n
        self._max_days = max_days

    @property
    def name(self) -> str:
        return f"高股息TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """按股息率降序排序取TOP N（股息率越高越靠前）"""
        n = rank or self.n

        valid_stocks = {
            code: factor for code, factor in stock_factors.items()
            if not factor.is_suspended
        }

        # 使用 getattr 安全获取 dividend_yield，缺失时当作0（最低优先级）
        sorted_stocks = sorted(
            valid_stocks.items(),
            key=lambda x: getattr(x[1], 'dividend_yield', 0) or 0,
            reverse=True  # 降序：高股息在前
        )
        return [code for code, _ in sorted_stocks[:n]]


class ValueGrowthBalancedStrategy(MultiFactorStrategy):
    """价值成长平衡策略 - 多因子均衡配置 v1.0

    权重配置：growth=0.25, value=0.25, quality=0.3, momentum=0.2
    相比 MultiFactorStrategy 更注重质量和价值，成长和动量为辅助因子。
    """

    def __init__(self, n: int = 10, max_days: int = 5):
        """
        Args:
            n: 最大持仓数量
            max_days: 最大持仓天数
        """
        super().__init__(n=n, max_days=max_days, weights={
            'growth': 0.25,
            'value': 0.25,
            'quality': 0.3,
            'momentum': 0.2
        })

    @property
    def name(self) -> str:
        return f"价值成长平衡TOP{self.n}"


class RecommendationStrategy(Strategy):
    """推荐策略 - 使用 BuyAnalyzer.get_buy_signals() 选股 v1.0

    复用 recommender 的完整逻辑：
    - 融合预测（GainPrediction + ProbabilityPrediction）
    - Kelly 仓位计算
    - ST/涨跌停/停牌 过滤
    - 买入强度排序
    """

    def __init__(self, n: int = 10, max_days: int = 5,
                 principal: float = 1000000.0,
                 risk_preference: str = 'balanced'):
        self.n = n
        self._max_days = max_days
        self.principal = principal
        self.risk_preference = risk_preference

    @property
    def name(self) -> str:
        return f"推荐TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """使用 BuyAnalyzer.get_buy_signals() 选股

        Args:
            date: 信号日 (T日) - 用于获取对应日期的预测数据
            stock_factors: {code: StockFactor} 历史战力因子数据
            rank: 最大持仓数量

        Returns:
            目标持仓股票代码列表
        """
        from backend.recommender.buy_analyzer import BuyAnalyzer
        from backend.engine import StockCP

        n = rank or self.n

        # 将 StockFactor 转换为 StockCP
        stocks = []
        for code, factor in stock_factors.items():
            if factor.is_suspended:
                continue
            # StockCP 需要的字段
            stock = self._factor_to_stockcp(factor)
            stocks.append(stock)

        if not stocks:
            return []

        # 调用 BuyAnalyzer 获取买入信号
        signals = BuyAnalyzer.get_buy_signals(
            stocks=stocks,
            principal=self.principal,
            risk_preference=self.risk_preference,
            limit=n * 2  # 多取一些以便排序
        )

        # 按 buy_strength 降序，取前 n 个
        signals.sort(key=lambda x: x.get('buy_strength', 0), reverse=True)
        return [s['code'] for s in signals[:n]]

    def _factor_to_stockcp(self, factor: StockFactor) -> 'StockCP':
        """将 StockFactor 转换为 StockCP"""
        from backend.engine import StockCP
        return StockCP(
            code=factor.code,
            name=factor.name,
            price=factor.close,
            pe=0, roe=0, pb=0,
            net_profit_growth=0, revenue_growth=0,
            change_pct=factor.change_pct,
            growth_score=factor.growth_score,
            value_score=factor.value_score,
            momentum_score=factor.momentum_score,
            quality_score=factor.quality_score,
            total_cp=factor.total_cp,
            risk_score=50,  # 默认中等风险
            volatility_20d=0,
            is_suspended=factor.is_suspended,
            avg_daily_amount_20d=0,
        )
