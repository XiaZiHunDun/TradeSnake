"""
风险评估模块 - Risk Analyzer
"""

from datetime import datetime
from typing import List, Dict, Tuple, Optional
from .constants import EARNINGS_SEASON_MONTHS, CONCENTRATION_THRESHOLDS, SMALL_ACCOUNT_THRESHOLD


class KellyCalculator:
    """
    Kelly公式仓位计算器 v18.2

    Kelly公式：f* = (b × p - q) / b = p - q/b
    其中：
    - f* = 最佳下注比例
    - b = 赔率（盈利/亏损比率）
    - p = 获胜概率
    - q = 失败概率 (q = 1-p)

    A股适用改进：
    - 使用历史胜率和盈亏比估算
    - 考虑交易成本影响
    - 提供半Kelly（保守）和全Kelly（激进）两种推荐
    - 最大仓位限制在20%以内避免过度集中
    """

    KELLY_FRACTION = 0.5
    MAX_POSITION_PCT = 20.0
    MIN_TRADE_VALUE = 50000

    @classmethod
    def calculate_win_rate(cls, trades: List[Dict]) -> float:
        if not trades:
            return 0.5
        wins = sum(1 for t in trades if t.get('profit', 0) > 0 or t.get('realized_pnl', 0) > 0)
        return wins / len(trades)

    @classmethod
    def calculate_avg_win_loss(cls, trades: List[Dict]) -> Tuple[float, float, float]:
        profits = [t.get('profit', 0) or t.get('realized_pnl', 0) for t in trades]
        wins = [p for p in profits if p > 0]
        losses = [abs(p) for p in profits if p < 0]
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 1
        if avg_loss == 0:
            avg_loss = 1
        return avg_win, avg_loss, avg_win / avg_loss

    @classmethod
    def calculate_kelly_fraction(cls, win_rate: float, win_loss_ratio: float) -> float:
        if win_rate <= 0 or win_loss_ratio <= 0:
            return 0
        kelly = win_rate - (1 - win_rate) / win_loss_ratio
        return max(0, min(kelly, 1))

    @classmethod
    def get_position_recommendation(
        cls,
        trades: List[Dict] = None,
        win_rate: float = None,
        win_loss_ratio: float = None,
        total_capital: float = 100000,
        risk_preference: str = 'balanced'
    ) -> Dict:
        if trades:
            p = cls.calculate_win_rate(trades)
            _, _, b = cls.calculate_avg_win_loss(trades)
        elif win_rate is not None and win_loss_ratio is not None:
            p = win_rate
            b = win_loss_ratio
        else:
            return {
                'kelly_fraction': 0.20,
                'recommended_position_pct': 10.0,
                'max_position_pct': cls.MAX_POSITION_PCT,
                'reason': '无历史交易数据，使用保守推荐',
                'risk_level': 'low',
                'suggestion': '建议先积累交易历史后再使用Kelly公式'
            }

        kelly_full = cls.calculate_kelly_fraction(p, b)
        if risk_preference == 'conservative':
            kelly_fraction = kelly_full * 0.25
        elif risk_preference == 'aggressive':
            kelly_fraction = kelly_full * 0.75
        else:
            kelly_fraction = kelly_full * cls.KELLY_FRACTION

        recommended_position_pct = min(kelly_fraction * 100, cls.MAX_POSITION_PCT)
        recommended_position_value = total_capital * (recommended_position_pct / 100)
        meets_min_trade = recommended_position_value >= cls.MIN_TRADE_VALUE

        if kelly_fraction >= 0.2:
            risk_level = 'high'
            risk_label = '高风险'
        elif kelly_fraction >= 0.1:
            risk_level = 'medium'
            risk_label = '中等风险'
        else:
            risk_level = 'low'
            risk_label = '低风险'

        suggestions = []
        if kelly_fraction <= 0:
            suggestions.append('胜率或盈亏比不佳，建议观望或减少仓位')
        elif kelly_fraction < 0.05:
            suggestions.append('Kelly比例很低，建议轻仓参与')
        elif kelly_fraction > 0.3:
            suggestions.append('Kelly比例较高，但建议控制仓位不超过20%分散风险')

        return {
            'win_rate': round(p * 100, 1),
            'win_loss_ratio': round(b, 2),
            'kelly_full': round(kelly_full * 100, 1),
            'kelly_fraction': round(kelly_fraction * 100, 1),
            'recommended_position_pct': round(recommended_position_pct, 1),
            'recommended_position_value': round(recommended_position_value, 2),
            'max_position_pct': cls.MAX_POSITION_PCT,
            'risk_level': risk_level,
            'risk_label': risk_label,
            'risk_preference': risk_preference,
            'meets_min_trade': meets_min_trade,
            'reason': f'胜率{p*100:.0f}%×盈亏比{b:.1f}适中',
            'suggestions': suggestions
        }

    @classmethod
    def assess_trade_kelly(cls, from_cp: float, to_cp: float, holding_days: int = 30,
                           trade_cost: float = 0, principal: float = 100000) -> Dict:
        cp_diff = to_cp - from_cp
        expected_return_rate = cp_diff * 0.01
        expected_return = expected_return_rate * principal * (holding_days / 365)
        net_profit = expected_return - trade_cost

        if abs(cp_diff) >= 15:
            win_prob = 0.75 if cp_diff > 0 else 0.35
        elif abs(cp_diff) >= 10:
            win_prob = 0.65 if cp_diff > 0 else 0.40
        elif abs(cp_diff) >= 5:
            win_prob = 0.55 if cp_diff > 0 else 0.45
        else:
            win_prob = 0.50

        if net_profit > 0:
            win_loss_ratio = net_profit / (trade_cost * 0.5) if trade_cost > 0 else 1
        else:
            win_loss_ratio = 0.5

        kelly_full = cls.calculate_kelly_fraction(win_prob, win_loss_ratio)
        kelly_fraction = kelly_full * cls.KELLY_FRACTION
        recommended_pct = min(kelly_fraction * 100, cls.MAX_POSITION_PCT)

        if kelly_fraction <= 0:
            action = 'avoid'
            action_label = '不建议换股'
        elif kelly_fraction < 0.05:
            action = 'cautious'
            action_label = '谨慎换股'
        elif kelly_fraction < 0.15:
            action = 'consider'
            action_label = '可以考虑换股'
        else:
            action = 'recommend'
            action_label = '建议换股'

        return {
            'from_cp': from_cp,
            'to_cp': to_cp,
            'cp_diff': cp_diff,
            'expected_return': round(expected_return, 2),
            'trade_cost': round(trade_cost, 2),
            'net_profit': round(net_profit, 2),
            'win_probability': round(win_prob * 100, 1),
            'win_loss_ratio': round(win_loss_ratio, 2),
            'kelly_full_pct': round(kelly_full * 100, 1),
            'kelly_recommended_pct': round(kelly_fraction * 100, 1),
            'recommended_position_pct': round(recommended_pct, 1),
            'action': action,
            'action_label': action_label,
            'holding_days': holding_days,
            'principal': principal
        }


class RiskAnalyzer:
    """风险评估器"""

    EARNINGS_SEASON_MONTHS = EARNINGS_SEASON_MONTHS
    CONCENTRATION_THRESHOLDS = CONCENTRATION_THRESHOLDS
    SMALL_ACCOUNT_THRESHOLD = SMALL_ACCOUNT_THRESHOLD
    MIN_MEANINGFUL_TRADE = 50000

    @classmethod
    def get_market_cp(cls, stocks: List) -> float:
        """计算市场整体CP"""
        if not stocks:
            return 50
        total_cp = sum(s.total_cp for s in stocks if hasattr(s, 'total_cp'))
        return total_cp / len(stocks) if len(stocks) > 0 else 50

    @classmethod
    def assess_concentration_risk(cls, holdings: List[Dict]) -> Dict:
        """评估仓位集中度风险"""
        if not holdings:
            return {'risk_level': 'none', 'details': [], 'suggestions': []}

        total_cost = sum(h.get('cost_total', 0) for h in holdings)
        if total_cost <= 0:
            return {'risk_level': 'none', 'details': [], 'suggestions': []}

        details = []
        for h in holdings:
            concentration = h.get('cost_total', 0) / total_cost * 100
            details.append({
                'code': h['code'], 'name': h['name'],
                'concentration_pct': round(concentration, 1),
                'risk': 'high' if concentration > cls.CONCENTRATION_THRESHOLDS['high'] else
                        'medium' if concentration > cls.CONCENTRATION_THRESHOLDS['medium'] else 'low'
            })

        max_concentration = max(d.get('concentration_pct', 0) for d in details)

        if max_concentration > cls.CONCENTRATION_THRESHOLDS['high']:
            risk_level = 'high'
            suggestion = f"仓位过于集中！最大仓位占比{max_concentration:.1f}%，建议分散投资"
        elif max_concentration > cls.CONCENTRATION_THRESHOLDS['medium']:
            risk_level = 'medium'
            suggestion = f"仓位集中度偏高，最大仓位占比{max_concentration:.1f}%，建议适当分散"
        elif max_concentration > cls.CONCENTRATION_THRESHOLDS['low']:
            risk_level = 'low'
            suggestion = f"仓位集中度可接受，最大仓位占比{max_concentration:.1f}%"
        else:
            risk_level = 'low'
            suggestion = "仓位分散度良好"

        return {
            'risk_level': risk_level,
            'max_concentration_pct': round(max_concentration, 1),
            'details': details,
            'suggestions': [suggestion] if risk_level != 'low' else []
        }

    @classmethod
    def assess_industry_concentration_risk(cls, holdings: List[Dict]) -> Dict:
        """评估行业集中度风险"""
        if not holdings:
            return {'risk_level': 'none', 'industry_allocation': {}, 'suggestions': []}

        total_cost = sum(h.get('cost_total', 0) for h in holdings)
        if total_cost <= 0:
            return {'risk_level': 'none', 'industry_allocation': {}, 'suggestions': []}

        industry_values = {}
        for h in holdings:
            sector = h.get('sector', '未知')
            if sector not in industry_values:
                industry_values[sector] = 0
            industry_values[sector] += h.get('cost_total', 0)

        industry_allocation = {}
        for sector, value in industry_values.items():
            pct = value / total_cost * 100
            industry_allocation[sector] = {'value': round(value, 2), 'percentage': round(pct, 1), 'stocks': 0}

        for h in holdings:
            sector = h.get('sector', '未知')
            if sector in industry_allocation:
                industry_allocation[sector]['stocks'] += 1

        max_industry_pct = max((v['percentage'] for v in industry_allocation.values()), default=0)
        industry_count = len(industry_allocation)

        if max_industry_pct > 60:
            risk_level = 'high'
            suggestion = f"行业过于集中！单一行业仓位{max_industry_pct:.1f}%，建议分散"
        elif max_industry_pct > 40 or industry_count < 2:
            risk_level = 'medium'
            suggestion = f"行业集中度偏高，最大行业占比{max_industry_pct:.1f}%"
        else:
            risk_level = 'low'
            suggestion = "行业分布良好"

        return {
            'risk_level': risk_level, 'max_industry_pct': round(max_industry_pct, 1),
            'industry_count': industry_count, 'industry_allocation': industry_allocation,
            'suggestions': [suggestion] if risk_level != 'low' else []
        }

    @classmethod
    def assess_liquidity_risk(cls, holdings: List[Dict], avg_volume: float = None) -> Dict:
        """评估流动性风险"""
        if not holdings:
            return {'risk_level': 'low', 'warnings': [], 'suggestions': []}

        total_value = sum(h.get('value_total', 0) for h in holdings)
        if avg_volume is None:
            avg_volume = 10000000

        warnings = []
        suggestions = []

        for h in holdings:
            value = h.get('value_total', 0)
            if value > total_value * 0.3 and value > 5000000:
                warnings.append(f"{h['name']}持仓较大({value/10000:.0f}万)，可能存在流动性风险")
                suggestions.append(f"考虑分批卖出{h['name']}")

        if not warnings:
            return {'risk_level': 'low', 'warnings': [], 'suggestions': []}

        return {'risk_level': 'medium', 'warnings': warnings, 'suggestions': suggestions}

    @classmethod
    def assess_market_risk(cls, market_cp: float, holdings: List[Dict] = None) -> Dict:
        """评估市场系统性风险"""
        if market_cp < 40:
            risk_level = 'high'
            desc = "市场整体CP偏低，系统性风险较高"
        elif market_cp < 50:
            risk_level = 'medium'
            desc = "市场整体CP偏低，谨慎操作"
        else:
            risk_level = 'low'
            desc = "市场整体CP正常"

        suggestions = []
        if holdings:
            avg_holding_cp = sum(h.get('cp', 0) for h in holdings if h.get('cp')) / len(holdings) if holdings else 0
            if avg_holding_cp < market_cp * 0.8:
                suggestions.append(f"持仓CP({avg_holding_cp:.1f})低于市场CP({market_cp:.1f})，建议优化持仓")

        return {'risk_level': risk_level, 'market_cp': round(market_cp, 1), 'description': desc, 'suggestions': suggestions}

    @classmethod
    def is_earnings_season(cls, dt: datetime = None) -> Tuple[bool, str]:
        """检查是否在财报发布期"""
        if dt is None:
            dt = datetime.now()

        month = dt.month

        if month in cls.EARNINGS_SEASON_MONTHS:
            day = dt.day
            if day <= 15:
                return True, f"{month}月是财报发布期，股价波动可能较大，请注意风险"
            elif day <= 25:
                return True, f"{month}月财报密集发布期，持续波动中"
            else:
                return False, ""
        else:
            return False, ""

    @classmethod
    def check_trade_cooldown(cls, db, code: str) -> Dict:
        """检查股票交易冷却状态"""
        cooldown = db.get_trade_cooldown(code)
        return cooldown

    @classmethod
    def assess_small_account_risk(cls, capital: float, trade_amount: float = None) -> Dict:
        """评估小额账户风险"""
        if capital >= cls.SMALL_ACCOUNT_THRESHOLD:
            return {'is_small': False, 'capital': capital, 'warning': None, 'min_recommended_trade': None}

        min_trade = 25000
        warning = f"资金较少({capital:.0f}元)，单次交易佣金最低5元占比过高，建议集中资金做大额交易"

        return {
            'is_small': True, 'capital': capital, 'warning': warning,
            'min_recommended_trade': min_trade, 'commission_impact': f"交易金额 < {min_trade}元时，佣金影响 > 0.02%"
        }

    @classmethod
    def calculate_break_even(cls, cost_price: float, current_price: float) -> Dict:
        """计算解套所需涨幅"""
        if cost_price <= 0 or current_price <= 0:
            return {'is_underwater': False, 'cost_price': cost_price, 'current_price': current_price,
                    'loss_pct': 0, 'break_even_pct': 0, 'can_break_even': True}

        loss_pct = (current_price - cost_price) / cost_price * 100
        is_underwater = loss_pct < 0
        break_even_pct = abs(loss_pct) if is_underwater else 0

        if not is_underwater:
            can_break_even = True
            difficulty = 'already_profitable'
        elif break_even_pct <= 5:
            can_break_even = True
            difficulty = 'easy'
        elif break_even_pct <= 15:
            can_break_even = True
            difficulty = 'medium'
        elif break_even_pct <= 30:
            can_break_even = True
            difficulty = 'hard'
        else:
            can_break_even = False
            difficulty = 'very_hard'

        return {
            'is_underwater': is_underwater, 'cost_price': cost_price, 'current_price': current_price,
            'loss_pct': round(loss_pct, 2), 'break_even_pct': round(break_even_pct, 2),
            'can_break_even': can_break_even, 'difficulty': difficulty,
            'suggestion': cls._get_break_even_suggestion(is_underwater, break_even_pct, difficulty)
        }

    @classmethod
    def _get_break_even_suggestion(cls, is_underwater: bool, break_even_pct: float, difficulty: str) -> str:
        """获取解套建议"""
        if not is_underwater:
            return "已盈利，继续持有"
        if difficulty == 'easy':
            return f"套牢{break_even_pct:.1f}%，解套容易，可考虑补仓"
        elif difficulty == 'medium':
            return f"套牢{break_even_pct:.1f}%，解套需耐心持有或补仓"
        elif difficulty == 'hard':
            return f"套牢{break_even_pct:.1f}%，解套较难，建议止损或等待"
        else:
            return f"套牢{break_even_pct:.1f}%，深套，建议长期持有等待反弹"

    @classmethod
    def find_industry_peers(cls, stock_code: str, sector: str, all_stocks: List) -> List[Dict]:
        """找同行业替代股票"""
        if not sector or sector == '未知':
            return []

        peers = []
        for s in all_stocks:
            if not hasattr(s, 'sector') or not hasattr(s, 'total_cp'):
                continue
            if s.sector == sector and s.code.upper() != stock_code.upper():
                peers.append({
                    'code': s.code, 'name': s.name, 'cp': s.total_cp,
                    'roe': getattr(s, 'roe', 0), 'pe': getattr(s, 'pe', 0),
                    'change_pct': getattr(s, 'change_pct', 0)
                })

        peers.sort(key=lambda x: x['cp'], reverse=True)
        return peers[:10]

    @classmethod
    def generate_risk_report(cls, db, holdings: List[Dict], all_stocks: List,
                            market_cp: float = None, capital: float = None) -> Dict:
        """生成综合风险报告"""
        if market_cp is None:
            market_cp = cls.get_market_cp(all_stocks)

        report = {
            'timestamp': datetime.now().isoformat(),
            'market_cp': round(market_cp, 1),
            'warnings': [], 'suggestions': []
        }

        market_risk = cls.assess_market_risk(market_cp, holdings)
        report['market_risk'] = market_risk
        if market_risk['risk_level'] != 'low':
            report['warnings'].append(market_risk['description'])
        report['suggestions'].extend(market_risk.get('suggestions', []))

        if holdings:
            concentration = cls.assess_concentration_risk(holdings)
            report['concentration_risk'] = concentration
            if concentration['risk_level'] == 'high':
                report['warnings'].append(f"仓位过于集中，最大仓位{concentration['max_concentration_pct']}%")
            report['suggestions'].extend(concentration.get('suggestions', []))

            industry_risk = cls.assess_industry_concentration_risk(holdings)
            report['industry_risk'] = industry_risk
            if industry_risk['risk_level'] == 'high':
                report['warnings'].append(f"行业过于集中，最大行业仓位{industry_risk['max_industry_pct']}%")
            report['suggestions'].extend(industry_risk.get('suggestions', []))

        is_earnings, earnings_warning = cls.is_earnings_season()
        if is_earnings:
            report['earnings_season_warning'] = earnings_warning
            report['warnings'].append(earnings_warning)

        if capital is not None:
            small_account = cls.assess_small_account_risk(capital)
            report['small_account_risk'] = small_account
            if small_account['is_small']:
                report['warnings'].append(small_account['warning'])

        cooldown_statuses = []
        for h in holdings:
            cooldown = cls.check_trade_cooldown(db, h['code'])
            if cooldown.get('on_cooldown'):
                cooldown_statuses.append(cooldown)
                report['suggestions'].append(f"{h['name']}刚交易过，需等待{cooldown['days_remaining']}天冷却期")

        underwater_stocks = []
        for h in holdings:
            if h.get('cost_price') and h.get('current_price'):
                break_even = cls.calculate_break_even(h['cost_price'], h['current_price'])
                if break_even['is_underwater']:
                    underwater_stocks.append({**break_even, 'code': h['code'], 'name': h['name']})
                    if break_even['difficulty'] in ['hard', 'very_hard']:
                        report['warnings'].append(f"{h['name']}深套{break_even['break_even_pct']}%，解套困难")

        report['underwater_stocks'] = underwater_stocks

        industry_swaps = []
        for h in holdings:
            if h.get('cp', 0) < 50:
                peers = cls.find_industry_peers(h['code'], h.get('sector', ''), all_stocks)
                if peers and peers[0]['cp'] > h.get('cp', 0) + 5:
                    industry_swaps.append({
                        'from_code': h['code'], 'from_name': h['name'], 'from_cp': h.get('cp', 0),
                        'to_code': peers[0]['code'], 'to_name': peers[0]['name'], 'to_cp': peers[0]['cp'],
                        'cp_improvement': peers[0]['cp'] - h.get('cp', 0), 'peers': peers[:3]
                    })

        report['industry_swaps'] = industry_swaps

        high_risk_count = sum(1 for w in report['warnings'] if '深套' in w or '过于集中' in w or '系统性' in w)
        if high_risk_count >= 3:
            report['overall_risk_level'] = 'high'
        elif len(report['warnings']) >= 2:
            report['overall_risk_level'] = 'medium'
        else:
            report['overall_risk_level'] = 'low'

        return report
