"""
战力计算引擎 - Combat Power Engine
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from .constants import WEIGHTS, TRADE_COST, SELL_COST_RATE, BUY_COST_RATE, TOTAL_TRADE_COST_RATE, MIN_TRADE_VALUE, CASH_CP_BASELINE, RISK_FREE_RATE


@dataclass
class ValidationResult:
    """数据校验结果"""
    is_valid: bool
    cleaned_data: Dict[str, Any] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.cleaned_data is None:
            self.cleaned_data = {}


class DataValidator:
    """
    数据校验器 v18.2

    负责校验和清洗输入数据，拦截不合格股票（如ST/*ST股）
    """

    # ST/*ST股名称前缀（不区分大小写）
    ST_PREFIXES = ('ST', '*ST', 'SST', 'S*ST', 'S', 'SS', 'SSD', 'SSR')

    # 必需字段
    REQUIRED_FIELDS = ['code', 'name', 'price', 'pe', 'roe', 'net_profit_growth', 'revenue_growth', 'change_pct']

    # 数值范围校验
    VALIDATION_RULES = {
        'price': {'min': 0, 'max': 10000, 'default': 0},
        'pe': {'min': 0, 'max': 1000, 'default': 0},
        'roe': {'min': -100, 'max': 100, 'default': 0},
        'change_pct': {'min': -50, 'max': 50, 'default': 0},
        'net_profit_growth': {'min': -500, 'max': 500, 'default': 0},
        'revenue_growth': {'min': -100, 'max': 200, 'default': 0},
    }

    @classmethod
    def is_st_stock(cls, name: str) -> bool:
        """检查是否为ST/*ST股"""
        if not name:
            return False
        name_upper = name.upper().strip()
        return name_upper.startswith(cls.ST_PREFIXES)

    @classmethod
    def validate_field(cls, name: str, value: Any, field_type: type) -> Any:
        """校验并转换单个字段"""
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            if value == '' or value.upper() in ('N/A', 'NONE', 'NULL', '-'):
                return None

        try:
            if field_type == float:
                return float(value)
            elif field_type == int:
                return int(float(value))
            elif field_type == str:
                return str(value)
            else:
                return value
        except (ValueError, TypeError):
            return None

    @classmethod
    def validate(cls, raw: Dict[str, Any]) -> ValidationResult:
        """
        校验输入数据

        参数:
            raw: 原始数据字典

        返回:
            ValidationResult(is_valid, cleaned_data, errors)
        """
        errors = []
        cleaned = {}

        # 1. 检查股票名称是否为ST/*ST股（最优先检查）
        name = raw.get('name', '')
        if cls.is_st_stock(name):
            return ValidationResult(
                is_valid=False,
                errors=['ST/*ST股不允许交易或上榜'],
                cleaned_data={'code': raw.get('code'), 'name': name, 'rejected_reason': 'ST/*ST股'}
            )

        # 2. 检查必需字段
        for field in cls.REQUIRED_FIELDS:
            if field not in raw or raw[field] is None:
                if field in ('pe', 'roe', 'net_profit_growth', 'revenue_growth', 'change_pct'):
                    cleaned[field] = 0.0
                else:
                    errors.append(f'缺少必需字段: {field}')
                continue
            cleaned[field] = raw[field]

        # 3. 数值范围校验
        for field, rules in cls.VALIDATION_RULES.items():
            if field in cleaned and cleaned[field] is not None:
                value = cleaned[field]
                if isinstance(value, str):
                    value = cls.validate_field(field, value, float)
                    if value is None:
                        cleaned[field] = rules['default']
                        continue

                if not isinstance(value, (int, float)):
                    cleaned[field] = rules['default']
                    continue

                if value < rules['min']:
                    cleaned[field] = rules['min']
                elif value > rules['max']:
                    cleaned[field] = rules['max']
                else:
                    cleaned[field] = value

        # 4. 字段映射和扩展字段处理
        field_mappings = {
            'code': 'code', 'name': 'name', 'price': 'price', 'pe': 'pe', 'pb': 'pb',
            'roe': 'roe', 'net_profit_growth': 'net_profit_growth',
            'revenue_growth': 'revenue_growth', 'change_pct': 'change_pct',
            'gross_margin': 'gross_margin', 'revenue': 'revenue', 'cashflow': 'cashflow',
            'debt_ratio': 'debt_ratio', 'volume': 'volume', 'amount': 'amount',
            'dividend_yield': 'dividend_yield', 'market_cap': 'market_cap',
            'high': 'high', 'low': 'low', 'data_quality': 'data_quality',
            'current_ratio': 'current_ratio', 'interest_coverage': 'interest_coverage',
            'deducted_net_profit': 'deducted_net_profit', 'sector': 'sector',
        }

        for src_field, dst_field in field_mappings.items():
            if src_field in raw and raw[src_field] is not None:
                cleaned[dst_field] = raw[src_field]

        # 5. 类型强制转换
        for field in ['code', 'name']:
            if field in cleaned:
                cleaned[field] = str(cleaned[field])

        for field in ['price', 'pe', 'roe', 'net_profit_growth', 'revenue_growth', 'change_pct',
                       'pb', 'gross_margin', 'revenue', 'cashflow', 'debt_ratio', 'volume',
                       'amount', 'dividend_yield', 'market_cap', 'high', 'low',
                       'current_ratio', 'interest_coverage', 'deducted_net_profit']:
            if field in cleaned and cleaned[field] is not None:
                cleaned[field] = cls.validate_field(field, cleaned[field], float)
                if cleaned[field] is None:
                    cleaned[field] = 0.0

        if errors:
            return ValidationResult(is_valid=False, errors=errors, cleaned_data=cleaned)

        return ValidationResult(is_valid=True, cleaned_data=cleaned, errors=[])


class CashCP:
    """
    现金战力计算

    核心思想：现金应视为"特殊股票"，其战力定义为持有现金的"机会成本"

    公式：现金战力 = 本金 × (年化无风险利率 / 365) × 持有天数
    示例：10万现金持有30天 = 100000 × (0.02 / 365) × 30 = 164.38 战力损失

    现金CP基准: 50 (中等水平，代表"零增长"基准)
    当所有持仓股CP < 50时，清仓持有现金可能是更优选择
    """

    RISK_FREE_RATE = RISK_FREE_RATE
    CASH_CP_BASELINE = CASH_CP_BASELINE

    @classmethod
    def get_opportunity_cost(cls, cash: float, days: int) -> float:
        """计算持有现金的每日机会成本（战力损失）"""
        daily_rate = cls.RISK_FREE_RATE / 365
        return cash * daily_rate * days

    @classmethod
    def get_daily_cost_rate(cls) -> float:
        return cls.RISK_FREE_RATE / 365

    @classmethod
    def get_cash_cp_baseline(cls) -> float:
        return cls.CASH_CP_BASELINE

    @classmethod
    def should_hold_cash(cls, stock_cp: float, stock_change_pct: float = None) -> tuple[bool, str]:
        """判断是否应该持有现金（而非股票）"""
        if stock_cp < cls.CASH_CP_BASELINE:
            return True, f"股票CP({stock_cp:.1f}) < 现金基准({cls.CASH_CP_BASELINE})"

        if stock_change_pct is not None and stock_change_pct < -5 and stock_cp < 60:
            return True, f"股票下跌({stock_change_pct:.1f}%)且CP偏低({stock_cp:.1f})"

        return False, ""


class TradeDecision:
    """
    换股决策引擎 v15

    核心公式：
        换股净收益 = (B战力 - A战力) × 本金 × 持有天数 - 交易成本
    """

    THRESHOLD_STRONG_BUY = 0.20
    THRESHOLD_BUY = 0.0
    THRESHOLD_HOLD = -0.50

    @classmethod
    def calculate_trade_cost(cls, principal: float, board_from: str = 'main', board_to: str = 'main') -> dict:
        """计算完整换股的总成本 v18.2

        Args:
            principal: 交易本金
            board_from: 卖出股票所在板块 ('main', 'gem', 'star', 'bge')
            board_to: 买入股票所在板块

        注意：
        - 过户费仅沪市收取（双向）
        - 印花税仅卖出时收取
        - 佣金最低5元/笔
        """
        # 券商佣金（双向）
        sell_commission = max(principal * TRADE_COST['commission'], TRADE_COST['min_commission'])
        buy_commission = max(principal * TRADE_COST['commission'], TRADE_COST['min_commission'])

        # 印花税（仅卖出）
        sell_stamp = principal * TRADE_COST['stamp_tax']

        # 过户费（仅沪市双向）
        is_shanghai_from = board_from in ('main', 'star')  # 主板和科创板是沪市
        is_shanghai_to = board_to in ('main', 'star')
        sell_transfer = principal * TRADE_COST['transfer_fee'] if is_shanghai_from else 0
        buy_transfer = principal * TRADE_COST['transfer_fee'] if is_shanghai_to else 0

        total_cost = (sell_commission + sell_stamp + sell_transfer +
                      buy_commission + buy_transfer)

        return {
            'principal': principal,
            'sell_commission': sell_commission,
            'sell_stamp_tax': sell_stamp,
            'sell_transfer_fee': sell_transfer,
            'buy_commission': buy_commission,
            'buy_transfer_fee': buy_transfer,
            'total_cost': total_cost,
            'cost_rate': total_cost / principal if principal > 0 else 0,
            'board_from': board_from,
            'board_to': board_to,
            'note': f"{'沪市' if is_shanghai_from else '深市'}卖出, {'沪市' if is_shanghai_to else '深市'}买入"
        }

    @classmethod
    def should_swap(cls, cp_a: float, cp_b: float, principal: float = 100000,
                    holding_days: int = 30, board_from: str = 'main', board_to: str = 'main') -> dict:
        """判断是否应该从股票A换到股票B v18.2

        Args:
            cp_a: 股票A战力
            cp_b: 股票B战力
            principal: 本金
            holding_days: 持有天数
            board_from: 卖出股票板块
            board_to: 买入股票板块
        """
        cp_diff = cp_b - cp_a
        expected_return = cp_diff * 0.01
        actual_return_rate = expected_return * (holding_days / 365)
        gross_profit = principal * actual_return_rate

        cost_detail = cls.calculate_trade_cost(principal, board_from, board_to)
        trade_cost = cost_detail['total_cost']
        net_profit = gross_profit - trade_cost
        net_return = net_profit / principal if principal > 0 else 0

        cost_threshold_strong = trade_cost * (1 + cls.THRESHOLD_STRONG_BUY)
        cost_threshold_danger = trade_cost * cls.THRESHOLD_HOLD

        if net_profit > cost_threshold_strong:
            action = 'swap'
            action_level = 'strong_buy'
            action_color = 'green'
            action_label = '强烈建议换股'
        elif net_profit > cls.THRESHOLD_BUY * trade_cost:
            action = 'swap'
            action_level = 'buy'
            action_color = 'yellow'
            action_label = '谨慎换股'
        elif net_profit > cost_threshold_danger:
            action = 'hold'
            action_level = 'hold'
            action_color = 'gray'
            action_label = '持有不动'
        else:
            action = 'avoid'
            action_level = 'danger'
            action_color = 'red'
            action_label = '别换！'

        return {
            'from_cp': cp_a, 'to_cp': cp_b, 'cp_diff': cp_diff,
            'expected_return': expected_return, 'holding_days': holding_days,
            'gross_profit': gross_profit, 'trade_cost': trade_cost,
            'net_profit': net_profit, 'net_return': net_return,
            'action': action, 'action_level': action_level,
            'action_color': action_color, 'action_label': action_label,
            'principal': principal,
            'board_from': board_from, 'board_to': board_to,
            'cost_breakdown': cost_detail
        }

    @classmethod
    def get_cp_threshold(cls, principal: float = 100000, holding_days: int = 30, threshold: float = 0) -> float:
        """计算需要最小战力差才能达到指定收益率"""
        trade_cost = cls.calculate_trade_cost(principal)['total_cost']
        daily_cp_value = 0.01 * principal * (holding_days / 365)
        return (trade_cost + threshold) / daily_cp_value if daily_cp_value > 0 else float('inf')


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

    pb: float = 0
    gross_margin: float = 0
    revenue: float = 0
    cashflow: float = 0
    debt_ratio: float = 0
    current_ratio: float = 0
    interest_coverage: float = 0
    deducted_net_profit: float = 0
    volume: float = 0
    amount: float = 0
    dividend_yield: float = 0
    market_cap: float = 0
    high: float = 0
    low: float = 0
    sector: str = ''

    growth_score: float = 0
    value_score: float = 0
    momentum_score: float = 0
    quality_score: float = 0
    total_cp: float = 0

    risk_score: float = 0
    peg: float = 0

    data_quality: str = 'low'

    # v18.4 新增字段
    is_suspended: bool = False  # 是否停牌
    avg_daily_amount_20d: float = 0  # 20日均成交额
    turnover_rate: float = 0  # 换手率
    volatility_20d: float = 0  # 20日波动率

    # v19.6 新增字段
    real_time_score: float = 0  # 实时分（基于1分钟K线，仅核心池）

    def __post_init__(self):
        self.calculate_scores()

    @property
    def board_type(self) -> str:
        code_clean = self.code.lower().replace('sz', '').replace('sh', '')
        if code_clean.startswith('688'):
            return 'star'
        elif code_clean.startswith('300'):
            return 'gem'
        elif code_clean.startswith('4') or code_clean.startswith('8'):
            return 'bge'
        else:
            return 'main'

    @property
    def board_name(self) -> str:
        names = {'main': '主板', 'gem': '创业板', 'star': '科创板', 'bge': '北交所'}
        return names.get(self.board_type, '主板')

    @property
    def price_limit_pct(self) -> float:
        """获取当日价格波动限制 v18.2"""
        limits = {'main': 10.0, 'gem': 20.0, 'star': 20.0, 'bge': 30.0}
        return limits.get(self.board_type, 10.0)

    @property
    def is_limit_up(self) -> bool:
        """检测是否涨停 v18.2

        判断依据：
        1. 涨跌幅在价格限制的0.5%范围内
        2. 最高价达到涨停价
        """
        if self.price <= 0:
            return False
        limit_pct = self.price_limit_pct
        # 涨幅接近涨停限制（10%或20%）
        if abs(self.change_pct - limit_pct) < 0.5:
            return True
        return False

    @property
    def is_limit_down(self) -> bool:
        """检测是否跌停 v18.2

        判断依据：
        1. 跌幅在价格限制的0.5%范围内
        2. 最低价达到跌停价
        """
        if self.price <= 0:
            return False
        limit_pct = self.price_limit_pct
        # 跌幅接近跌停限制（-10%或-20%）
        if abs(self.change_pct + limit_pct) < 0.5:
            return True
        return False

    @property
    def is_st(self) -> bool:
        """是否为ST股 v18.4"""
        return DataValidator.is_st_stock(self.name)

    @property
    def can_trade_newbie(self) -> bool:
        return self.board_type == 'main'

    @property
    def trade_requirement(self) -> str:
        if self.can_trade_newbie:
            return "新手可交易"
        requirements = {'gem': '需2年交易经验', 'star': '需50万资金门槛', 'bge': '需开通北交所权限'}
        return requirements.get(self.board_type, '')

    def calculate_scores(self):
        """计算各因子原始分"""
        # 成长分
        net_g = max(0, min(300, self.net_profit_growth))
        rev_g = max(-50, min(100, self.revenue_growth))
        self.growth_score = net_g * 0.6 + rev_g * 0.4

        # 价值分
        base_roe = min(max(0, self.roe), 25)

        pe_score = 0
        if self.pe > 0:
            if 5 <= self.pe <= 20:
                pe_score = 10
            elif self.pe < 5:
                pe_score = 5
            elif 20 < self.pe <= 30:
                pe_score = 7
            elif 30 < self.pe <= 50:
                pe_score = 3
            elif self.pe > 50:
                pe_score = -5
            elif self.pe > 100:
                pe_score = -10

        peg_bonus = 0
        self.peg = 0
        if self.pe > 0 and self.net_profit_growth > 0:
            self.peg = self.pe / self.net_profit_growth
            if self.peg <= 0.5:
                peg_bonus = 8
            elif self.peg <= 1:
                peg_bonus = 5
            elif self.peg <= 2:
                peg_bonus = 0
            else:
                peg_bonus = -5
        elif self.net_profit_growth < 0:
            peg_bonus = -3

        pb_score = 0
        if self.pb > 0:
            if self.pb <= 1:
                pb_score = 8
            elif self.pb <= 3:
                pb_score = 5
            elif self.pb <= 5:
                pb_score = 2
            elif self.pb > 10:
                pb_score = -3

        self.value_score = max(0, base_roe + pe_score + peg_bonus + pb_score * 0.3)

        # 质量分
        cf_score = 0
        if self.cashflow > 0 and self.roe > 0:
            cf_ratio = self.cashflow / (self.roe * 10 + 1)
            if 0.5 <= cf_ratio <= 3:
                cf_score = 15
            elif cf_ratio > 3:
                cf_score = 10
            else:
                cf_score = 5
        elif self.cashflow <= 0 and self.roe > 0:
            if self.debt_ratio > 80:
                cf_score = 8
            else:
                cf_score = -5

        gm_score = 0
        if self.gross_margin == 0 and self.roe > 10:
            gm_score = 8
        elif self.gross_margin > 30:
            gm_score = 10
        elif self.gross_margin > 15:
            gm_score = 6
        elif self.gross_margin > 0:
            gm_score = 3
        elif self.gross_margin < 0:
            gm_score = -5

        debt_score = 0
        if self.debt_ratio > 80:
            debt_score = -8
        elif self.debt_ratio > 60:
            debt_score = -4
        elif self.debt_ratio > 50:
            debt_score = 0
        else:
            debt_score = 3

        self.quality_score = max(0, cf_score + gm_score + debt_score)

        # 趋势分
        self.momentum_score = max(-10, min(10, self.change_pct))

        self.calculate_risk()

    def calculate_risk(self):
        """计算风险分数（0-100）v18.2

        改进点：
        1. 使用加权风险因子代替简单累加
        2. PE风险考虑行业相对性（不同行业PE基准不同）
        3. 波动风险使用最大风险因子+波动率加权
        """
        # 风险因子及权重
        risk_factors = []

        # 1. PE风险（权重35%）
        if self.pe < 0:
            pe_risk = 100  # 亏损股最高风险
        elif self.pe > 100:
            pe_risk = 80
        elif self.pe > 50:
            pe_risk = 50
        elif self.pe < 5 and self.pe > 0:
            pe_risk = 30  # 低PE可能是价值陷阱
        else:
            pe_risk = 10  # 正常PE范围
        risk_factors.append(('pe', pe_risk, 0.35))

        # 2. ROE风险（权重25%）
        if self.roe < 0:
            roe_risk = 100
        elif self.roe < 5:
            roe_risk = 50
        elif self.roe < 10:
            roe_risk = 20
        else:
            roe_risk = 5
        risk_factors.append(('roe', roe_risk, 0.25))

        # 3. 成长风险（权重20%）
        if self.net_profit_growth < -50:
            growth_risk = 100
        elif self.net_profit_growth < -20:
            growth_risk = 70
        elif self.net_profit_growth < 0:
            growth_risk = 40
        elif self.net_profit_growth > 100:
            growth_risk = 30  # 增长过高可能不可持续
        else:
            growth_risk = 10
        risk_factors.append(('growth', growth_risk, 0.20))

        # 4. 营收风险（权重10%）
        if self.revenue_growth < -30:
            rev_risk = 80
        elif self.revenue_growth < -10:
            rev_risk = 50
        elif self.revenue_growth < 0:
            rev_risk = 20
        else:
            rev_risk = 5
        risk_factors.append(('revenue', rev_risk, 0.10))

        # 5. 波动风险（权重10%）- 使用最大风险因子
        if abs(self.change_pct) > 8:
            vol_risk = 100
        elif abs(self.change_pct) > 5:
            vol_risk = 60
        elif abs(self.change_pct) > 3:
            vol_risk = 30
        else:
            vol_risk = 10
        risk_factors.append(('volatility', vol_risk, 0.10))

        # 加权计算风险分数
        # 使用 max(最大风险因子, 加权平均) 避免单一极端风险被平均稀释
        weighted_sum = sum(risk * weight for _, risk, weight in risk_factors)
        max_risk = max(risk for _, risk, _ in risk_factors)

        # 最终风险 = 0.4 * 最大风险 + 0.6 * 加权平均
        # 这样既考虑极端情况，又不忽视整体风险
        self.risk_score = min(100, 0.4 * max_risk + 0.6 * weighted_sum)

    def get_risk_level(self) -> str:
        if self.risk_score >= 60:
            return '高风险'
        elif self.risk_score >= 30:
            return '中等'
        else:
            return '较低'

    def get_cp_explanation(self) -> dict:
        """获取战力分解说明"""
        weights = {
            'growth': {'weight': 0.30, 'name': '成长分'},
            'value': {'weight': 0.25, 'name': '价值分'},
            'quality': {'weight': 0.20, 'name': '质量分'},
            'momentum': {'weight': 0.15, 'name': '动量分'},
        }

        factors = []

        net_g = max(0, min(300, self.net_profit_growth))
        rev_g = max(-50, min(100, self.revenue_growth))
        growth_raw = net_g * 0.6 + rev_g * 0.4
        factors.append({
            "name": "成长分", "weight": "30%",
            "raw_score": round(growth_raw, 1),
            "contribution": round(self.growth_score * 0.30, 1),
            "detail": f"净利润增长:{self.net_profit_growth:.1f}% × 0.6 + 营收增长:{self.revenue_growth:.1f}% × 0.4"
        })

        base_roe = min(max(0, self.roe), 25)
        factors.append({
            "name": "价值分", "weight": "25%",
            "raw_score": round(self.value_score / 0.25, 1) if self.value_score > 0 else 0,
            "contribution": round(self.value_score * 0.25, 1),
            "detail": f"ROE基础分:{base_roe:.1f} + PE/PEG评分"
        })

        factors.append({
            "name": "质量分", "weight": "20%",
            "raw_score": round(self.quality_score / 0.20, 1) if self.quality_score > 0 else 0,
            "contribution": round(self.quality_score * 0.20, 1),
            "detail": "现金流 + 毛利率 + 资产负债率"
        })

        momentum_raw = max(-10, min(10, self.change_pct))
        factors.append({
            "name": "动量分", "weight": "15%",
            "raw_score": round(momentum_raw, 1),
            "contribution": round(self.momentum_score * 0.15, 1),
            "detail": f"当日涨跌幅:{self.change_pct:.2f}%"
        })

        risk_items = []
        if self.pe < 0:
            risk_items.append("PE为负(亏损)")
        elif self.pe > 100:
            risk_items.append(f"PE极高({self.pe:.0f})")
        if self.roe < 0:
            risk_items.append("ROE为负")
        if abs(self.change_pct) > 8:
            risk_items.append(f"高波动({self.change_pct:.1f}%)")

        summary_parts = []
        if self.growth_score > 70:
            summary_parts.append("成长性优秀")
        if self.value_score > 70:
            summary_parts.append("价值被低估")
        if self.quality_score > 70:
            summary_parts.append("盈利质量高")
        if self.risk_score < 30:
            summary_parts.append("风险较低")
        summary = "，".join(summary_parts) if summary_parts else "综合表现一般"

        return {
            "code": self.code, "name": self.name, "total_cp": round(self.total_cp, 1),
            "factors": factors,
            "risk": {
                "score": self.risk_score, "level": self.get_risk_level(),
                "items": risk_items,
                "adjustment": f"× {1 - (self.risk_score / 100) * 0.10:.2f}"
            },
            "data_quality": self.data_quality,
            "summary": f"{self.name}({self.code})战力{round(self.total_cp, 1)}分，{summary}。"
        }

    def to_dict(self) -> dict:
        return {
            'code': self.code, 'name': self.name, 'price': self.price,
            'pe': self.pe, 'roe': self.roe, 'net_profit_growth': self.net_profit_growth,
            'revenue_growth': self.revenue_growth, 'change_pct': self.change_pct,
            'growth_score': self.growth_score, 'value_score': self.value_score,
            'momentum_score': self.momentum_score, 'quality_score': self.quality_score,
            'total_cp': self.total_cp, 'risk_score': self.risk_score,
            'risk_level': self.get_risk_level(), 'peg': self.peg,
            'pb': self.pb, 'gross_margin': self.gross_margin, 'revenue': self.revenue,
            'cashflow': self.cashflow, 'debt_ratio': self.debt_ratio,
            'dividend_yield': self.dividend_yield, 'market_cap': self.market_cap,
            'high': self.high, 'low': self.low, 'data_quality': self.data_quality,
            'board_type': self.board_type, 'board_name': self.board_name,
            'can_trade_newbie': self.can_trade_newbie, 'trade_requirement': self.trade_requirement,
            'current_ratio': self.current_ratio, 'interest_coverage': self.interest_coverage,
            'deducted_net_profit': self.deducted_net_profit, 'sector': self.sector,
        }


class CPEngine:
    """战力计算引擎"""

    def __init__(self):
        self.stocks: List[StockCP] = []

    def add_stock(self, stock: StockCP):
        """添加股票（自动去重）"""
        if any(s.code == stock.code for s in self.stocks):
            return
        self.stocks.append(stock)

    @staticmethod
    def _robust_normalize(values: List[float], clip_percentile: float = 0.95) -> List[float]:
        """
        稳健归一化 - 使用百分位裁剪避免极值干扰 v18.2

        改进：对于小数据集（< 20），使用IQR方法避免百分位不准确
        """
        if not values:
            return []

        arr = np.array(values, dtype=float)

        # 小数据集使用IQR方法，避免百分位不准确
        if len(arr) < 20:
            return CPEngine._robust_normalize_small(arr)

        # 大数据集使用百分位裁剪
        lower = np.percentile(arr, (1 - clip_percentile) * 50)
        upper = np.percentile(arr, clip_percentile * 50)

        clipped = np.clip(arr, lower, upper)

        if upper == lower:
            return [50.0] * len(values)

        normalized = ((clipped - lower) / (upper - lower)) * 100

        return normalized.tolist()

    @staticmethod
    def _robust_normalize_small(arr: np.ndarray) -> List[float]:
        """
        小数据集归一化（使用IQR异常值检测）v18.2
        """
        if len(arr) < 2:
            return [50.0] * len(arr)

        q1 = np.percentile(arr, 25)
        q3 = np.percentile(arr, 75)
        iqr = q3 - q1

        # IQR方法：1.5*IQR为异常值边界
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        # 确保有区分度
        if upper == lower:
            # 如果IQR为0，使用简单的min-max
            lower = arr.min()
            upper = arr.max()

        clipped = np.clip(arr, lower, upper)

        # min-max归一化到0-100
        if upper == lower:
            return [50.0] * len(arr)

        normalized = ((clipped - lower) / (upper - lower)) * 100

        return normalized.tolist()

    def apply_multi_day_momentum(self, momentum_func, days: int = 5) -> 'CPEngine':
        """
        应用多日动量因子 v18.2

        将历史战力变化的N日动量融入当日动量分
        避免"连续下跌股今日反弹2%动量高于平稳上涨股"的错误信号

        Args:
            momentum_func: 动量计算函数，如 history.calc_momentum_5d
            days: 计算天数

        Returns:
            self（支持链式调用）
        """
        for stock in self.stocks:
            # 获取多日动量（战力变化值）
            nd_momentum = momentum_func(stock.code, days) if momentum_func else 0

            # 多日动量标准化到0-100范围（假设日均战力变化±10为正常范围）
            nd_momentum_normalized = max(0, min(100, (nd_momentum + 50) * 2))

            # 当日涨跌幅标准化
            daily_momentum = max(-10, min(10, stock.change_pct))
            daily_normalized = (daily_momentum + 10) / 20 * 100  # -10~10 -> 0~100

            # 组合动量 = 60%多日动量 + 40%当日动量
            combined_momentum = nd_momentum_normalized * 0.6 + daily_normalized * 0.4

            # 缩放到-10~10范围存储（与原有接口兼容）
            stock.momentum_score = (combined_momentum / 100) * 20 - 10

        return self

    def apply_technical_indicators(self, price_history_func=None) -> 'CPEngine':
        """
        应用技术指标增强动量分 v18.2

        基于MA/MACD/RSI等技术指标调整动量分权重
        技术面与基本面共振时信号更可靠

        Args:
            price_history_func: 获取股票价格历史的函数，签名为 (code: str, days: int) -> List[float]
                                如果为None，使用stock.price作为单一价格点

        Returns:
            self（支持链式调用）
        """
        try:
            from .indicators import TechnicalIndicators
        except ImportError:
            return self  # 技术指标模块不可用时跳过

        for stock in self.stocks:
            # 获取价格历史
            if price_history_func:
                prices = price_history_func(stock.code, 60)
            else:
                # 使用当日价格模拟（实际上需要真实历史数据才能发挥技术指标作用）
                prices = [stock.price * (1 + stock.change_pct / 100 * (i/60 - 0.5))
                         for i in range(60)]

            if len(prices) < 20:
                continue  # 数据不足跳过

            # 获取技术信号
            tech_signal = TechnicalIndicators.get_technical_signal(prices)

            # 存储技术指标数据到股票对象
            if not hasattr(stock, 'technical_signal'):
                stock.technical_signal = tech_signal

            # 基于技术信号调整动量分
            # 技术面偏多时，动量分加权上调
            # 技术面偏空时，动量分加权下调
            momentum = stock.momentum_score

            if tech_signal['signal'] == 'bullish':
                # 技术面偏多，上调动量分
                momentum = momentum * 1.15  # +15%
            elif tech_signal['signal'] == 'bearish':
                # 技术面偏空，下调动量分
                momentum = momentum * 0.85  # -15%

            # RSI超买超卖极端情况进行额外调整
            rsi = tech_signal.get('rsi')
            if rsi is not None:
                if rsi > 80:
                    momentum = momentum * 0.7  # 极度超买，大幅下调
                elif rsi < 20:
                    momentum = momentum * 1.3  # 极度超卖，大幅上浮

            stock.momentum_score = max(-10, min(10, momentum))

        return self

    def calculate_real_time_score(self, code: str, current_price: float) -> float:
        """计算实时因子 v19.6

        基于1分钟K线计算MA5、MA15变化率和成交量比率
        仅在盘中交易时间计算

        Args:
            code: 股票代码
            current_price: 当前价格（用于计算开盘均线变化）

        Returns:
            real_time_score (-10 ~ 10)
        """
        try:
            from .trading_time import is_trading_time
            if not is_trading_time():
                return 0.0  # 非交易时间返回0

            from data_manager import get_minute_ma, get_minute_klines

            # 获取分钟级均线
            ma5 = get_minute_ma(code, minutes=5, days=1)
            ma15 = get_minute_ma(code, minutes=15, days=1)

            # 获取分钟K线数据计算成交量比率
            kline_result = get_minute_klines(code, days=1, limit=10)
            if not kline_result.success or kline_result.data.empty:
                return 0.0

            df = kline_result.data
            if len(df) < 5:
                return 0.0

            current_volume = float(df.iloc[0]['volume']) if 'volume' in df.columns else 0
            avg_volume = df['volume'].mean() if 'volume' in df.columns else 0

            # 计算均线变化率
            ma5_change = 0.0
            if ma5 and current_price:
                ma5_change = (current_price - ma5) / ma5 * 100

            ma15_change = 0.0
            if ma15 and current_price:
                ma15_change = (current_price - ma15) / ma15 * 100

            # 计算成交量比率
            volume_ratio = 1.0
            if avg_volume > 0:
                volume_ratio = current_volume / avg_volume

            # 计算real_time_score
            # real_time_score = MA5变化×0.5 + MA15变化×0.3 + 成交量异常×0.2
            real_time = (
                ma5_change * 0.5 +
                ma15_change * 0.3 +
                (volume_ratio - 1) * 10 * 0.2
            )

            return max(-10, min(10, real_time))
        except Exception:
            return 0.0

    def calculate_all(self, use_multi_day_momentum: bool = True) -> List[StockCP]:
        """计算所有股票的总战力 v18.2

        使用稳健归一化（百分位裁剪）避免分数漂移问题
        参考专家评审3的问题1修复方案

        Args:
            use_multi_day_momentum: 是否集成多日动量因子（默认True）
                                   集成后可避免"连续下跌股今日反弹2%动量高于平稳上涨股"的错误信号
        """
        if not self.stocks:
            return []

        # 多日动量因子集成 v18.2
        # 在归一化之前计算，避免当日涨跌幅权重过高
        if use_multi_day_momentum:
            try:
                from .history import calc_momentum_5d
                self.apply_multi_day_momentum(calc_momentum_5d, days=5)
            except ImportError:
                pass  # 历史模块不可用时跳过

        # 收集各维度原始分数
        growth_values = [s.growth_score for s in self.stocks]
        value_values = [s.value_score for s in self.stocks]
        momentum_values = [s.momentum_score for s in self.stocks]
        quality_values = [s.quality_score for s in self.stocks]

        # 稳健归一化（使用95%百分位裁剪）
        norm_growth_list = self._robust_normalize(growth_values, clip_percentile=0.95)
        norm_value_list = self._robust_normalize(value_values, clip_percentile=0.95)
        norm_momentum_list = self._robust_normalize(momentum_values, clip_percentile=0.95)

        MIN_QUALITY_BASELINE = 10

        for i, stock in enumerate(self.stocks):
            # 计算实时因子 v19.6（仅核心池需要，已在外部调用时过滤）
            stock.real_time_score = self.calculate_real_time_score(stock.code, stock.price)

            # 使用稳健归一化后的分数
            norm_growth = norm_growth_list[i]
            norm_value = norm_value_list[i]
            norm_momentum = norm_momentum_list[i]

            # 波动率调整动量分 v18.2
            # 高波动日子的涨跌幅信号可靠性下降，适当降低权重
            norm_momentum = self._apply_volatility_adjustment(stock, norm_momentum)

            # 质量分使用保底机制
            norm_quality = max(MIN_QUALITY_BASELINE, stock.quality_score)

            stock.growth_score = norm_growth
            stock.value_score = norm_value
            stock.momentum_score = norm_momentum
            stock.quality_score = norm_quality

            # real_time_score 已在 calculate_real_time_score() 中计算
            norm_real_time = max(-10, min(10, stock.real_time_score))

            base_cp = (
                norm_growth * WEIGHTS['growth'] +
                norm_value * WEIGHTS['value'] +
                norm_quality * WEIGHTS['quality'] +
                norm_momentum * WEIGHTS['momentum'] +
                norm_real_time * WEIGHTS.get('real_time', 0)
            )

            risk_factor = 1 - (stock.risk_score / 100) * WEIGHTS['risk_penalty']
            stock.total_cp = max(0, base_cp * risk_factor)

        # 行业相对PE风险调整 v18.2
        self._apply_industry_pe_adjustment()

        return self.stocks

    def _calculate_industry_pe_averages(self) -> Dict[str, float]:
        """计算行业平均PE v18.2

        从当前股票池计算各行业的PE中位数
        用于行业相对PE风险评估
        """
        industry_pe = {}
        industry_count = {}

        for stock in self.stocks:
            if not stock.sector or stock.pe <= 0:
                continue

            sector = stock.sector
            if sector not in industry_pe:
                industry_pe[sector] = []
                industry_count[sector] = 0

            industry_pe[sector].append(stock.pe)
            industry_count[sector] += 1

        # 计算各行业中位数（排除样本数少于3的行业）
        industry_median_pe = {}
        for sector, pes in industry_pe.items():
            if industry_count[sector] >= 3:
                industry_median_pe[sector] = sorted(pes)[len(pes) // 2]

        return industry_median_pe

    def _apply_industry_pe_adjustment(self):
        """应用行业相对PE风险调整 v18.2

        调整逻辑：
        - 如果某股票PE显著高于行业平均（如2倍以上），增加风险
        - 如果某股票PE显著低于行业平均（如0.5倍以下），降低风险（价值洼地）
        """
        industry_median_pe = self._calculate_industry_pe_averages()
        if not industry_median_pe:
            return

        for stock in self.stocks:
            if not stock.sector or stock.pe <= 0 or stock.sector not in industry_median_pe:
                continue

            industry_pe = industry_median_pe[stock.sector]
            if industry_pe <= 0:
                continue

            pe_ratio = stock.pe / industry_pe

            # 根据PE与行业中位数的比率调整风险
            # pe_ratio > 2: 高于行业2倍，风险+20
            # pe_ratio < 0.5: 低于行业一半，价值洼地，风险-10
            adjustment = 0
            if pe_ratio > 2.5:
                adjustment = 25
            elif pe_ratio > 2.0:
                adjustment = 20
            elif pe_ratio > 1.5:
                adjustment = 10
            elif pe_ratio < 0.4:
                adjustment = -15
            elif pe_ratio < 0.5:
                adjustment = -10
            elif pe_ratio < 0.7:
                adjustment = -5

            # 应用调整（限制在0-100范围内）
            stock.risk_score = max(0, min(100, stock.risk_score + adjustment))

            # 同时调整价值分：如果PE低于行业，价值分加成
            if pe_ratio < 0.6 and stock.value_score > 0:
                bonus = min(10, (0.6 - pe_ratio) * 25)
                stock.value_score = min(100, stock.value_score + bonus)

    @staticmethod
    def _apply_volatility_adjustment(stock: 'StockCP', momentum: float) -> float:
        """波动率调整动量分 v18.2

        调整逻辑：
        - 使用 high-low 范围计算日内波动率
        - 高波动日的涨跌幅信号可靠性下降，适当降低权重
        - 涨停/跌停时波动率极高，完全依赖稳健归一化处理

        Args:
            stock: 股票对象
            momentum: 原始动量分（归一化后0-100）

        Returns:
            调整后的动量分
        """
        if stock.price <= 0 or stock.high <= 0 or stock.low <= 0:
            return momentum

        # 计算日内波动率 (high-low) / price
        daily_range = (stock.high - stock.low) / stock.price

        # 正常波动范围：1%-3%
        # 高波动：>5% 可靠性差
        # 低波动：<1% 可靠性高
        if daily_range > 0.08:  # 极端波动（8%+）
            volatility_factor = 0.3  # 30%权重
        elif daily_range > 0.05:  # 高波动（5%+）
            volatility_factor = 0.5  # 50%权重
        elif daily_range > 0.03:  # 正常偏高（3%+）
            volatility_factor = 0.7  # 70%权重
        elif daily_range < 0.01:  # 低波动（1%以内）
            volatility_factor = 1.2  # 120%权重加成
        else:
            volatility_factor = 1.0  # 正常权重

        adjusted_momentum = momentum * volatility_factor

        # 限制在0-100范围内
        return max(0, min(100, adjusted_momentum))

    def get_top(self, n: int = 50, board: str = None) -> List[StockCP]:
        """获取战力榜TOP N"""
        stocks = self.stocks
        if board == 'main':
            stocks = [s for s in stocks if s.can_trade_newbie]
        elif board is not None and board != 'all':
            stocks = [s for s in stocks if s.board_type == board]

        sorted_stocks = sorted(stocks, key=lambda s: s.total_cp, reverse=True)
        return sorted_stocks[:n]

    def get_bottom(self, n: int = 10, board: str = None) -> List[StockCP]:
        """获取战力榜BOTTOM N（避雷区）"""
        stocks = self.stocks
        if board == 'main':
            stocks = [s for s in stocks if s.can_trade_newbie]

        sorted_stocks = sorted(stocks, key=lambda s: s.total_cp, reverse=True)
        return sorted_stocks[-n:]

    def get_by_code(self, code: str) -> Optional[StockCP]:
        """根据代码获取股票"""
        for stock in self.stocks:
            if stock.code == code:
                return stock
        return None

    def calculate_all_with_cache(
        self,
        use_cache: bool = True,
        cache_ttl: int = 300,
        use_multi_day_momentum: bool = True
    ) -> List[StockCP]:
        """
        使用缓存计算所有股票战力 v18.2

        优化重复计算：
        - 对于缓存未过期的股票，直接使用缓存的归一化分数
        - 对于缓存已过期或不存在，重新计算并更新缓存

        Args:
            use_cache: 是否使用缓存（默认True）
            cache_ttl: 缓存有效期（秒，默认300）
            use_multi_day_momentum: 是否使用多日动量

        Returns:
            计算后的股票列表
        """
        if not self.stocks:
            return []

        try:
            from .cache import get_factor_cache, cache_stock_factors, StockFactorCache
        except ImportError:
            # 缓存模块不可用时，使用常规计算
            return self.calculate_all(use_multi_day_momentum)

        cache = get_factor_cache()

        # 检查每只股票的缓存状态
        cached_stocks = []
        uncached_codes = []

        for stock in self.stocks:
            cached = cache.get(stock.code)
            if cached and not cached.is_expired(cache_ttl):
                cached_stocks.append((stock, cached))
            else:
                uncached_codes.append(stock.code)

        # 如果大多数股票已缓存，尝试使用缓存的归一化参数
        if use_cache and len(cached_stocks) > len(self.stocks) * 0.5:
            # 使用缓存的归一化参数进行计算
            norm_params = cache.get_norm_params()
            if norm_params:
                return self._calculate_with_cached_params(
                    cached_stocks, norm_params, cache_ttl
                )

        # 常规计算并更新缓存
        result = self.calculate_all(use_multi_day_momentum)

        # 缓存计算结果
        if use_cache:
            for stock in result:
                cache_stock_factors(stock, cache_ttl)

        return result

    def _calculate_with_cached_params(
        self,
        cached_stocks: List[Tuple['StockCP', 'StockFactorCache']],
        norm_params: Dict,
        cache_ttl: int
    ) -> List[StockCP]:
        """
        使用缓存的归一化参数快速计算 v18.2

        Args:
            cached_stocks: (股票, 缓存条目) 列表
            norm_params: 归一化参数字典
            cache_ttl: 缓存有效期

        Returns:
            计算后的股票列表
        """
        for stock, cached in cached_stocks:
            # 应用缓存的归一化分数
            stock.growth_score = cached.norm_growth_score
            stock.value_score = cached.norm_value_score
            stock.momentum_score = cached.norm_momentum_score
            stock.quality_score = cached.norm_quality_score
            stock.risk_score = cached.risk_score
            stock.peg = cached.peg

            # 重新计算总战力
            base_cp = (
                stock.growth_score * WEIGHTS['growth'] +
                stock.value_score * WEIGHTS['value'] +
                stock.quality_score * WEIGHTS['quality'] +
                stock.momentum_score * WEIGHTS['momentum']
            )
            risk_factor = 1 - (stock.risk_score / 100) * WEIGHTS['risk_penalty']
            stock.total_cp = max(0, base_cp * risk_factor)

        return [s[0] for s in cached_stocks]

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame"""
        data = [s.to_dict() for s in self.stocks]
        df = pd.DataFrame(data)
        return df.sort_values('total_cp', ascending=False)


def create_stock_from_raw(
    code: str, name: str, price: float, pe: float, roe: float,
    net_profit_growth: float, revenue_growth: float, change_pct: float,
    pb: float = 0, gross_margin: float = 0, revenue: float = 0,
    cashflow: float = 0, debt_ratio: float = 0, volume: float = 0,
    amount: float = 0, dividend_yield: float = 0, market_cap: float = 0,
    high: float = 0, low: float = 0, data_quality: str = 'low',
    current_ratio: float = 0, interest_coverage: float = 0, deducted_net_profit: float = 0,
    sector: str = '',
    # v18.4 新增字段
    is_suspended: bool = False,
    avg_daily_amount_20d: float = 0,
    turnover_rate: float = 0,
    volatility_20d: float = 0
) -> StockCP:
    """从原始数据创建StockCP对象

    注意:
        函数内部会调用DataValidator.validate()进行数据校验，
        ST/*ST股会被拦截并返回is_valid=False
    """
    # 使用DataValidator进行数据校验
    raw_data = {
        'code': code, 'name': name, 'price': price, 'pe': pe, 'roe': roe,
        'net_profit_growth': net_profit_growth, 'revenue_growth': revenue_growth,
        'change_pct': change_pct, 'pb': pb, 'gross_margin': gross_margin,
        'revenue': revenue, 'cashflow': cashflow, 'debt_ratio': debt_ratio,
        'volume': volume, 'amount': amount, 'dividend_yield': dividend_yield,
        'market_cap': market_cap, 'high': high, 'low': low,
        'data_quality': data_quality, 'current_ratio': current_ratio,
        'interest_coverage': interest_coverage, 'deducted_net_profit': deducted_net_profit,
        'sector': sector,
        # v18.4 新增字段
        'is_suspended': is_suspended,
        'avg_daily_amount_20d': avg_daily_amount_20d,
        'turnover_rate': turnover_rate,
        'volatility_20d': volatility_20d,
    }

    validation_result = DataValidator.validate(raw_data)

    if not validation_result.is_valid:
        raise ValueError(f"数据校验失败: {validation_result.errors}")

    cleaned = validation_result.cleaned_data

    return StockCP(
        code=cleaned.get('code', code),
        name=cleaned.get('name', name),
        price=cleaned.get('price', price),
        pe=cleaned.get('pe', pe),
        roe=cleaned.get('roe', roe),
        net_profit_growth=cleaned.get('net_profit_growth', net_profit_growth),
        revenue_growth=cleaned.get('revenue_growth', revenue_growth),
        change_pct=cleaned.get('change_pct', change_pct),
        pb=cleaned.get('pb', pb),
        gross_margin=cleaned.get('gross_margin', gross_margin),
        revenue=cleaned.get('revenue', revenue),
        cashflow=cleaned.get('cashflow', cashflow),
        debt_ratio=cleaned.get('debt_ratio', debt_ratio),
        volume=cleaned.get('volume', volume),
        amount=cleaned.get('amount', amount),
        dividend_yield=cleaned.get('dividend_yield', dividend_yield),
        market_cap=cleaned.get('market_cap', market_cap),
        high=cleaned.get('high', high),
        low=cleaned.get('low', low),
        data_quality=cleaned.get('data_quality', data_quality),
        current_ratio=cleaned.get('current_ratio', current_ratio),
        interest_coverage=cleaned.get('interest_coverage', interest_coverage),
        deducted_net_profit=cleaned.get('deducted_net_profit', deducted_net_profit),
        sector=cleaned.get('sector', sector),
        # v18.4 新增字段
        is_suspended=cleaned.get('is_suspended', is_suspended),
        avg_daily_amount_20d=cleaned.get('avg_daily_amount_20d', avg_daily_amount_20d),
        turnover_rate=cleaned.get('turnover_rate', turnover_rate),
        volatility_20d=cleaned.get('volatility_20d', volatility_20d),
    )
