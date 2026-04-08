"""
回测验证模块 - Backtest Verification v19.7

用于验证：
1. 换股效果：验证换股决策是否带来正收益
2. 战力预测准确性：验证战力高的股票是否真的涨

数据来源：
- simulator holding_snapshots 表（每日持仓快照）
- simulator trades 表（交易记录）
- data_manager cp_history_store（战力历史，v19.7迁移）

注意：v19.7 cp_history 已从 simulator 迁移到 data_manager/cp_history_store.py
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class SwapVerification:
    """换股验证结果"""
    code: str
    name: str
    action: str  # 'buy' / 'sell'
    swap_date: str
    price: float  # 成交价
    quantity: int
    # 后续验证
    hold_days: int  # 持有天数
    end_price: float  # 卖出时价格（或最新价格）
    end_cp: float  # 卖出时战力（或最新战力）
    price_change_pct: float  # 价格变化
    cp_change: float  # 战力变化
    is_profitable: bool  # 是否盈利
    profit: float  # 盈亏金额


@dataclass
class CPPredictionAccuracy:
    """战力预测准确性结果"""
    period: str  # 验证周期
    total_stocks: int  # 样本数
    high_cp_above_avg: float  # 高战力组平均涨幅 vs 市场平均
    low_cp_below_avg: float  # 低战力组平均涨幅 vs 市场平均
    accuracy: float  # 准确率（高战力跑赢市场的比例）
    avg_profit_if_hold_high_cp: float  # 持有高战力股票平均收益
    avg_profit_if_hold_low_cp: float  # 持有低战力股票平均收益


class BacktestVerifier:
    """回测验证器 v19.7"""

    def __init__(self, db, cp_history_store=None):
        """初始化验证器

        Args:
            db: simulator.database.Database 实例
            cp_history_store: data_manager.cp_history_store.CPHistoryStore 实例
        """
        self.db = db
        # 尝试导入 CPHistoryStore
        if cp_history_store is None:
            try:
                from data_manager.cp_history_store import get_cp_history_store
                self.cp_store = get_cp_history_store()
            except ImportError:
                self.cp_store = None
        else:
            self.cp_store = cp_history_store

    def verify_swap_effectiveness(
        self,
        start_date: str = None,
        end_date: str = None,
        min_hold_days: int = 1
    ) -> List[SwapVerification]:
        """验证换股效果

        分析所有卖出交易，计算如果持有到现在收益如何

        Args:
            start_date: 开始日期
            end_date: 结束日期
            min_hold_days: 最小持有天数

        Returns:
            换股验证结果列表
        """
        # 获取交易记录
        trades = self.db.get_trades(limit=1000)

        results = []
        for trade in trades:
            if trade['action'] != 'sell':
                continue

            code = trade['code']
            name = trade['name']
            swap_date = trade['recorded_at'][:10]  # 取日期部分
            sell_price = trade['price']
            quantity = trade['quantity']

            # 获取今日收盘价和战力
            today = datetime.now().strftime("%Y-%m-%d")
            current_stock = self.db.get_stock(code)
            if not current_stock:
                continue

            current_price = current_stock.get('price', 0)
            current_cp = current_stock.get('total_cp', 0)

            # 计算持有天数
            swap_dt = datetime.strptime(swap_date, "%Y-%m-%d")
            today_dt = datetime.now()
            hold_days = (today_dt - swap_dt).days

            if hold_days < min_hold_days:
                continue

            # 计算收益
            price_change_pct = (current_price - sell_price) / sell_price * 100 if sell_price > 0 else 0
            profit = (current_price - sell_price) * quantity
            is_profitable = profit > 0

            # 获取当时的CP
            cp_history = self.cp_store.get_cp_history(code, days=30) if self.cp_store else []
            sell_cp = 0
            if cp_history:
                for h in cp_history:
                    if h['recorded_at'][:10] == swap_date:
                        sell_cp = h['total_cp']
                        break

            results.append(SwapVerification(
                code=code,
                name=name,
                action='sell',
                swap_date=swap_date,
                price=sell_price,
                quantity=quantity,
                hold_days=hold_days,
                end_price=current_price,
                end_cp=current_cp,
                price_change_pct=round(price_change_pct, 2),
                cp_change=round(current_cp - sell_cp, 2) if sell_cp else 0,
                is_profitable=is_profitable,
                profit=round(profit, 2)
            ))

        return results

    def get_swap_summary(self, verifications: List[SwapVerification]) -> Dict:
        """获取换股验证汇总

        Args:
            verifications: 换股验证结果列表

        Returns:
            汇总统计
        """
        if not verifications:
            return {
                'total_swaps': 0,
                'profitable_count': 0,
                'avg_profit_pct': 0,
                'total_profit': 0,
                'win_rate': 0
            }

        profitable = [v for v in verifications if v.is_profitable]
        avg_profit_pct = sum(v.price_change_pct for v in verifications) / len(verifications)
        total_profit = sum(v.profit for v in verifications)

        return {
            'total_swaps': len(verifications),
            'profitable_count': len(profitable),
            'avg_profit_pct': round(avg_profit_pct, 2),
            'total_profit': round(total_profit, 2),
            'win_rate': round(len(profitable) / len(verifications) * 100, 2) if verifications else 0
        }

    def verify_cp_prediction_accuracy(
        self,
        date: str = None,
        holding_days: int = 5,
        high_cp_threshold: float = 70,
        low_cp_threshold: float = 50
    ) -> CPPredictionAccuracy:
        """验证战力预测准确性

        比较战力高的股票组和战力低的股票组在未来N天的表现

        Args:
            date: 基准日期（战力发布日期）
            holding_days: 持有天数
            high_cp_threshold: 高战力阈值
            low_cp_threshold: 低战力阈值

        Returns:
            战力预测准确性结果
        """
        if date is None:
            # 使用最近一个有战力记录的日期
            today = datetime.now().strftime("%Y-%m-%d")
            cp_list = self.cp_store.get_cp_history_by_date(today) if self.cp_store else []
            if not cp_list:
                # 尝试前一天
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                cp_list = self.cp_store.get_cp_history_by_date(yesterday) if self.cp_store else []
            date = cp_list[0]['recorded_at'][:10] if cp_list else today

        # 获取当日的战力数据
        cp_list = self.cp_store.get_cp_history_by_date(date) if self.cp_store else []
        if not cp_list:
            return CPPredictionAccuracy(
                period=date,
                total_stocks=0,
                high_cp_above_avg=0,
                low_cp_below_avg=0,
                accuracy=0,
                avg_profit_if_hold_high_cp=0,
                avg_profit_if_hold_low_cp=0
            )

        # 分组
        high_cp_stocks = [c for c in cp_list if c['total_cp'] >= high_cp_threshold]
        low_cp_stocks = [c for c in cp_list if c['total_cp'] <= low_cp_threshold]

        # 计算各组在未来N天的平均收益
        end_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=holding_days)).strftime("%Y-%m-%d")

        high_cp_profits = []
        for stock in high_cp_stocks:
            code = stock['code']
            current = self.db.get_stock(code)
            if current:
                price_now = current.get('price', 0)
                price_then = None
                # 从cp_history找当时的price
                history = self.cp_store.get_cp_history(code, days=holding_days + 5) if self.cp_store else []
                for h in history:
                    if h['recorded_at'][:10] <= date:
                        price_then = h.get('close') or h.get('price')
                        break
                if price_then and price_now and price_then > 0:
                    profit_pct = (price_now - price_then) / price_then * 100
                    high_cp_profits.append(profit_pct)

        low_cp_profits = []
        for stock in low_cp_stocks:
            code = stock['code']
            current = self.db.get_stock(code)
            if current:
                price_now = current.get('price', 0)
                price_then = None
                history = self.cp_store.get_cp_history(code, days=holding_days + 5) if self.cp_store else []
                for h in history:
                    if h['recorded_at'][:10] <= date:
                        price_then = h.get('close') or h.get('price')
                        break
                if price_then and price_now and price_then > 0:
                    profit_pct = (price_now - price_then) / price_then * 100
                    low_cp_profits.append(profit_pct)

        # 计算市场平均
        all_profits = high_cp_profits + low_cp_profits
        market_avg = sum(all_profits) / len(all_profits) if all_profits else 0

        # 计算高/低战力组相对于市场的表现
        high_avg = sum(high_cp_profits) / len(high_cp_profits) if high_cp_profits else 0
        low_avg = sum(low_cp_profits) / len(low_cp_profits) if low_cp_profits else 0

        high_cp_above_avg = high_avg - market_avg
        low_cp_below_avg = low_avg - market_avg

        # 计算准确率（高战力组跑赢市场的比例）
        high_beats_market = sum(1 for p in high_cp_profits if p > market_avg)
        accuracy = high_beats_market / len(high_cp_profits) * 100 if high_cp_profits else 0

        return CPPredictionAccuracy(
            period=f"{date} ~ +{holding_days}d",
            total_stocks=len(cp_list),
            high_cp_above_avg=round(high_cp_above_avg, 2),
            low_cp_below_avg=round(low_cp_below_avg, 2),
            accuracy=round(accuracy, 2),
            avg_profit_if_hold_high_cp=round(high_avg, 2),
            avg_profit_if_hold_low_cp=round(low_avg, 2)
        )

    def get_verification_report(self, days: int = 30) -> Dict:
        """获取完整的验证报告

        Args:
            days: 验证最近N天的数据

        Returns:
            验证报告
        """
        # 换股验证
        verifications = self.verify_swap_effectiveness(
            start_date=(datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        )
        swap_summary = self.get_swap_summary(verifications)

        # 战力预测准确性验证
        cp_accuracy = self.verify_cp_prediction_accuracy(
            holding_days=5,
            high_cp_threshold=70,
            low_cp_threshold=50
        )

        return {
            'report_date': datetime.now().strftime("%Y-%m-%d"),
            'swap_verification': swap_summary,
            'cp_prediction_accuracy': {
                'period': cp_accuracy.period,
                'total_stocks': cp_accuracy.total_stocks,
                'high_cp_group_avg_profit': cp_accuracy.avg_profit_if_hold_high_cp,
                'low_cp_group_avg_profit': cp_accuracy.avg_profit_if_hold_low_cp,
                'high_cp_beats_market_rate': cp_accuracy.accuracy,
                'high_cp_vs_market': cp_accuracy.high_cp_above_avg,
                'low_cp_vs_market': cp_accuracy.low_cp_below_avg
            },
            'conclusion': self._generate_conclusion(swap_summary, cp_accuracy)
        }

    def _generate_conclusion(self, swap_summary: Dict, cp_accuracy: CPPredictionAccuracy) -> str:
        """生成结论"""
        conclusions = []

        # 换股效果结论
        if swap_summary['total_swaps'] > 0:
            if swap_summary['win_rate'] >= 60:
                conclusions.append(f"换股策略有效：胜率{swap_summary['win_rate']}%，平均收益{swap_summary['avg_profit_pct']}%")
            elif swap_summary['win_rate'] >= 50:
                conclusions.append(f"换股策略中性：胜率{swap_summary['win_rate']}%，需进一步观察")
            else:
                conclusions.append(f"换股策略需优化：胜率{swap_summary['win_rate']}%，平均亏损{swap_summary['avg_profit_pct']}%")
        else:
            conclusions.append("暂无换股数据")

        # 战力预测结论
        if cp_accuracy.total_stocks > 0:
            if cp_accuracy.accuracy >= 55:
                conclusions.append(f"战力预测有效：高战力组跑赢市场概率{cp_accuracy.accuracy}%")
            elif cp_accuracy.accuracy >= 45:
                conclusions.append(f"战力预测中性：高战力组跑赢市场概率{cp_accuracy.accuracy}%")
            else:
                conclusions.append(f"战力预测需优化：高战力组跑赢市场概率{cp_accuracy.accuracy}%")
        else:
            conclusions.append("暂无战力预测数据")

        return " | ".join(conclusions) if conclusions else "数据不足，无法生成结论"


def verify_swap_effectiveness(db, start_date: str = None, end_date: str = None) -> List[SwapVerification]:
    """便捷函数：验证换股效果"""
    verifier = BacktestVerifier(db)
    return verifier.verify_swap_effectiveness(start_date, end_date)


def verify_cp_prediction_accuracy(db, date: str = None, holding_days: int = 5) -> CPPredictionAccuracy:
    """便捷函数：验证战力预测准确性"""
    verifier = BacktestVerifier(db)
    return verifier.verify_cp_prediction_accuracy(date, holding_days)


def get_verification_report(db, days: int = 30) -> Dict:
    """便捷函数：获取验证报告"""
    verifier = BacktestVerifier(db)
    return verifier.get_verification_report(days)
