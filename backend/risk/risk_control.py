"""实盘风险管理器 v1.0

5项风控功能：
1. 自动止损 — 持仓亏损达阈值时强制平仓
2. 尾随止损（Trailing Stop）— 从持仓最高价回撤一定比例时平仓
3. 组合级回撤熔断 — 组合总净值从峰值回撤超限时降低仓位或清仓


4. Kelly 仓位实际执行 — Trader 按 Kelly 计算结果自动调整下单数量
5. 市场环境识别 — 简单牛熊判断调整总仓位
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from backend.engine.cp_engine.constants import RISK_MANAGEMENT


@dataclass
class RiskCheckResult:
    """风控检查结果"""
    should_sell: bool
    reason: str
    action: Optional[str] = None  # 'stop_loss', 'trailing_stop', 'reduce', 'clear'


class RiskManager:
    """实盘风险管理器 v1.0"""

    def __init__(self, config: Dict = None):
        self.config = config or RISK_MANAGEMENT

    def check_stop_loss(self, position: Dict) -> RiskCheckResult:
        """检查固定止损

        Args:
            position: 持仓信息，需包含 current_price, cost_price

        Returns:
            (should_sell, reason)
        """
        if not self.config['enabled']:
            return RiskCheckResult(False, "")

        current_price = position.get('current_price', 0)
        cost_price = position.get('cost_price', 0)
        if cost_price <= 0:
            return RiskCheckResult(False, "")

        pnl_pct = (current_price - cost_price) / cost_price
        if pnl_pct <= self.config['stop_loss_pct']:
            return RiskCheckResult(
                True,
                f"固定止损触发: {pnl_pct:.2%} <= {self.config['stop_loss_pct']:.2%}",
                'stop_loss'
            )
        return RiskCheckResult(False, "")

    def check_trailing_stop(self, position: Dict) -> RiskCheckResult:
        """检查尾随止损

        Args:
            position: 持仓信息，需包含 current_price, peak_price

        Returns:
            (should_sell, reason)
        """
        if not self.config['enabled']:
            return RiskCheckResult(False, "")

        current_price = position.get('current_price', 0)
        peak_price = position.get('peak_price', current_price)
        if peak_price <= 0:
            return RiskCheckResult(False, "")

        drawdown = (current_price - peak_price) / peak_price
        if drawdown <= self.config['trailing_stop_pct']:
            return RiskCheckResult(
                True,
                f"尾随止损触发: 从最高{peak_price:.2f}回撤{drawdown:.2%}",
                'trailing_stop'
            )
        return RiskCheckResult(False, "")

    def check_portfolio_drawdown(self, account_info: Dict) -> RiskCheckResult:
        """检查组合级回撤

        Args:
            account_info: 账户信息，需包含 total_assets, peak_assets

        Returns:
            (should_reduce, reason)
        """
        if not self.config['enabled']:
            return RiskCheckResult(False, "")

        current_value = account_info.get('total_assets', 0)
        peak_value = account_info.get('peak_assets', current_value)
        if peak_value <= 0:
            return RiskCheckResult(False, "")

        drawdown = (current_value - peak_value) / peak_value
        if drawdown <= self.config['portfolio_drawdown_limit']:
            action = self.config['portfolio_drawdown_action']
            return RiskCheckResult(
                True,
                f"组合回撤熔断: {drawdown:.2%}, 动作: {action}",
                action
            )
        return RiskCheckResult(False, "")

    def calculate_kelly_position_size(self, stock_code: str, account_value: float,
                                       current_price: float) -> int:
        """用 Kelly 公式计算建议仓位

        Args:
            stock_code: 股票代码
            account_value: 账户总市值
            current_price: 当前股价

        Returns:
            建议买入股数（100的整数倍），0表示不建议买入
        """
        if not self.config['enabled'] or not self.config['use_kelly_sizing']:
            return 0

        try:
            from backend.risk.kelly_calculator import KellyCalculator
            calculator = KellyCalculator()
            kelly_result = calculator.calculate(stock_code)
        except Exception:
            return 0

        kelly_pct = kelly_result.get('kelly_position', 0)
        if kelly_pct <= 0:
            return 0

        kelly_pct = kelly_pct * self.config['kelly_fraction']
        kelly_pct = min(kelly_pct, self.config['max_single_position_pct'])

        target_value = account_value * kelly_pct
        shares = int(target_value / current_price / 100) * 100
        return max(0, shares)

    def detect_market_regime(self, index_code: str = '000001') -> str:
        """简单的市场环境识别

        基于上证指数 MA20：
        - 指数 > MA20 → 'bull'
        - 指数 < MA20 → 'bear'

        Args:
            index_code: 指数代码，默认上证指数

        Returns:
            'bull' | 'bear' | 'unknown'
        """
        if not self.config['enabled'] or not self.config['market_regime_enabled']:
            return 'unknown'

        try:
            from backend.data_manager.duckdb_store import get_duckdb_store
            duckdb = get_duckdb_store()

            ma_period = self.config['market_ma_period']
            result = duckdb.get_klines(index_code, limit=ma_period + 5)
            if not result.success or result.data is None or len(result.data) < ma_period:
                return 'unknown'

            df = result.data.sort_values('trade_date')
            prices = df['close'].values

            current_price = float(prices[-1])
            ma_value = float(prices[-ma_period:].mean())

            if current_price > ma_value:
                return 'bull'
            else:
                return 'bear'
        except Exception:
            return 'unknown'

    def get_position_limit_by_regime(self, regime: str) -> float:
        """根据市场环境获取仓位限制

        Args:
            regime: 'bull' | 'bear' | 'unknown'

        Returns:
            仓位比例 (0.0 ~ 1.0)
        """
        if regime == 'bull':
            return self.config['bull_position_pct']
        elif regime == 'bear':
            return self.config['bear_position_pct']
        return 1.0

    def get_positions_with_risk_info(self, holdings: List[Dict],
                                      prices: Dict[str, float]) -> List[Dict]:
        """为持仓列表添加风控信息

        Args:
            holdings: 持仓列表
            prices: 股票价格字典 {code: price}

        Returns:
            带风控信息的持仓列表
        """
        result = []
        for h in holdings:
            code = h.get('code', '')
            current_price = prices.get(code, 0)
            cost_price = h.get('avg_cost_price', 0) or h.get('cost_price', 0)
            peak_price = h.get('peak_price', current_price)

            info = {**h}
            info['current_price'] = current_price
            info['cost_price'] = cost_price
            info['peak_price'] = peak_price

            # 计算盈亏
            if cost_price > 0 and current_price > 0:
                info['pnl_pct'] = (current_price - cost_price) / cost_price
                info['drawdown_pct'] = (current_price - peak_price) / peak_price if peak_price > 0 else 0
            else:
                info['pnl_pct'] = 0
                info['drawdown_pct'] = 0

            # 风控触发检查
            stop_loss_result = self.check_stop_loss(info)
            trailing_result = self.check_trailing_stop(info)
            info['should_stop_loss'] = stop_loss_result.should_sell
            info['stop_loss_reason'] = stop_loss_result.reason
            info['should_trailing_stop'] = trailing_result.should_sell
            info['trailing_stop_reason'] = trailing_result.reason

            result.append(info)

        return result
