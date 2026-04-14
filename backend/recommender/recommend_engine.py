"""
推荐引擎 - Recommend Engine
==========================
支持三大场景：换股、纯买入、纯卖出
"""

from typing import List, Dict, Optional, Set
from backend.engine import CPEngine, StockCP, TradeDecision

from .filters import StockFilter
from .swap_calculator import SwapCalculator
from .buy_analyzer import BuyAnalyzer
from .sell_analyzer import SellAnalyzer
from .fusion import PredictionFusion, FusionResult
from .prompts import generate_stock_prompt


class RecommenderCallback:
    """接收 stock_selector 的池状态变化通知 v18.5

    用于 RecommenderEngine 与 StockSelector 的联动：
    - 池变化时更新推荐候选池
    - 股票晋级到核心池时优先推荐
    - 财务预警时从推荐移除，加入监控
    """

    def __init__(self, engine: 'RecommendEngine'):
        self._engine = engine
        # 推荐候选池
        self.candidate_pool: List[str] = []
        # 优先候选集
        self.priority_candidates: Set[str] = set()
        # 监控列表 {code: [warnings]}
        self.watchlist: Dict[str, List[str]] = {}

    def on_pool_changed(self, tier: 'PoolTier', added: List[str], removed: List[str]) -> None:
        """池变化时更新推荐候选池

        Args:
            tier: 池层级
            added: 新加入的股票代码列表
            removed: 移除的股票代码列表
        """
        from backend.stock_selector.enums import PoolTier

        # 只处理核心池和活跃池
        if tier not in [PoolTier.CORE, PoolTier.ACTIVE]:
            return

        # 新纳入的加入推荐候选池
        for code in added:
            if code not in self.candidate_pool:
                self.candidate_pool.append(code)

        # 移除的从推荐候选池移除
        self.candidate_pool = [c for c in self.candidate_pool if c not in removed]

        # 从优先候选集中移除
        for code in removed:
            self.priority_candidates.discard(code)

    def on_stock_upgraded_to_core(self, code: str) -> None:
        """股票晋级到核心池 → 优先推荐

        Args:
            code: 股票代码
        """
        self.priority_candidates.add(code)
        # 如果不在候选池中，添加进去
        if code not in self.candidate_pool:
            self.candidate_pool.append(code)

    def on_financial_warning(self, code: str, warnings: List[str]) -> None:
        """财务预警时 → 从推荐移除，加入监控

        Args:
            code: 股票代码
            warnings: 预警信息列表
        """
        # 从候选池移除
        self.candidate_pool = [c for c in self.candidate_pool if c != code]
        # 从优先候选集移除
        self.priority_candidates.discard(code)
        # 加入监控列表
        self.watchlist[code] = warnings

    def get_candidate_pool(self) -> List[str]:
        """获取当前候选池"""
        return self.candidate_pool.copy()

    def get_priority_candidates(self) -> Set[str]:
        """获取优先候选集"""
        return self.priority_candidates.copy()

    def get_watchlist(self) -> Dict[str, List[str]]:
        """获取监控列表"""
        return self.watchlist.copy()


class RecommendEngine:
    """智能推荐引擎

    支持三大操作场景：
    1. 换股：卖出A，买入B
    2. 纯买入：空仓/轻仓直接买入
    3. 纯卖出：持仓止盈/止损卖出
    """

    def __init__(self):
        self.engine = CPEngine()
        self.stock_filter = StockFilter()
        self.swap_calculator = SwapCalculator()

    # ==================== 换股建议 ====================

    def get_swap_suggestions(
        self,
        holdings: List[Dict],
        all_stocks: List[StockCP],
        principal: float = 100000,
        holding_days: int = 30
    ) -> List[Dict]:
        """获取换股建议列表

        Args:
            holdings: 持仓列表 [{code, name, cp, quantity, cost_price}, ...]
            all_stocks: 全量股票列表
            principal: 本金
            holding_days: 持有天数

        Returns:
            换股建议列表
        """
        suggestions = []

        for holding in holdings:
            code = holding.get('code')
            current_cp = holding.get('cp', 0)

            if current_cp <= 0:
                continue

            holding_cp = current_cp

            for stock in all_stocks:
                if stock.code == code:
                    continue
                if stock.total_cp <= holding_cp:
                    continue

                # 过滤
                if not self._is_swappable(stock):
                    continue

                decision = TradeDecision.should_swap(
                    holding_cp, stock.total_cp, principal, holding_days
                )

                if decision['action'] in ('swap', 'strong_buy'):
                    # 计算回本天数
                    breakeven = self.swap_calculator.calculate_breakeven_days(
                        decision['trade_cost'],
                        stock,
                        principal
                    )

                    suggestions.append({
                        'from_code': code,
                        'from_name': holding.get('name', ''),
                        'from_cp': round(holding_cp, 1),
                        'to_code': stock.code,
                        'to_name': stock.name,
                        'to_cp': round(stock.total_cp, 1),
                        'cp_improvement': round(stock.total_cp - holding_cp, 1),
                        'net_profit': round(decision['net_profit'], 2),
                        'trade_cost': round(decision['trade_cost'], 2),
                        'breakeven_days': breakeven,
                        'action_level': decision['action_level'],
                        'action_label': decision['action_label']
                    })

        suggestions.sort(key=lambda x: x['cp_improvement'], reverse=True)
        return suggestions[:10]

    def _is_swappable(self, stock: StockCP) -> bool:
        """检查是否可换入"""
        # ST股（使用is_st属性）
        if getattr(stock, 'is_st', False):
            return False

        # 涨停（不能买入）
        if stock.is_limit_up:
            return False

        # 停牌
        if getattr(stock, 'is_suspended', False):
            return False

        return True

    # ==================== 纯买入分析 ====================

    def get_buy_signals(
        self,
        stocks: List[StockCP],
        principal: float,
        risk_preference: str = 'balanced',
        limit: int = 10,
        use_fusion: bool = True
    ) -> List[Dict]:
        """获取买入信号列表（空仓/轻仓入场）

        Args:
            stocks: 候选股票列表
            principal: 本金
            risk_preference: 风险偏好 (conservative/balanced/aggressive)
            limit: 返回数量
            use_fusion: 是否使用预测融合（v19.8）

        Returns:
            买入信号列表
        """
        if not use_fusion:
            return BuyAnalyzer.get_buy_signals(
                stocks=stocks,
                principal=principal,
                risk_preference=risk_preference,
                limit=limit
            )

        # v19.8: 使用预测融合
        return self._get_buy_signals_with_fusion(
            stocks=stocks,
            principal=principal,
            risk_preference=risk_preference,
            limit=limit
        )

    def _get_buy_signals_with_fusion(
        self,
        stocks: List[StockCP],
        principal: float,
        risk_preference: str = 'balanced',
        limit: int = 10
    ) -> List[Dict]:
        """获取买入信号列表（使用预测融合） v19.8

        Args:
            stocks: 候选股票列表
            principal: 本金
            risk_preference: 风险偏好
            limit: 返回数量

        Returns:
            融合后的买入信号列表
        """
        # 1. 获取最新预测数据
        codes = [s.code for s in stocks]
        gain_preds, prob_preds = PredictionFusion.get_latest_predictions(codes)

        # 2. 批量融合
        fusion_results = PredictionFusion.fuse_batch(
            stocks=stocks,
            gain_predictions=gain_preds,
            prob_predictions=prob_preds,
            risk_preference=risk_preference
        )

        # 3. 取Top N进行买入分析
        top_stocks = [s for s in stocks if s.code in {r.code for r in fusion_results[:limit * 2]}]

        signals = []
        for stock in top_stocks:
            # 获取该股票的融合结果
            fusion_result = next((r for r in fusion_results if r.code == stock.code), None)

            signal = BuyAnalyzer.analyze_buy_opportunity(stock, principal)

            # 添加预测融合字段
            if fusion_result:
                signal.predicted_gain_5d = fusion_result.predicted_gain_5d
                signal.up_probability_5d = fusion_result.up_probability_5d
                signal.prediction_confidence = fusion_result.confidence
                signal.fused_score = fusion_result.fused_score

            # 根据风险偏好过滤
            if risk_preference == 'conservative' and signal.risk_level == 'risk':
                continue
            elif risk_preference == 'balanced' and signal.risk_level in ('risk', 'warning'):
                pass

            signals.append(BuyAnalyzer._to_dict(signal))

        # 4. 如果有融合结果，按融合得分排序；否则按买入强度
        if fusion_results:
            # 建立code到信号的映射
            signal_map = {s['code']: s for s in signals}
            # 按融合排名重新排序
            fusion_rank_map = {r.code: r.fused_rank for r in fusion_results}
            signals.sort(key=lambda x: (fusion_rank_map.get(x['code'], 999), -x['buy_strength']))
        else:
            signals.sort(key=lambda x: x['buy_strength'], reverse=True)

        return signals[:limit]

    def analyze_buy_opportunity(
        self,
        stock: StockCP,
        principal: float,
        max_position_pct: float = 20.0,
        win_rate: float = 0.55,
        win_loss_ratio: float = 1.5
    ) -> Dict:
        """分析单只股票的买入价值

        Args:
            stock: 股票
            principal: 本金
            max_position_pct: 最大仓位比例
            win_rate: 胜率
            win_loss_ratio: 盈亏比

        Returns:
            买入信号字典
        """
        signal = BuyAnalyzer.analyze_buy_opportunity(
            stock=stock,
            principal=principal,
            max_position_pct=max_position_pct,
            win_rate=win_rate,
            win_loss_ratio=win_loss_ratio
        )
        return BuyAnalyzer._to_dict(signal)

    # ==================== 纯卖出分析 ====================

    def get_sell_signals(
        self,
        holdings: List[Dict],
        market_mode: str = 'normal'
    ) -> List[Dict]:
        """获取持仓卖出信号列表

        Args:
            holdings: 持仓列表 [{code, name, stock, quantity, cost_price}, ...]
            market_mode: 大盘模式 (normal/defensive/crisis)

        Returns:
            卖出信号列表
        """
        return SellAnalyzer.get_sell_signals(
            holdings=holdings,
            market_mode=market_mode
        )

    def analyze_sell_opportunity(
        self,
        holding: Dict,
        market_mode: str = 'normal'
    ) -> Dict:
        """分析单只持仓的卖出价值

        Args:
            holding: 持仓信息 {stock, quantity, cost_price}
            market_mode: 大盘模式

        Returns:
            卖出信号字典
        """
        signal = SellAnalyzer.analyze_sell_opportunity(
            holding=holding,
            market_mode=market_mode
        )
        return SellAnalyzer._to_dict(signal)

    # ==================== 原有方法（保持兼容） ====================

    def get_recommendations(
        self,
        category: str = 'value',
        risk_preference: str = 'balanced',
        exclude_holdings: bool = True,
        holdings: List[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """获取推荐股票（原有接口，保持兼容）"""
        if holdings is None:
            holdings = []

        stocks = self.engine.stocks
        if exclude_holdings and holdings:
            stocks = [s for s in stocks if s.code not in holdings]

        # 排序
        if category == 'value':
            sorted_stocks = sorted(stocks, key=lambda x: x.value_score, reverse=True)
        elif category == 'growth':
            sorted_stocks = sorted(stocks, key=lambda x: x.growth_score, reverse=True)
        elif category == 'momentum':
            sorted_stocks = sorted(stocks, key=lambda x: x.momentum_score, reverse=True)
        elif category == 'quality':
            sorted_stocks = sorted(stocks, key=lambda x: x.quality_score, reverse=True)
        else:
            sorted_stocks = sorted(stocks, key=lambda x: x.total_cp, reverse=True)

        # 风险过滤
        if risk_preference == 'conservative':
            sorted_stocks = [s for s in sorted_stocks if s.risk_score < 30]
        elif risk_preference == 'balanced':
            sorted_stocks = [s for s in sorted_stocks if s.risk_score < 50]

        result = []
        for stock in sorted_stocks[:limit]:
            result.append({
                'code': stock.code,
                'name': stock.name,
                'total_cp': round(stock.total_cp, 1),
                'growth_score': round(stock.growth_score, 1),
                'value_score': round(stock.value_score, 1),
                'quality_score': round(stock.quality_score, 1),
                'momentum_score': round(stock.momentum_score, 1),
                'risk_score': stock.risk_score,
                'risk_level': stock.get_risk_level(),
                'pe': stock.pe,
                'roe': stock.roe,
                'net_profit_growth': stock.net_profit_growth,
                'change_pct': stock.change_pct,
                'price': stock.price,
                'board_type': stock.board_type,
                'board_name': stock.board_name,
                'can_trade_newbie': stock.can_trade_newbie
            })

        return result


# 单例
_recommend_engine = None


def get_recommend_engine() -> RecommendEngine:
    """获取推荐引擎单例"""
    global _recommend_engine
    if _recommend_engine is None:
        _recommend_engine = RecommendEngine()
    return _recommend_engine
