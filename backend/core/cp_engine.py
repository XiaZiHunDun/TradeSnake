"""
战力计算引擎 - TradeSnake Core
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

# 战力公式权重
WEIGHTS = {
    'growth': 0.40,
    'value': 0.40,
    'momentum': 0.20
}


@dataclass
class StockCP:
    """单只股票战力数据"""
    code: str
    name: str
    price: float
    pe: float
    roe: float
    net_profit_growth: float
    revenue_growth: float
    change_pct: float

    # 计算得分
    growth_score: float = 0
    value_score: float = 0
    momentum_score: float = 0
    total_cp: float = 0

    # 风险评估
    risk_score: float = 0  # 风险分数（0-100，越高风险越大）

    def __post_init__(self):
        self.calculate_scores()

    def calculate_scores(self):
        """计算各因子原始分

        公式v13（微调版）：
        - 成长分：净利润增长和营收增长分别限制在合理范围后加权
        - 价值分：ROE + PE健康度综合评分
        - 趋势分：当日涨跌幅
        """
        # 净利润增长：限制在0-300%
        net_g = max(0, min(300, self.net_profit_growth))
        # 营收增长：限制在-50%到100%
        rev_g = max(-50, min(100, self.revenue_growth))
        # 复合增长率
        self.growth_score = net_g * 0.6 + rev_g * 0.4

        # 价值分：ROE（负ROE当0，ROE>25截断）+ PE健康度加成
        base_value = min(max(0, self.roe), 25)
        # PE健康度：PE在10-30之间得满分，其他情况递减
        pe_penalty = 0
        if self.pe > 0:
            if self.pe < 10:
                pe_penalty = 5  # 低PE加成
            elif self.pe > 50:
                pe_penalty = -5  # 高PE惩罚
            elif self.pe > 100:
                pe_penalty = -10  # 极高PE大惩罚
        self.value_score = max(0, base_value + pe_penalty)

        # 趋势分：当日涨跌幅（限制在-10到10之间）
        self.momentum_score = max(-10, min(10, self.change_pct))

        # 计算风险分数
        self.calculate_risk()

    def calculate_risk(self):
        """计算风险分数（0-100，越高风险越大）"""
        risk = 0

        # PE风险
        if self.pe < 0:
            risk += 30  # 亏损股票
        elif self.pe > 100:
            risk += 20  # 极高PE
        elif self.pe > 50:
            risk += 10  # 高PE
        elif self.pe < 5 and self.pe > 0:
            risk += 5   # 低PE可能有问题

        # ROE风险
        if self.roe < 0:
            risk += 25  # 负ROE
        elif self.roe < 5:
            risk += 10  # 低ROE

        # 增长风险
        if self.net_profit_growth < -50:
            risk += 15  # 大幅下降
        elif self.net_profit_growth < 0:
            risk += 5   # 小幅下降

        # 营收风险
        if self.revenue_growth < -30:
            risk += 10  # 营收大幅下降

        # 波动风险（涨跌幅）
        if abs(self.change_pct) > 8:
            risk += 15  # 高波动
        elif abs(self.change_pct) > 5:
            risk += 8   # 中等波动

        self.risk_score = min(100, risk)

    def get_risk_level(self) -> str:
        """获取风险等级"""
        if self.risk_score >= 60:
            return '高风险'
        elif self.risk_score >= 30:
            return '中等'
        else:
            return '较低'

    def to_dict(self) -> dict:
        return {
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'pe': self.pe,
            'roe': self.roe,
            'net_profit_growth': self.net_profit_growth,
            'revenue_growth': self.revenue_growth,
            'change_pct': self.change_pct,
            'growth_score': self.growth_score,
            'value_score': self.value_score,
            'momentum_score': self.momentum_score,
            'total_cp': self.total_cp,
            'risk_score': self.risk_score,
            'risk_level': self.get_risk_level()
        }


class CPEngine:
    """战力计算引擎"""

    def __init__(self):
        self.stocks: List[StockCP] = []

    def add_stock(self, stock: StockCP):
        """添加股票"""
        self.stocks.append(stock)

    def calculate_all(self) -> List[StockCP]:
        """计算所有股票的总战力"""
        if not self.stocks:
            return []

        # 找出各因子的范围，用于归一化
        growth_values = [s.growth_score for s in self.stocks]
        max_growth = max(growth_values)
        min_growth = min(growth_values)
        growth_range = max_growth - min_growth or 1

        value_values = [s.value_score for s in self.stocks]
        max_value = max(value_values)
        min_value = min(value_values)
        value_range = max_value - min_value or 1

        momentum_values = [s.momentum_score for s in self.stocks]
        max_momentum = max(momentum_values)
        min_momentum = min(momentum_values)
        momentum_range = max_momentum - min_momentum or 1

        # 归一化各因子到0-100范围，然后计算总战力
        for stock in self.stocks:
            # 归一化到0-100
            norm_growth = ((stock.growth_score - min_growth) / growth_range) * 100
            norm_value = ((stock.value_score - min_value) / value_range) * 100
            norm_momentum = ((stock.momentum_score - min_momentum) / momentum_range) * 100

            # 更新显示用分数（归一化后的0-100分数）
            stock.growth_score = norm_growth
            stock.value_score = norm_value
            stock.momentum_score = norm_momentum

            # 计算总战力
            stock.total_cp = (
                norm_growth * WEIGHTS['growth'] +
                norm_value * WEIGHTS['value'] +
                norm_momentum * WEIGHTS['momentum']
            )

        return self.stocks

    def get_top(self, n: int = 50) -> List[StockCP]:
        """获取战力榜TOP N"""
        sorted_stocks = sorted(self.stocks, key=lambda s: s.total_cp, reverse=True)
        return sorted_stocks[:n]

    def get_bottom(self, n: int = 10) -> List[StockCP]:
        """获取战力榜BOTTOM N（避雷区）"""
        sorted_stocks = sorted(self.stocks, key=lambda s: s.total_cp, reverse=True)
        return sorted_stocks[-n:]

    def get_by_code(self, code: str) -> Optional[StockCP]:
        """根据代码获取股票"""
        for stock in self.stocks:
            if stock.code == code:
                return stock
        return None

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame"""
        data = [s.to_dict() for s in self.stocks]
        df = pd.DataFrame(data)
        return df.sort_values('total_cp', ascending=False)


def create_stock_from_raw(
    code: str,
    name: str,
    price: float,
    pe: float,
    roe: float,
    net_profit_growth: float,
    revenue_growth: float,
    change_pct: float
) -> StockCP:
    """从原始数据创建StockCP对象"""
    return StockCP(
        code=code,
        name=name,
        price=price,
        pe=pe,
        roe=roe,
        net_profit_growth=net_profit_growth,
        revenue_growth=revenue_growth,
        change_pct=change_pct
    )
