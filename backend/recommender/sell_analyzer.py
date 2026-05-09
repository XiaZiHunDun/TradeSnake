"""
卖出分析器 - Sell Analyzer
=========================
职责：分析持仓卖出的机会（止盈/止损/调仓）
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from backend.engine import StockCP


@dataclass
class SellSignal:
    """卖出信号"""
    stock: StockCP
    holding_quantity: int  # 持仓数量
    cost_price: float  # 成本价
    current_price: float  # 当前价
    unrealized_pnl: float  # 浮动盈亏（元）
    unrealized_pnl_pct: float  # 盈亏比例（%）
    sell_reason: str  # 卖出原因
    market_mode: str  # 大盘模式
    action: str  # 建议：sell now/wait/don't sell
    action_label: str  # 行动标签
    action_color: str  # 颜色
    next_steps: str  # 后续建议
    urgency: int  # 紧急程度 1-3


class SellAnalyzer:
    """卖出分析器"""

    # 卖出原因
    SELL_REASONS = {
        'profit_taking': '止盈',
        'stop_loss': '止损',
        'rebalance': '调仓',
        'risk_avoid': '风险规避',
        'momentum_weakening': '动量减弱',
        'sector_rotation': '板块轮动'
    }

    # 决策阈值（与 RiskManager 风控标准对齐：TS=-8%, SL=-7%）
    PROFIT_TAKING_THRESHOLD = 0.20  # 盈利>20%止盈
    STOP_LOSS_THRESHOLD = -0.10  # 亏损>10%建议止损（RiskManager 在-7%自动止损，此处作为提前预警）
    CAUTIOUS_THRESHOLD = 0.10  # 盈利>10%但大盘弱

    @classmethod
    def analyze_sell_opportunity(
        cls,
        holding: Dict,
        market_mode: str = 'normal'
    ) -> SellSignal:
        """分析卖出机会

        Args:
            holding: 持仓信息，包含：
                - stock: StockCP
                - quantity: 持仓数量
                - cost_price: 成本价
            market_mode: 大盘模式 (normal/defensive/crisis)
        """
        stock = holding.get('stock')
        quantity = holding.get('quantity', 0)
        cost_price = holding.get('cost_price', 0)
        current_price = stock.price

        # 1. 计算盈亏
        unrealized_pnl = (current_price - cost_price) * quantity
        unrealized_pnl_pct = (current_price - cost_price) / cost_price if cost_price > 0 else 0

        # 2. 判断卖出原因
        sell_reason = cls._determine_sell_reason(unrealized_pnl_pct, market_mode)

        # 3. 决策
        action, urgency = cls._make_sell_decision(unrealized_pnl_pct, market_mode)

        # 4. 后续建议
        next_steps = cls._suggest_next_steps(stock, market_mode, action)

        # 5. 标签和颜色
        action_label, action_color = cls._get_action_label_color(action)

        return SellSignal(
            stock=stock,
            holding_quantity=quantity,
            cost_price=cost_price,
            current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct * 100,
            sell_reason=cls.SELL_REASONS.get(sell_reason, sell_reason),
            market_mode=market_mode,
            action=action,
            action_label=action_label,
            action_color=action_color,
            next_steps=next_steps,
            urgency=urgency
        )

    @classmethod
    def get_sell_signals(
        cls,
        holdings: List[Dict],
        market_mode: str = 'normal'
    ) -> List[Dict]:
        """获取持仓卖出信号列表

        Args:
            holdings: 持仓列表
            market_mode: 大盘模式
        """
        signals = []

        for holding in holdings:
            signal = cls.analyze_sell_opportunity(holding, market_mode)
            signals.append(cls._to_dict(signal))

        # 按紧急程度和盈亏排序
        # 亏损严重且紧急的排在前面
        signals.sort(key=lambda x: (x['urgency'], x['unrealized_pnl_pct']), reverse=True)
        return signals

    @classmethod
    def _determine_sell_reason(cls, pnl_pct: float, market_mode: str) -> str:
        """判断卖出原因"""
        if pnl_pct > cls.PROFIT_TAKING_THRESHOLD:
            return 'profit_taking'
        elif pnl_pct < cls.STOP_LOSS_THRESHOLD:
            return 'stop_loss'
        elif market_mode in ('defensive', 'crisis') and pnl_pct > cls.CAUTIOUS_THRESHOLD:
            return 'risk_avoid'
        else:
            return 'rebalance'

    @classmethod
    def _make_sell_decision(cls, pnl_pct: float, market_mode: str) -> tuple:
        """做出卖出决策

        Returns:
            (action, urgency)

        注意：SellAnalyzer 建议阈值比 RiskManager 实盘风控（SL=-7%, TS=-8%）更保守，
        作为提前预警。实际自动止损由 RiskManager 执行。
        """
        # 大盘危机，强烈建议减仓
        if market_mode == 'crisis':
            if pnl_pct < -0.07:  # 与 RiskManager SL=-7% 对齐
                return 'sell now', 3
            elif pnl_pct < 0:
                return 'sell now', 2
            elif pnl_pct < 0.10:
                return 'wait', 1
            else:
                return 'sell now', 2

        # 大盘防御，谨慎操作
        if market_mode == 'defensive':
            if pnl_pct > cls.PROFIT_TAKING_THRESHOLD:
                return 'sell now', 2
            elif pnl_pct < -0.08:  # 介于 SL=-7% 和 TS=-8% 之间
                return 'sell now', 3
            elif pnl_pct < -0.05:
                return 'wait', 2
            elif pnl_pct > 0.05:
                return 'wait', 1
            else:
                return "don't sell", 0

        # 大盘正常
        if pnl_pct > cls.PROFIT_TAKING_THRESHOLD:
            return 'sell now', 2
        elif pnl_pct < cls.STOP_LOSS_THRESHOLD:
            return 'sell now', 3
        elif pnl_pct < -0.05:
            return 'wait', 2
        elif pnl_pct > 0.10:
            return 'wait', 1
        else:
            return "don't sell", 0

    @classmethod
    def _suggest_next_steps(cls, stock: StockCP, market_mode: str, action: str) -> str:
        """建议后续步骤"""
        if action == "don't sell":
            return "继续持有，等待机会"

        if action == 'wait':
            if market_mode in ('defensive', 'crisis'):
                return "建议等待大盘企稳后再操作"
            else:
                return "等待更好的卖点"

        # sell now
        if market_mode == 'crisis':
            return "卖出后持有现金，等待大盘企稳"
        elif market_mode == 'defensive':
            return "卖出后持有现金，关注低估机会"
        else:
            return "卖出后可考虑换入战力更高的股票"

    @classmethod
    def _get_action_label_color(cls, action: str) -> tuple:
        """获取行动标签和颜色"""
        labels = {
            'sell now': ('建议卖出', 'red'),
            'wait': ('继续持有', 'yellow'),
            "don't sell": ('坚定持有', 'green')
        }
        return labels.get(action, ('未知', 'gray'))

    @classmethod
    def _to_dict(cls, signal: SellSignal) -> Dict:
        """转换为字典格式"""
        return {
            'code': signal.stock.code,
            'name': signal.stock.name,
            'quantity': signal.holding_quantity,
            'cost_price': round(signal.cost_price, 2),
            'current_price': round(signal.current_price, 2),
            'unrealized_pnl': round(signal.unrealized_pnl, 2),
            'unrealized_pnl_pct': round(signal.unrealized_pnl_pct, 2),
            'sell_reason': signal.sell_reason,
            'market_mode': signal.market_mode,
            'action': signal.action,
            'action_label': signal.action_label,
            'action_color': signal.action_color,
            'urgency': signal.urgency,
            'next_steps': signal.next_steps,
            'prompt': cls._generate_prompt(signal)
        }

    @classmethod
    def _generate_prompt(cls, signal: SellSignal) -> str:
        """生成卖出建议文本"""
        stock = signal.stock
        pnl_color = '🔴' if signal.unrealized_pnl < 0 else '🟢'

        prompt = f"""【{stock.name}（{stock.code}）】{pnl_color}

持仓：{signal.holding_quantity}股
成本价：{signal.cost_price:.2f}元
当前价：{signal.current_price:.2f}元

盈亏：{signal.unrealized_pnl:+.2f}元（{signal.unrealized_pnl_pct:+.1f}%）

卖出原因：{signal.sell_reason}
大盘状态：{signal.market_mode}

建议：{signal.action_label}
紧急程度：{'🔴' * signal.urgency if signal.urgency > 0 else '✅'}

后续建议：{signal.next_steps}
"""
        return prompt
