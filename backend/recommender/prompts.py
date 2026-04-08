"""
推荐理由生成器 - Prompts Generator
===================================
职责：基于规则引擎生成推荐理由
"""

from typing import List, Dict
from backend.engine.cp_engine import StockCP


class PromptsGenerator:
    """推荐理由生成器"""

    @classmethod
    def generate_stock_prompt(cls, stock: StockCP, all_stocks: List[StockCP] = None) -> str:
        """生成单股推荐文本

        Args:
            stock: 股票
            all_stocks: 全量股票（用于计算百分位）
        """
        highlights = cls.generate_highlights(stock, all_stocks)
        risk_warnings = cls.generate_risk_warnings(stock)
        technical_signal = cls.generate_technical_signal(stock)

        prompt = f"""{stock.name}（{stock.code}）量化分析

【战力概览】
总战力：{stock.total_cp:.1f}
成长分：{stock.growth_score:.1f}
价值分：{stock.value_score:.1f}
质量分：{stock.quality_score:.1f}
动量分：{stock.momentum_score:.1f}
风险分：{stock.risk_score:.1f}（{stock.get_risk_level()}）

【核心亮点】
{'；'.join(highlights) if highlights else '战力综合表现良好'}

【基本面】
市盈率（PE）：{stock.pe:.1f}
净资产收益率（ROE）：{stock.roe:.1f}%
净利润增长：{stock.net_profit_growth:.1f}%
营收增长：{stock.revenue_growth:.1f}%

【技术面】
{technical_signal}

【风险提示】
{'；'.join(risk_warnings) if risk_warnings else '市场有风险，投资需谨慎'}
"""
        return prompt

    @classmethod
    def generate_highlights(cls, stock: StockCP, all_stocks: List[StockCP] = None) -> List[str]:
        """生成核心亮点

        规则引擎：
        1. 成长分Top X%
        2. ROE连续X年>15%
        3. 行业PE低估
        4. 动量增强
        """
        highlights = []

        # 成长分百分位
        if all_stocks and len(all_stocks) > 5:
            growth_scores = [s.growth_score for s in all_stocks]
            percentile = cls._calculate_percentile(stock.growth_score, growth_scores)
            if percentile >= 80:
                highlights.append(f"成长分处于市场Top {100-percentile:.0f}%")
        elif stock.growth_score > 80:
            highlights.append(f"成长分{stock.growth_score:.0f}，表现优异")

        # 价值分
        if stock.value_score > 80:
            highlights.append(f"价值分{stock.value_score:.0f}，估值有优势")

        # 质量分
        if stock.quality_score > 80:
            highlights.append(f"质量分{stock.quality_score:.0f}，基本面优秀")

        # ROE
        if stock.roe > 15:
            highlights.append(f"ROE {stock.roe:.1f}%，盈利能力强劲")
        elif stock.roe > 10:
            highlights.append(f"ROE {stock.roe:.1f}%，表现良好")

        # PE估值
        if 0 < stock.pe < 15:
            highlights.append(f"PE {stock.pe:.1f}，估值偏低")
        elif 0 < stock.pe < 25:
            highlights.append(f"PE {stock.pe:.1f}，估值合理")

        # 行业PE相对估值
        sector_pe_ratio = getattr(stock, 'sector_pe_ratio', None)
        if sector_pe_ratio and sector_pe_ratio < 0.8:
            highlights.append(f"行业PE相对低估{(1-sector_pe_ratio)*100:.0f}%")

        # 动量
        if stock.momentum_score > 80:
            highlights.append(f"动量分{stock.momentum_score:.0f}，趋势向上")

        return highlights

    @classmethod
    def generate_risk_warnings(cls, stock: StockCP) -> List[str]:
        """生成风险提示

        规则引擎：
        1. 风险分>70
        2. 波动率>8%
        3. 财报季（3-4/8-9月）
        4. 流动性不足
        5. PE为负
        """
        warnings = []

        if stock.risk_score > 70:
            warnings.append(f"风险分{stock.risk_score:.0f}偏高，波动较大")
        elif stock.risk_score > 50:
            warnings.append(f"风险分{stock.risk_score:.0f}，需要注意")

        # 波动率
        volatility = getattr(stock, 'volatility_20d', 0)
        if volatility > 8:
            warnings.append(f"20日波动率{volatility:.1f}%偏高")
        elif volatility > 5:
            warnings.append(f"20日波动率{volatility:.1f}%适中")

        # 财报季
        import datetime
        current_month = datetime.datetime.now().month
        if current_month in [3, 4, 8, 9]:
            warnings.append("临近年报/中报披露期，业绩存在不确定性")

        # 流动性
        avg_amount = getattr(stock, 'avg_daily_amount_20d', 0)
        if avg_amount > 0 and avg_amount < 10000000:
            warnings.append(f"日均成交额{avg_amount/10000000:.1f}千万，流动性偏低")

        # PE为负
        if stock.pe < 0:
            warnings.append("当前处于亏损状态")
        elif stock.pe > 100:
            warnings.append(f"PE {stock.pe:.1f}，估值偏高")

        return warnings

    @classmethod
    def generate_technical_signal(cls, stock: StockCP) -> str:
        """生成技术信号"""
        signals = []

        # 涨跌幅
        if stock.change_pct > 5:
            signals.append(f"今日涨幅{stock.change_pct:.1f}%，表现强势")
        elif stock.change_pct > 0:
            signals.append(f"今日上涨{stock.change_pct:.1f}%")
        elif stock.change_pct < -5:
            signals.append(f"今日跌幅{stock.change_pct:.1f}%，注意风险")
        elif stock.change_pct < 0:
            signals.append(f"今日下跌{stock.change_pct:.1f}%")

        # 换手率
        turnover = getattr(stock, 'turnover_rate', 0)
        if turnover > 0.05:
            signals.append(f"换手率{turnover*100:.1f}%，交易活跃")
        elif turnover < 0.01:
            signals.append(f"换手率{turnover*100:.1f}%，交易清淡")

        return signals[0] if signals else "技术面无明显信号"

    @classmethod
    def generate_swap_prompt(
        cls,
        from_stock: StockCP,
        to_stock: StockCP,
        cp_improvement: float,
        net_profit: float,
        trade_cost: float,
        breakeven_days: int
    ) -> str:
        """生成换股建议文本"""
        prompt = f"""从 {from_stock.name}（{from_stock.code}）换股到 {to_stock.name}（{to_stock.code}）

【战力对比】
原始战力：{from_stock.total_cp:.1f}
目标战力：{to_stock.total_cp:.1f}
战力提升：+{cp_improvement:.1f}

【成本分析】
交易成本：{trade_cost:.2f}元
净收益估算：{net_profit:.2f}元
回本天数：{breakeven_days}天

【后续建议】
"""
        if net_profit > 0:
            prompt += "战力提升明显，可以考虑换股\n"
        elif net_profit > -trade_cost * 0.5:
            prompt += "战力有提升但幅度有限，建议谨慎\n"
        else:
            prompt += "战力提升不足以覆盖成本，不建议换股\n"

        return prompt

    @classmethod
    def _calculate_percentile(cls, value: float, values: List[float]) -> float:
        """计算百分位"""
        if not values:
            return 50
        sorted_values = sorted(values)
        rank = sum(1 for v in sorted_values if v < value)
        return (rank / len(sorted_values)) * 100


# 便捷函数
def generate_stock_prompt(stock: StockCP, all_stocks: List[StockCP] = None) -> str:
    """生成单股推荐文本"""
    return PromptsGenerator.generate_stock_prompt(stock, all_stocks)


def generate_highlights(stock: StockCP, all_stocks: List[StockCP] = None) -> List[str]:
    """生成核心亮点"""
    return PromptsGenerator.generate_highlights(stock, all_stocks)


def generate_risk_warnings(stock: StockCP) -> List[str]:
    """生成风险提示"""
    return PromptsGenerator.generate_risk_warnings(stock)


def generate_swap_prompt(
    from_stock: StockCP,
    to_stock: StockCP,
    cp_improvement: float,
    net_profit: float,
    trade_cost: float,
    breakeven_days: int
) -> str:
    """生成换股建议文本"""
    return PromptsGenerator.generate_swap_prompt(
        from_stock, to_stock, cp_improvement, net_profit, trade_cost, breakeven_days
    )
