"""
买入分析器 - Buy Analyzer
=========================
职责：分析空仓/轻仓直接买入的机会
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from backend.engine import StockCP, KellyCalculator


@dataclass
class BuySignal:
    """买入信号

    Attributes:
        stock: 股票战力数据
        kelly_position: Kelly建议仓位比例（%）
        position_amount: 建议买入金额（元）
        shares: 建议买入股数（100整数倍）
        entry_price: 建议买入价
        stop_loss: 止损价（-5%）
        take_profit: 止盈价（+20%）
        risk_level: risk/warning/acceptable
        buy_strength: 买入强度 1-3星
        reasons: 买入理由
        warnings: 风险提示
        breakeven_days: 回本天数
        # v19.8 预测融合字段
        predicted_gain_5d: 预测5日涨幅（%）
        up_probability_5d: 5日上涨概率（0-1）
        prediction_confidence: 预测置信度（0-1）
        fused_score: 融合得分
    """
    stock: StockCP
    kelly_position: float  # Kelly建议仓位比例（%）
    position_amount: float  # 建议买入金额（元）
    shares: int  # 建议买入股数（100整数倍）
    entry_price: float  # 建议买入价
    stop_loss: float  # 止损价（-5%）
    take_profit: float  # 止盈价（+20%）
    risk_level: str  # risk/warning/acceptable
    buy_strength: int  # 买入强度 1-3星
    reasons: List[str]  # 买入理由
    warnings: List[str]  # 风险提示
    breakeven_days: int  # 回本天数
    # v19.8 预测融合字段
    predicted_gain_5d: float = 0  # 预测5日涨幅（%）
    up_probability_5d: float = 0  # 5日上涨概率（0-1）
    prediction_confidence: float = 0  # 预测置信度（0-1）
    fused_score: float = 0  # 融合得分


class BuyAnalyzer:
    """买入分析器

    使用engine.risk_analyzer.KellyCalculator进行仓位计算
    """

    # 止损止盈
    STOP_LOSS_PCT = 0.05  # -5%止损
    TAKE_PROFIT_PCT = 0.20  # +20%止盈

    @classmethod
    def analyze_buy_opportunity(
        cls,
        stock: StockCP,
        principal: float,
        max_position_pct: float = 20.0,
        win_rate: float = 0.55,
        win_loss_ratio: float = 1.5
    ) -> BuySignal:
        """分析买入机会

        Args:
            stock: 股票
            principal: 本金
            max_position_pct: 最大仓位比例
            win_rate: 胜率（默认0.55）
            win_loss_ratio: 盈亏比（默认1.5）
        """
        # 1. 风险检查（ST、涨跌停、停牌）
        if not cls._is_buyable(stock):
            return cls._blocked_signal(stock, "风险检查未通过")

        # 2. Kelly仓位计算（使用engine的KellyCalculator）
        kelly = KellyCalculator.calculate_kelly_fraction(win_rate, win_loss_ratio)
        safe_kelly = kelly * KellyCalculator.KELLY_FRACTION
        position_pct = min(safe_kelly, max_position_pct / 100)

        position_amount = principal * position_pct
        shares = cls._round_to_lot(position_amount / stock.price, stock.price)

        # 3. 止损止盈
        stop_loss = stock.price * (1 - cls.STOP_LOSS_PCT)
        take_profit = stock.price * (1 + cls.TAKE_PROFIT_PCT)

        # 4. 买入理由
        reasons = cls._generate_buy_reasons(stock)
        warnings = cls._generate_buy_warnings(stock)

        # 5. 回本天数估算
        breakeven_days = cls._estimate_breakeven_days(stock, shares, position_amount)

        # 6. 买入强度
        buy_strength = cls._calculate_buy_strength(position_pct * 100)

        # 7. 风险等级
        risk_level = cls._assess_risk_level(stock)

        return BuySignal(
            stock=stock,
            kelly_position=position_pct * 100,
            position_amount=position_amount,
            shares=shares,
            entry_price=stock.price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_level=risk_level,
            buy_strength=buy_strength,
            reasons=reasons,
            warnings=warnings,
            breakeven_days=breakeven_days
        )

    @classmethod
    def get_buy_signals(
        cls,
        stocks: List[StockCP],
        principal: float,
        risk_preference: str = 'balanced',
        limit: int = 10
    ) -> List[Dict]:
        """获取买入信号列表

        Args:
            stocks: 候选股票列表
            principal: 本金
            risk_preference: 风险偏好
            limit: 返回数量
        """
        signals = []

        for stock in stocks:
            signal = cls.analyze_buy_opportunity(stock, principal)

            # 根据风险偏好过滤
            if risk_preference == 'conservative' and signal.risk_level == 'risk':
                continue
            elif risk_preference == 'balanced' and signal.risk_level in ('risk', 'warning'):
                # 平衡型只接受 acceptable 和 warning
                pass

            signals.append(cls._to_dict(signal))

        # 按买入强度排序
        signals.sort(key=lambda x: x['buy_strength'], reverse=True)
        return signals[:limit]

    @classmethod
    def _is_buyable(cls, stock: StockCP) -> bool:
        """检查是否可以买入"""
        # ST股（使用is_st属性）
        if getattr(stock, 'is_st', False):
            return False

        # 涨停
        if stock.is_limit_up:
            return False

        # 停牌
        if getattr(stock, 'is_suspended', False):
            return False

        # 价格无效
        if stock.price <= 0:
            return False

        return True

    @classmethod
    def _blocked_signal(cls, stock: StockCP, reason: str) -> BuySignal:
        """返回被阻止的信号"""
        return BuySignal(
            stock=stock,
            kelly_position=0,
            position_amount=0,
            shares=0,
            entry_price=stock.price,
            stop_loss=0,
            take_profit=0,
            risk_level='risk',
            buy_strength=0,
            reasons=[],
            warnings=[reason],
            breakeven_days=999,
            predicted_gain_5d=0,
            up_probability_5d=0,
            prediction_confidence=0,
            fused_score=0
        )

    @classmethod
    def _round_to_lot(cls, amount: float, price: float) -> int:
        """按手取整（每手=100股）"""
        if price <= 0:
            return 0
        shares = int(amount / price / 100) * 100
        if shares == 0:
            return 0  # 金额不足以买1手
        return max(100, shares)  # 最小买入1手

    @classmethod
    def _generate_buy_reasons(cls, stock: StockCP) -> List[str]:
        """生成买入理由"""
        reasons = []

        if stock.growth_score > 80:
            reasons.append(f"成长分{stock.growth_score:.0f}，市场Top")
        if stock.value_score > 80:
            reasons.append(f"价值分{stock.value_score:.0f}，估值有优势")
        if stock.quality_score > 80:
            reasons.append(f"质量分{stock.quality_score:.0f}，基本面优秀")
        if stock.momentum_score > 70:
            reasons.append(f"动量分{stock.momentum_score:.0f}，趋势向上")

        if stock.roe > 15:
            reasons.append(f"ROE {stock.roe:.1f}%，盈利能力强劲")
        if 0 < stock.pe < 20:
            reasons.append(f"PE {stock.pe:.1f}，估值合理")

        return reasons or ["战力综合得分较高"]

    @classmethod
    def _generate_buy_warnings(cls, stock: StockCP) -> List[str]:
        """生成风险提示"""
        warnings = []

        if stock.risk_score > 70:
            warnings.append(f"风险分{stock.risk_score:.0f}偏高，波动较大")

        volatility = getattr(stock, 'volatility_20d', 0)
        if volatility > 8:
            warnings.append(f"20日波动率{volatility:.1f}%偏高")

        # 流动性
        avg_amount = getattr(stock, 'avg_daily_amount_20d', 0)
        if avg_amount > 0 and avg_amount < 10000000:
            warnings.append(f"日均成交额{avg_amount/10000000:.1f}千万，流动性偏低")

        if stock.pe < 0:
            warnings.append("当前处于亏损状态")

        return warnings

    @classmethod
    def _estimate_breakeven_days(cls, stock: StockCP, shares: int, position_amount: float) -> int:
        """估算回本天数"""
        if shares <= 0 or position_amount <= 0:
            return 999

        # 假设每日预期收益为战力分对应的收益率
        # 简化：用change_pct作为日均收益估计
        daily_return = abs(stock.change_pct / 100) if stock.change_pct != 0 else 0.001
        if daily_return <= 0:
            daily_return = 0.001  # 默认0.1%日收益

        daily_profit = position_amount * daily_return
        if daily_profit <= 0:
            return 999

        # 回本天数 = 交易成本 / 日收益
        # 简化估算：成本约为0.3%
        trade_cost = position_amount * 0.003
        breakeven = int(trade_cost / daily_profit)

        return min(breakeven, 999)

    @classmethod
    def _calculate_buy_strength(cls, position_pct: float) -> int:
        """计算买入强度（1-3星）"""
        if position_pct > 15:
            return 3  # ⭐⭐⭐ 强烈买入
        elif position_pct > 8:
            return 2  # ⭐⭐ 建议买入
        elif position_pct > 3:
            return 1  # ⭐ 谨慎买入
        else:
            return 0  # 不建议

    @classmethod
    def _assess_risk_level(cls, stock: StockCP) -> str:
        """评估风险等级"""
        if stock.risk_score > 70:
            return 'risk'
        elif stock.risk_score > 50:
            return 'warning'
        else:
            return 'acceptable'

    @classmethod
    def _to_dict(cls, signal: BuySignal) -> Dict:
        """转换为字典格式"""
        return {
            'code': signal.stock.code,
            'name': signal.stock.name,
            'total_cp': round(signal.stock.total_cp, 1),
            'kelly_position': round(signal.kelly_position, 2),
            'position_amount': round(signal.position_amount, 2),
            'shares': signal.shares,
            'entry_price': round(signal.entry_price, 2),
            'stop_loss': round(signal.stop_loss, 2),
            'take_profit': round(signal.take_profit, 2),
            'buy_strength': signal.buy_strength,
            'risk_level': signal.risk_level,
            'reasons': signal.reasons,
            'warnings': signal.warnings,
            'breakeven_days': signal.breakeven_days,
            # v19.8 预测融合字段
            'predicted_gain_5d': round(signal.predicted_gain_5d, 2),
            'up_probability_5d': round(signal.up_probability_5d, 3),
            'prediction_confidence': round(signal.prediction_confidence, 3),
            'fused_score': round(signal.fused_score, 4),
            'prompt': cls._generate_prompt(signal)
        }

    @classmethod
    def _generate_prompt(cls, signal: BuySignal) -> str:
        """生成买入建议文本"""
        stock = signal.stock
        strength_stars = '⭐' * signal.buy_strength if signal.buy_strength > 0 else '⚠️'

        prompt = f"""【{stock.name}（{stock.code}）】{strength_stars}

战力：{stock.total_cp:.1f} | 成长：{stock.growth_score:.0f} | 价值：{stock.value_score:.0f}

建议买入：
- 仓位：{signal.kelly_position:.1f}%
- 金额：{signal.position_amount:.0f}元
- 股数：{signal.shares}股
- 价格：{signal.entry_price:.2f}元

止损：{signal.stop_loss:.2f}元（-5%）
止盈：{signal.take_profit:.2f}元（+20%）

理由：{'；'.join(signal.reasons)}

风险：{'；'.join(signal.warnings) if signal.warnings else '无'}
"""
        return prompt
