"""
战力计算引擎 - TradeSnake Core
"""

import pandas as pd
from typing import List, Optional
from dataclasses import dataclass

# 战力公式权重 v14（赚钱版）
# 成长(30%) + 价值(25%) + 质量(20%) + 动量(15%) + 风险调整(10%)
WEIGHTS = {
    'growth': 0.30,
    'value': 0.25,
    'quality': 0.20,
    'momentum': 0.15,
    'risk_penalty': 0.10  # 风险惩罚因子
}

# ============================================
# 交易成本常量 v15（包含手续费建模）
# ============================================
# A股交易费用（2024年最新标准）
TRADE_COST = {
    'commission': 0.0003,       # 券商佣金：万分之三，默认水平
    'stamp_tax': 0.0005,        # 印花税：万分之五，仅卖出时收取
    'transfer_fee': 0.00001,    # 过户费：十万分之一，沪市双向，深市免
    'min_commission': 5.0,      # 最低佣金：5元/笔
}

# 完整换股一次的成本比率（买+卖）
SELL_COST_RATE = TRADE_COST['commission'] + TRADE_COST['stamp_tax'] + TRADE_COST['transfer_fee']  # 0.081%
BUY_COST_RATE = TRADE_COST['commission'] + TRADE_COST['transfer_fee']                              # 0.031%
TOTAL_TRADE_COST_RATE = SELL_COST_RATE + BUY_COST_RATE  # 0.112%

# 最小有意义交易量（使最低消费影响 < 0.02%）
MIN_TRADE_VALUE = 50000  # 5万


class CashCP:
    """
    现金战力计算 v15

    核心思想：现金应视为"特殊股票"，其战力定义为持有现金的"机会成本"

    公式：现金战力 = 本金 × (年化无风险利率 / 365) × 持有天数
    示例：10万现金持有30天 = 100000 × (0.02 / 365) × 30 = 164.38 战力损失
    """

    RISK_FREE_RATE = 0.02  # 年化无风险利率 2%（国债/货基基准）

    @classmethod
    def get_opportunity_cost(cls, cash: float, days: int) -> float:
        """
        计算持有现金的每日机会成本（战力损失）

        参数:
            cash: 现金金额（元）
            days: 持有天数

        返回:
            战力损失值（持有现金 vs 买入优质股）

        示例:
            CashCP.get_opportunity_cost(100000, 30) = 164.38
        """
        daily_rate = cls.RISK_FREE_RATE / 365
        return cash * daily_rate * days

    @classmethod
    def get_daily_cost_rate(cls) -> float:
        """获取每日机会成本比率"""
        return cls.RISK_FREE_RATE / 365


class TradeDecision:
    """
    换股决策引擎 v15

    核心公式：
        换股净收益 = (B战力 - A战力) × 本金 × 持有天数 - 交易成本

    换股建议分级：
        - 强烈建议换：净收益 > 交易成本的20%
        - 可以考虑换：净收益 > 0
        - 不建议换：净收益 <= 0（持有不动 🎯）
        - 别换：净收益 < -交易成本的50%（会亏钱）
    """

    # 建议阈值
    THRESHOLD_STRONG_BUY = 0.20  # 强烈建议换：净收益 > 成本20%
    THRESHOLD_BUY = 0.0          # 可以考虑换：净收益 > 0
    THRESHOLD_HOLD = -0.50       # 不建议换：净收益 < -成本50%

    @classmethod
    def calculate_trade_cost(cls, principal: float) -> dict:
        """
        计算完整换股的总成本

        参数:
            principal: 本金（元）

        返回:
            成本明细字典
        """
        sell_commission = max(principal * TRADE_COST['commission'], TRADE_COST['min_commission'])
        sell_stamp = principal * TRADE_COST['stamp_tax']  # 印花税仅卖出
        sell_transfer = principal * TRADE_COST['transfer_fee']

        buy_commission = max(principal * TRADE_COST['commission'], TRADE_COST['min_commission'])
        buy_transfer = principal * TRADE_COST['transfer_fee']

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
            'cost_rate': total_cost / principal if principal > 0 else 0
        }

    @classmethod
    def should_swap(cls,
                   cp_a: float,
                   cp_b: float,
                   principal: float = 100000,
                   holding_days: int = 30) -> dict:
        """
        判断是否应该从股票A换到股票B

        参数:
            cp_a: 当前股票战力
            cp_b: 目标股票战力
            principal: 本金（元），默认10万
            holding_days: 计划持有天数，默认30天

        返回:
            决策建议字典，包含：
            - cp_diff: 战力差
            - expected_return: 预期收益率（年化）
            - gross_profit: 毛收益（元）
            - trade_cost: 交易成本（元）
            - net_profit: 净收益（元）
            - net_return: 净收益率
            - action: 建议操作
            - action_level: 操作等级 (strong_buy/buy/hold/danger)
            - action_color: 颜色代码
            - action_label: 操作标签
        """
        # 1. 战力差
        cp_diff = cp_b - cp_a

        # 2. 战力差转换为预期年化收益率
        # 假设CP差1分（约1%）对应年化收益差1%
        expected_return = cp_diff * 0.01  # 年化收益率

        # 3. 考虑持有天数的实际收益
        # 实际收益 = 年化收益 × (持有天数 / 365)
        actual_return_rate = expected_return * (holding_days / 365)
        gross_profit = principal * actual_return_rate

        # 4. 交易成本
        trade_cost = cls.calculate_trade_cost(principal)['total_cost']

        # 5. 净收益
        net_profit = gross_profit - trade_cost
        net_return = net_profit / principal if principal > 0 else 0

        # 6. 判断操作建议
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
            action_label = '持有不动 🎯'
        else:
            action = 'avoid'
            action_level = 'danger'
            action_color = 'red'
            action_label = '别换！'

        return {
            'from_cp': cp_a,
            'to_cp': cp_b,
            'cp_diff': cp_diff,
            'expected_return': expected_return,
            'holding_days': holding_days,
            'gross_profit': gross_profit,
            'trade_cost': trade_cost,
            'net_profit': net_profit,
            'net_return': net_return,
            'action': action,
            'action_level': action_level,
            'action_color': action_color,
            'action_label': action_label,
            'principal': principal,
            'cost_breakdown': cls.calculate_trade_cost(principal)
        }

    @classmethod
    def get_cp_threshold(cls,
                        principal: float = 100000,
                        holding_days: int = 30,
                        threshold: float = 0) -> float:
        """
        计算需要最小战力差才能达到指定收益率

        参数:
            principal: 本金
            holding_days: 持有天数
            threshold: 目标收益率（默认为0，即不亏钱的临界点）

        返回:
            需要的最小战力差
        """
        trade_cost = cls.calculate_trade_cost(principal)['total_cost']
        # net_profit = cp_diff * 0.01 * principal * (days/365) - trade_cost >= threshold
        # cp_diff >= (trade_cost + threshold) / (0.01 * principal * (days/365))
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

    # 扩展字段
    pb: float = 0  # 市净率
    gross_margin: float = 0  # 毛利率
    revenue: float = 0  # 主营收入(亿)
    cashflow: float = 0  # 经营现金流(亿)
    debt_ratio: float = 0  # 资产负债率
    volume: float = 0  # 成交量(手)
    amount: float = 0  # 成交额(万)
    dividend_yield: float = 0  # 股息率(%)
    market_cap: float = 0  # 市值(亿)
    high: float = 0  # 最高价
    low: float = 0  # 最低价

    # 计算得分
    growth_score: float = 0
    value_score: float = 0
    momentum_score: float = 0
    quality_score: float = 0  # 质量因子：现金流+毛利率
    total_cp: float = 0

    # 风险评估
    risk_score: float = 0  # 风险分数（0-100，越高风险越大）
    peg: float = 0  # PEG估值

    # 数据质量标记
    data_quality: str = 'low'  # high/medium/low

    def __post_init__(self):
        self.calculate_scores()

    @property
    def board_type(self) -> str:
        """根据代码判断板块类型"""
        code_clean = self.code.lower().replace('sz', '').replace('sh', '')
        if code_clean.startswith('688'):
            return 'star'  # 科创板
        elif code_clean.startswith('300'):
            return 'gem'   # 创业板
        elif code_clean.startswith('4') or code_clean.startswith('8'):
            return 'bge'   # 北交所
        else:
            return 'main'  # 主板

    @property
    def board_name(self) -> str:
        """获取板块显示名称"""
        names = {
            'main': '主板',
            'gem': '创业板',
            'star': '科创板',
            'bge': '北交所'
        }
        return names.get(self.board_type, '主板')

    @property
    def can_trade_newbie(self) -> bool:
        """新手是否可以交易"""
        return self.board_type == 'main'

    @property
    def trade_requirement(self) -> str:
        """交易权限要求"""
        if self.can_trade_newbie:
            return "新手可交易"
        requirements = {
            'gem': '需2年交易经验',
            'star': '需50万资金门槛',
            'bge': '需开通北交所权限'
        }
        return requirements.get(self.board_type, '')

    def calculate_scores(self):
        """计算各因子原始分

        公式v14（赚钱版）：
        - 成长分：净利润增长和营收增长
        - 价值分：ROE + PE健康度 + PEG综合评分
        - 趋势分：当日涨跌幅
        - 质量分：现金流质量 + 毛利率
        """
        # ========== 成长分 ==========
        # 净利润增长：限制在0-300%
        net_g = max(0, min(300, self.net_profit_growth))
        # 营收增长：限制在-50%到100%
        rev_g = max(-50, min(100, self.revenue_growth))
        # 复合增长率
        self.growth_score = net_g * 0.6 + rev_g * 0.4

        # ========== 价值分（增强版）============
        # 基础ROE评分（负ROE当0，ROE>25截断）
        base_roe = min(max(0, self.roe), 25)

        # PE健康度评分
        pe_score = 0
        if self.pe > 0:
            if 5 <= self.pe <= 20:
                pe_score = 10  # 合理PE区间
            elif self.pe < 5:
                pe_score = 5   # 低PE可能有问题
            elif 20 < self.pe <= 30:
                pe_score = 7
            elif 30 < self.pe <= 50:
                pe_score = 3
            elif self.pe > 50:
                pe_score = -5
            elif self.pe > 100:
                pe_score = -10

        # PEG估值（PE/Growth，越低越好）
        peg_bonus = 0
        self.peg = 0
        if self.pe > 0 and self.net_profit_growth > 0:
            self.peg = self.pe / self.net_profit_growth
            # PEG < 1 优质，> 2 高估
            if self.peg <= 0.5:
                peg_bonus = 8
            elif self.peg <= 1:
                peg_bonus = 5
            elif self.peg <= 2:
                peg_bonus = 0
            else:
                peg_bonus = -5
        elif self.net_profit_growth < 0:
            peg_bonus = -3  # 负增长惩罚

        # PB市净率评分（银行/周期股参考）
        pb_score = 0
        if self.pb > 0:
            if self.pb <= 1:
                pb_score = 8  # 破净或低PB
            elif self.pb <= 3:
                pb_score = 5
            elif self.pb <= 5:
                pb_score = 2
            elif self.pb > 10:
                pb_score = -3

        self.value_score = max(0, base_roe + pe_score + peg_bonus + pb_score * 0.3)

        # ========== 质量分（新增：现金流+毛利率）============
        cf_score = 0
        if self.cashflow > 0 and self.roe > 0:
            # 现金流/ROE比例合理表示盈利质量高
            cf_ratio = self.cashflow / (self.roe * 10 + 1)
            if 0.5 <= cf_ratio <= 3:
                cf_score = 15
            elif cf_ratio > 3:
                cf_score = 10
            else:
                cf_score = 5
        elif self.cashflow <= 0 and self.roe > 0:
            cf_score = -5  # 有利润无现金流，问题

        # 毛利率评分（反映护城河）
        gm_score = 0
        if self.gross_margin > 30:
            gm_score = 10  # 高毛利=护城河
        elif self.gross_margin > 15:
            gm_score = 6
        elif self.gross_margin > 0:
            gm_score = 3
        elif self.gross_margin < 0:
            gm_score = -5  # 负毛利

        # 资产负债率风险
        debt_score = 0
        if self.debt_ratio > 80:
            debt_score = -8  # 高负债风险
        elif self.debt_ratio > 60:
            debt_score = -4
        elif self.debt_ratio > 50:
            debt_score = 0
        else:
            debt_score = 3  # 低负债=稳健

        self.quality_score = max(0, cf_score + gm_score + debt_score)

        # ========== 趋势分 ==========
        # 当日涨跌幅（限制在-10到10之间）
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

    def get_cp_explanation(self) -> dict:
        """
        获取战力分解说明 v16

        展示为什么这只股票得到这个战力值，让用户理解每个因子的贡献

        返回格式：
        {
            "code": "600519",
            "name": "贵州茅台",
            "total_cp": 95.5,
            "factors": [
                {"name": "成长分", "weight": "30%", "raw_score": 85, "norm_score": 28.5, "detail": "..."},
                ...
            ],
            "risk": {...},
            "summary": "..."
        }
        """
        # 权重配置
        weights = {
            'growth': {'weight': 0.30, 'name': '成长分'},
            'value': {'weight': 0.25, 'name': '价值分'},
            'quality': {'weight': 0.20, 'name': '质量分'},
            'momentum': {'weight': 0.15, 'name': '动量分'},
        }

        # 计算各因子的贡献
        factors = []

        # 成长分详情
        net_g = max(0, min(300, self.net_profit_growth))
        rev_g = max(-50, min(100, self.revenue_growth))
        growth_raw = net_g * 0.6 + rev_g * 0.4
        factors.append({
            "name": "成长分",
            "weight": "30%",
            "raw_score": round(growth_raw, 1),
            "contribution": round(self.growth_score * 0.30, 1),
            "detail": f"净利润增长:{self.net_profit_growth:.1f}%(限制后:{net_g:.1f}%) × 0.6 + 营收增长:{self.revenue_growth:.1f}%(限制后:{rev_g:.1f}%) × 0.4"
        })

        # 价值分详情
        base_roe = min(max(0, self.roe), 25)
        pe_score = 0
        pe_explain = ""
        if self.pe > 0:
            if 5 <= self.pe <= 20:
                pe_score = 10
                pe_explain = f"PE={self.pe:.1f}在合理区间[5,20]，+10分"
            elif self.pe < 5:
                pe_score = 5
                pe_explain = f"PE={self.pe:.1f}偏低，可能有问题，+5分"
            elif 20 < self.pe <= 30:
                pe_score = 7
                pe_explain = f"PE={self.pe:.1f}略高，+7分"
            elif 30 < self.pe <= 50:
                pe_score = 3
                pe_explain = f"PE={self.pe:.1f}偏高，+3分"
            elif self.pe > 50:
                pe_score = -5
                pe_explain = f"PE={self.pe:.1f}过高，-5分"
            elif self.pe > 100:
                pe_score = -10
                pe_explain = f"PE={self.pe:.1f}极高，-10分"
        else:
            pe_explain = f"PE={self.pe:.1f}为负，不参与评分"

        peg_bonus = 0
        peg_explain = ""
        if self.pe > 0 and self.net_profit_growth > 0:
            peg = self.pe / self.net_profit_growth
            if peg <= 0.5:
                peg_bonus = 8
                peg_explain = f"PEG={peg:.2f}<=0.5，成长性价比极高，+8分"
            elif peg <= 1:
                peg_bonus = 5
                peg_explain = f"PEG={peg:.2f}<=1，成长性价比合理，+5分"
            elif peg <= 2:
                peg_bonus = 0
                peg_explain = f"PEG={peg:.2f}<=2，成长性价比一般"
            else:
                peg_bonus = -5
                peg_explain = f"PEG={peg:.2f}>2，成长性价比差，-5分"
        elif self.net_profit_growth < 0:
            peg_explain = f"负增长，-3分"

        value_detail = f"ROE基础分:{base_roe:.1f} + PE健康度:{pe_score}分({pe_explain}) + PEG估值:{peg_bonus}分({peg_explain})"
        factors.append({
            "name": "价值分",
            "weight": "25%",
            "raw_score": round(self.value_score / 0.25, 1) if self.value_score > 0 else 0,
            "contribution": round(self.value_score * 0.25, 1),
            "detail": value_detail
        })

        # 质量分详情
        cf_score = 0
        cf_explain = ""
        if self.cashflow > 0 and self.roe > 0:
            cf_ratio = self.cashflow / (self.roe * 10 + 1)
            if 0.5 <= cf_ratio <= 3:
                cf_score = 15
                cf_explain = f"现金流/ROE比={cf_ratio:.2f}在合理区间[0.5,3]，+15分"
            elif cf_ratio > 3:
                cf_score = 10
                cf_explain = f"现金流/ROE比={cf_ratio:.2f}偏高，+10分"
            else:
                cf_score = 5
                cf_explain = f"现金流/ROE比={cf_ratio:.2f}偏低，+5分"
        elif self.cashflow <= 0 and self.roe > 0:
            cf_score = -5
            cf_explain = "有利润无现金流，问题，-5分"

        gm_score = 0
        gm_explain = ""
        if self.gross_margin > 30:
            gm_score = 10
            gm_explain = f"毛利率={self.gross_margin:.1f}%>30%，护城河强，+10分"
        elif self.gross_margin > 15:
            gm_score = 6
            gm_explain = f"毛利率={self.gross_margin:.1f}%>15%，有一定护城河，+6分"
        elif self.gross_margin > 0:
            gm_score = 3
            gm_explain = f"毛利率={self.gross_margin:.1f}%>0%，护城河弱，+3分"
        else:
            gm_explain = f"毛利率={self.gross_margin:.1f}%为负，-5分"

        debt_score = 0
        debt_explain = ""
        if self.debt_ratio > 80:
            debt_score = -8
            debt_explain = f"资产负债率={self.debt_ratio:.1f}%>80%，高负债风险，-8分"
        elif self.debt_ratio > 60:
            debt_score = -4
            debt_explain = f"资产负债率={self.debt_ratio:.1f}%>60%，中等风险，-4分"
        elif self.debt_ratio > 50:
            debt_explain = f"资产负债率={self.debt_ratio:.1f}%在合理范围"
        else:
            debt_score = 3
            debt_explain = f"资产负债率={self.debt_ratio:.1f}%<50%，低负债稳健，+3分"

        quality_detail = f"现金流评分:{cf_score}分({cf_explain}) + 毛利率评分:{gm_score}分({gm_explain}) + 资产负债率评分:{debt_score}分({debt_explain})"
        factors.append({
            "name": "质量分",
            "weight": "20%",
            "raw_score": round(self.quality_score / 0.20, 1) if self.quality_score > 0 else 0,
            "contribution": round(self.quality_score * 0.20, 1),
            "detail": quality_detail
        })

        # 动量分详情
        momentum_raw = max(-10, min(10, self.change_pct))
        factors.append({
            "name": "动量分",
            "weight": "15%",
            "raw_score": round(momentum_raw, 1),
            "contribution": round(self.momentum_score * 0.15, 1),
            "detail": f"当日涨跌幅:{self.change_pct:.2f}%，限制在[-10,10]后:{momentum_raw:.1f}"
        })

        # 风险详情
        risk_items = []
        if self.pe < 0:
            risk_items.append("PE为负(亏损)")
        elif self.pe > 100:
            risk_items.append(f"PE极高({self.pe:.0f})")
        elif self.pe > 50:
            risk_items.append(f"PE偏高({self.pe:.0f})")

        if self.roe < 0:
            risk_items.append("ROE为负")
        elif self.roe < 5:
            risk_items.append(f"ROE偏低({self.roe:.1f}%)")

        if self.net_profit_growth < -50:
            risk_items.append(f"净利润暴跌({self.net_profit_growth:.1f}%)")
        elif self.net_profit_growth < 0:
            risk_items.append(f"净利润下降({self.net_profit_growth:.1f}%)")

        if abs(self.change_pct) > 8:
            risk_items.append(f"高波动({self.change_pct:.1f}%)")

        # 生成总结
        summary_parts = []
        if self.growth_score > 70:
            summary_parts.append("成长性优秀")
        elif self.growth_score > 50:
            summary_parts.append("成长性良好")

        if self.value_score > 70:
            summary_parts.append("价值被低估")
        elif self.value_score > 50:
            summary_parts.append("价值合理")

        if self.quality_score > 70:
            summary_parts.append("盈利质量高")
        elif self.quality_score > 50:
            summary_parts.append("盈利质量中等")

        if self.risk_score < 30:
            summary_parts.append("风险较低")
        elif self.risk_score > 60:
            summary_parts.append("风险较高")

        summary = "，".join(summary_parts) if summary_parts else "综合表现一般"

        return {
            "code": self.code,
            "name": self.name,
            "total_cp": round(self.total_cp, 1),
            "factors": factors,
            "risk": {
                "score": self.risk_score,
                "level": self.get_risk_level(),
                "items": risk_items,
                "adjustment": f"× {1 - (self.risk_score / 100) * 0.10:.2f} (风险调整因子)"
            },
            "data_quality": self.data_quality,
            "summary": f"{self.name}({self.code})战力{round(self.total_cp, 1)}分，{summary}。"
        }

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
            'quality_score': self.quality_score,
            'total_cp': self.total_cp,
            'risk_score': self.risk_score,
            'risk_level': self.get_risk_level(),
            'peg': self.peg,
            'pb': self.pb,
            'gross_margin': self.gross_margin,
            'revenue': self.revenue,
            'cashflow': self.cashflow,
            'debt_ratio': self.debt_ratio,
            'dividend_yield': self.dividend_yield,
            'market_cap': self.market_cap,
            'high': self.high,
            'low': self.low,
            'data_quality': self.data_quality,
            # 板块信息
            'board_type': self.board_type,
            'board_name': self.board_name,
            'can_trade_newbie': self.can_trade_newbie,
            'trade_requirement': self.trade_requirement
        }


class CPEngine:
    """战力计算引擎"""

    def __init__(self):
        self.stocks: List[StockCP] = []

    def add_stock(self, stock: StockCP):
        """添加股票（自动去重）"""
        # 检查是否已存在相同代码
        if any(s.code == stock.code for s in self.stocks):
            return  # 忽略重复添加
        self.stocks.append(stock)

    def calculate_all(self) -> List[StockCP]:
        """计算所有股票的总战力（v14赚钱版）"""
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

        quality_values = [s.quality_score for s in self.stocks]
        max_quality = max(quality_values) if quality_values else 1
        min_quality = min(quality_values) if quality_values else 0
        quality_range = max_quality - min_quality or 1

        # 归一化各因子到0-100范围，然后计算总战力
        for stock in self.stocks:
            # 归一化到0-100
            norm_growth = ((stock.growth_score - min_growth) / growth_range) * 100
            norm_value = ((stock.value_score - min_value) / value_range) * 100
            norm_momentum = ((stock.momentum_score - min_momentum) / momentum_range) * 100
            norm_quality = ((stock.quality_score - min_quality) / quality_range) * 100

            # 更新显示用分数（归一化后的0-100分数）
            stock.growth_score = norm_growth
            stock.value_score = norm_value
            stock.momentum_score = norm_momentum
            stock.quality_score = norm_quality

            # 计算总战力（风险调整后）
            # 基础战力
            base_cp = (
                norm_growth * WEIGHTS['growth'] +
                norm_value * WEIGHTS['value'] +
                norm_quality * WEIGHTS['quality'] +
                norm_momentum * WEIGHTS['momentum']
            )

            # 风险调整因子：低风险股票加权更高
            risk_factor = 1 - (stock.risk_score / 100) * WEIGHTS['risk_penalty']

            # 最终战力 = 基础战力 × 风险调整因子
            stock.total_cp = max(0, base_cp * risk_factor)

        return self.stocks

    def get_top(self, n: int = 50, board: str = None) -> List[StockCP]:
        """获取战力榜TOP N

        Args:
            n: 返回数量
            board: 板块过滤，None表示全部，'main'表示主板，'all'表示全部（包含创业板科创板）
        """
        stocks = self.stocks
        # 板块过滤
        if board == 'main':
            stocks = [s for s in stocks if s.can_trade_newbie]
        elif board is not None and board != 'all':
            stocks = [s for s in stocks if s.board_type == board]

        sorted_stocks = sorted(stocks, key=lambda s: s.total_cp, reverse=True)
        return sorted_stocks[:n]

    def get_bottom(self, n: int = 10, board: str = None) -> List[StockCP]:
        """获取战力榜BOTTOM N（避雷区）

        Args:
            n: 返回数量
            board: 板块过滤，None表示全部，'main'表示主板
        """
        stocks = self.stocks
        # 板块过滤
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
    change_pct: float,
    pb: float = 0,
    gross_margin: float = 0,
    revenue: float = 0,
    cashflow: float = 0,
    debt_ratio: float = 0,
    volume: float = 0,
    amount: float = 0,
    dividend_yield: float = 0,
    market_cap: float = 0,
    high: float = 0,
    low: float = 0,
    data_quality: str = 'low'
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
        change_pct=change_pct,
        pb=pb,
        gross_margin=gross_margin,
        revenue=revenue,
        cashflow=cashflow,
        debt_ratio=debt_ratio,
        volume=volume,
        amount=amount,
        dividend_yield=dividend_yield,
        market_cap=market_cap,
        high=high,
        low=low,
        data_quality=data_quality
    )
