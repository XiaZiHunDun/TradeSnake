"""
回测引擎 - Backtest Engine v19.3
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from .strategies import Strategy, StockFactor
from .metrics import Metrics, Trade, BacktestResult
from backend.engine import TRADE_COST

# 交易费用（统一从 engine.constants 导入）
COMMISSION_RATE = TRADE_COST['commission']
MIN_COMMISSION = TRADE_COST['min_commission']
STAMP_TAX_RATE = TRADE_COST['stamp_tax']
TRANSFER_FEE_RATE = TRADE_COST['transfer_fee']
MIN_TRADE_UNIT = 100  # 最小交易单位（保留本地定义）


@dataclass
class Position:
    """持仓"""
    code: str
    name: str
    quantity: int = 0
    avg_cost: float = 0.0
    buy_date: str = ''  # 买入日期
    holding_days: int = 0  # 持仓天数（交易日）


class PositionManager:
    """持仓管理器 v19.8

    负责持仓的日常管理：
    - 更新持仓状态
    - 检查最大持仓天数
    - T+1 限制判断
    """

    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.pending_bought: Set[str] = set()  # 今日买入的股票

    def add(self, code: str, name: str, quantity: int, price: float, buy_date: str):
        """添加持仓"""
        if code in self.positions:
            pos = self.positions[code]
            total_qty = pos.quantity + quantity
            pos.avg_cost = (pos.avg_cost * pos.quantity + price * quantity) / total_qty
            pos.quantity = total_qty
        else:
            self.positions[code] = Position(
                code=code,
                name=name,
                quantity=quantity,
                avg_cost=price,
                buy_date=buy_date,
                holding_days=0
            )
        self.pending_bought.add(code)

    def remove(self, code: str) -> Optional[Position]:
        """移除持仓"""
        if code in self.positions:
            pos = self.positions.pop(code)
            return pos
        return None

    def update(self, date: str):
        """每日收盘后更新持仓状态

        Args:
            date: 当前日期
        """
        for pos in self.positions.values():
            pos.holding_days += 1

    def check_max_holding_days(self, max_days: int) -> List[str]:
        """检查超过最大持仓天数的股票

        Args:
            max_days: 最大持仓天数

        Returns:
            应卖出的股票代码列表
        """
        return [
            code for code, pos in self.positions.items()
            if pos.holding_days > max_days
        ]

    def was_bought_today(self, code: str, date: str) -> bool:
        """检查是否今日买入（T+1判断用）

        Args:
            code: 股票代码
            date: 当前日期

        Returns:
            True if 今日买入
        """
        if code not in self.positions:
            return False
        return self.positions[code].buy_date == date

    def clear_pending(self):
        """清除pending标记（新交易日开始）"""
        self.pending_bought.clear()

    def is_pending(self, code: str) -> bool:
        """检查是否在pending中（T+1限制）"""
        return code in self.pending_bought

    def get_position(self, code: str) -> Optional[Position]:
        """获取持仓"""
        return self.positions.get(code)

    def get_all_positions(self) -> Dict[str, Position]:
        """获取所有持仓"""
        return self.positions.copy()

    def total_value(self, price_func) -> float:
        """计算持仓总市值

        Args:
            price_func: 获取价格的函数 (code, date) -> float

        Returns:
            持仓总市值
        """
        return sum(
            pos.quantity * price_func(pos.code)
            for pos in self.positions.values()
        )


class Backtest:
    """回测引擎 v19.3

    核心流程：
    T日收盘：
        1. 获取T日战力数据
        2. 策略 select_stocks() → 目标持仓列表
        3. 生成调仓信号（仅当列表变化时）

    T+1日收盘：
        4. 按T+1日收盘价执行成交
        5. 涨跌停股票跳过
        6. 更新持仓、记录净值
    """

    def __init__(self):
        self.strategy: Strategy = None
        self.start_date: str = ''
        self.end_date: str = ''
        self.initial_capital: float = 20000
        self.stock_list: List[str] = None
        self.include_fees: bool = False
        self.strict_t1: bool = False
        self.benchmark: str = None

        # 内部状态
        self.cash: float = 20000
        self.positions: Dict[str, Position] = {}  # code -> Position
        self.pending_bought: Set[str] = set()  # 今日买入的股票（T+1判断）
        self.trades: List[Trade] = []
        self.equity_curve: Dict[str, float] = {}  # {date: total_value}
        self.net_value_curve: Dict[str, float] = {}  # {date: net_value}
        self.positions_history: List[Dict] = []

        # 数据获取函数（外部注入）
        self._get_trading_dates = None
        self._get_stock_factors = None
        self._get_price_data = None
        self._get_benchmark_data = None

    def run(self, strategy: Strategy,
             start_date: str,
             end_date: str,
             initial_capital: float = 20000,
             stock_list: List[str] = None,
             include_fees: bool = False,
             strict_t1: bool = False,
             benchmark: str = None,
             get_trading_dates_func=None,
             get_stock_factors_func=None,
             get_price_data_func=None,
             get_benchmark_data_func=None) -> BacktestResult:
        """执行回测

        Args:
            strategy: 策略实例
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            initial_capital: 初始资金
            stock_list: 股票池（None=全部）
            include_fees: 是否计入手续费
            strict_t1: 是否启用T+1严格模式
            benchmark: 基准代码，如 '000300.SH'
            get_trading_dates_func: 获取交易日列表函数 (start, end) -> List[str]
            get_stock_factors_func: 获取战力因子函数 (date, codes) -> Dict[str, StockFactor]
            get_price_data_func: 获取价格数据函数 (code, date) -> Dict
            get_benchmark_data_func: 获取基准数据函数 (date) -> float

        Returns:
            BacktestResult 回测结果
        """
        # 初始化参数
        self.strategy = strategy
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.stock_list = stock_list
        self.include_fees = include_fees
        self.strict_t1 = strict_t1
        self.benchmark = benchmark

        # 初始化状态
        self.cash = initial_capital
        self.positions = {}
        self.pending_bought = set()
        self.trades = []
        self.equity_curve = {}
        self.positions_history = []

        # 设置数据获取函数
        self._get_trading_dates = get_trading_dates_func or self._default_get_trading_dates
        self._get_stock_factors = get_stock_factors_func or self._default_get_stock_factors
        self._get_price_data = get_price_data_func or self._default_get_price_data
        self._get_benchmark_data = get_benchmark_data_func or self._default_get_benchmark_data

        # 获取交易日列表
        trading_dates = self._get_trading_dates(start_date, end_date)
        if len(trading_dates) < 2:
            raise ValueError("交易日数据不足，无法回测")

        # 按日期遍历（T日收盘 → T+1日成交）
        for i in range(len(trading_dates) - 1):
            signal_date = trading_dates[i]
            trade_date = trading_dates[i + 1]

            # Step 1: 获取T日战力数据
            stock_factors = self._get_stock_factors(signal_date, self.stock_list)

            # Step 2: 策略选股
            target_codes = strategy.select_stocks(
                signal_date, stock_factors, strategy.max_positions
            )

            # Step 3: 获取当前持仓列表
            current_codes = set(self.positions.keys())

            # Step 4: 检查持仓是否超过最大天数（强制卖出）
            for code in list(current_codes):
                pos = self.positions[code]
                pos.holding_days += 1
                if pos.holding_days > strategy.max_position_days:
                    # 超时强制卖出
                    self._sell_stock(code, signal_date, trade_date, reason='max_days')

            # 重新获取当前持仓
            current_codes = set(self.positions.keys())

            # Step 5: 生成调仓信号（仅当列表变化时）
            new_target_codes = self._filter_and_rank_targets(target_codes, stock_factors)

            if set(new_target_codes) != current_codes:
                # 需要调仓
                self._execute_rebalance(
                    signal_date, trade_date,
                    list(current_codes), new_target_codes,
                    stock_factors
                )
            else:
                # 持仓不变，只更新持仓天数
                pass

            # 清除T日买入记录（新的交易日开始）
            self.pending_bought = set()

            # Step 6: 记录每日净值
            self._record_daily_value(signal_date)

        # 最后一个交易日也要记录净值
        self._record_daily_value(trading_dates[-1])

        # 计算绩效指标
        return self._calculate_result(trading_dates)

    def _filter_and_rank_targets(self, target_codes: List[str],
                                 stock_factors: Dict[str, StockFactor]) -> List[str]:
        """过滤并排序目标股票

        1. 过滤停牌、涨跌停
        2. 按持仓数量限制
        3. 保持战力排序
        """
        filtered = []
        for code in target_codes:
            if code in self.positions:
                # 已在持仓中，保留
                filtered.append(code)
                continue

            factor = stock_factors.get(code)
            if not factor:
                continue

            # 过滤停牌
            if factor.is_suspended:
                continue

            # 过滤涨跌停（买入时涨停不买，跌停也不买）
            if abs(factor.change_pct) >= 9.9:
                continue

            filtered.append(code)

        # 限制数量
        max_pos = self.strategy.max_positions
        return filtered[:max_pos]

    def _execute_rebalance(self, signal_date: str, trade_date: str,
                         current_codes: List[str], target_codes: List[str],
                         stock_factors: Dict[str, StockFactor]):
        """执行调仓"""
        current_set = set(current_codes)
        target_set = set(target_codes)

        # Step 1: 卖出不在目标列表的持仓
        for code in current_codes:
            if code not in target_set:
                self._sell_stock(code, signal_date, trade_date, reason='rebalance')

        # Step 2: 买入目标列表中的新持仓
        new_codes = [c for c in target_codes if c not in current_set]

        # 计算可用资金
        available = self.cash
        per_stock = available / len(target_codes) if target_codes else 0

        for code in new_codes:
            factor = stock_factors.get(code)
            if not factor:
                continue

            price = factor.close
            if price <= 0:
                continue

            # 按100股取整
            quantity = (int(per_stock / price) // MIN_TRADE_UNIT) * MIN_TRADE_UNIT
            if quantity > 0:
                self._buy_stock(code, factor.name, signal_date, trade_date,
                               price, quantity)

    def _buy_stock(self, code: str, name: str, signal_date: str,
                   trade_date: str, price: float, quantity: int):
        """买入股票"""
        amount = price * quantity
        commission = 0
        transfer_fee = 0

        if self.include_fees:
            commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
            transfer_fee = amount * TRANSFER_FEE_RATE
            total_cost = amount + commission + transfer_fee
        else:
            total_cost = amount

        if self.cash < total_cost:
            # 资金不足，减少数量
            max_q = int((self.cash / (1 + COMMISSION_RATE + TRANSFER_FEE_RATE)) / price)
            max_q = (max_q // MIN_TRADE_UNIT) * MIN_TRADE_UNIT
            if max_q < MIN_TRADE_UNIT:
                return  # 买不起1手
            quantity = max_q
            amount = price * quantity
            if self.include_fees:
                commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
                transfer_fee = amount * TRANSFER_FEE_RATE
                total_cost = amount + commission + transfer_fee
            else:
                total_cost = amount

        # 扣除资金
        self.cash -= total_cost

        # 记录持仓
        if code in self.positions:
            pos = self.positions[code]
            total_qty = pos.quantity + quantity
            pos.avg_cost = (pos.avg_cost * pos.quantity + price * quantity) / total_qty
            pos.quantity = total_qty
        else:
            self.positions[code] = Position(
                code=code,
                name=name,
                quantity=quantity,
                avg_cost=price,
                buy_date=trade_date,
                holding_days=0
            )

        # 记录买入
        trade = Trade(
            signal_date=signal_date,
            trade_date=trade_date,
            code=code,
            name=name,
            action='buy',
            price=price,
            quantity=quantity,
            amount=amount,
            commission=commission,
            stamp_tax=0,
            transfer_fee=transfer_fee,
            profit=0,
            reason='rebalance'
        )
        self.trades.append(trade)

        # 记录今日买入（T+1判断用）
        self.pending_bought.add(code)

    def _sell_stock(self, code: str, signal_date: str,
                   trade_date: str, reason: str = 'rebalance'):
        """卖出股票"""
        if code not in self.positions:
            return

        pos = self.positions[code]

        # T+1检查
        if self.strict_t1 and code in self.pending_bought:
            return  # T+1限制，今日不可卖

        price = self._get_price_data(code, trade_date).get('close', 0)
        if price <= 0:
            return

        amount = price * pos.quantity
        commission = 0
        stamp_tax = 0
        transfer_fee = 0
        profit = 0

        if self.include_fees:
            commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
            stamp_tax = amount * STAMP_TAX_RATE
            transfer_fee = amount * TRANSFER_FEE_RATE
            total_proceeds = amount - commission - stamp_tax - transfer_fee
        else:
            total_proceeds = amount

        profit = total_proceeds - (pos.avg_cost * pos.quantity)

        # 增加资金
        self.cash += total_proceeds

        # 记录卖出
        trade = Trade(
            signal_date=signal_date,
            trade_date=trade_date,
            code=code,
            name=pos.name,
            action='sell',
            price=price,
            quantity=pos.quantity,
            amount=amount,
            commission=commission,
            stamp_tax=stamp_tax,
            transfer_fee=transfer_fee,
            profit=profit,
            reason=reason
        )
        self.trades.append(trade)

        # 删除持仓
        del self.positions[code]

    def _record_daily_value(self, date: str):
        """记录每日净值

        使用当日收盘价计算持仓市值，更准确反映组合真实价值
        """
        positions_value = 0.0
        for pos in self.positions.values():
            # 优先使用当日收盘价计算市值
            price_data = self._get_price_data(pos.code, date)
            current_price = price_data.get('close', 0)
            if current_price <= 0:
                # 兜底使用成本价
                current_price = pos.avg_cost
            positions_value += pos.quantity * current_price

        total_value = self.cash + positions_value
        net_value = total_value / self.initial_capital  # 净值

        self.equity_curve[date] = total_value
        self.net_value_curve[date] = net_value

        # 记录持仓快照
        self.positions_history.append({
            'date': date,
            'cash': self.cash,
            'positions_value': positions_value,
            'total_value': total_value,
            'net_value': net_value,
            'positions': {
                code: {'name': pos.name, 'quantity': pos.quantity, 'avg_cost': pos.avg_cost}
                for code, pos in self.positions.items()
            }
        })

    def _calculate_result(self, trading_dates: List[str]) -> BacktestResult:
        """计算回测结果"""
        # 计算基准曲线
        benchmark_curve = {}
        if self.benchmark:
            for date in trading_dates:
                bm_price = self._get_benchmark_data(date)
                if bm_price:
                    benchmark_curve[date] = bm_price

        # 计算绩效指标
        metrics = Metrics.calculate_metrics(
            equity_curve=self.equity_curve,
            benchmark_curve=benchmark_curve,
            trades=self.trades,
            initial_capital=self.initial_capital
        )

        # 计算平均持仓天数
        holding_days_list = []
        buy_dates = {}
        for trade in self.trades:
            if trade.action == 'buy':
                buy_dates[trade.code] = trade.trade_date
            elif trade.action == 'sell' and trade.code in buy_dates:
                buy_date = buy_dates.pop(trade.code)
                if buy_date and trade.trade_date:
                    # 计算持仓天数
                    try:
                        bd = datetime.fromisoformat(buy_date)
                        sd = datetime.fromisoformat(trade.trade_date)
                        days = (sd - bd).days
                        holding_days_list.append(max(1, days))
                    except:
                        pass

        avg_holding_days = sum(holding_days_list) / len(holding_days_list) if holding_days_list else 0

        # 构建结果
        # 计算最终持仓市值（使用最后一日收盘价）
        final_positions_value = 0.0
        last_date = trading_dates[-1] if trading_dates else self.end_date
        for pos in self.positions.values():
            price_data = self._get_price_data(pos.code, last_date)
            final_price = price_data.get('close', 0)
            if final_price <= 0:
                final_price = pos.avg_cost
            final_positions_value += pos.quantity * final_price

        result = BacktestResult(
            strategy_name=self.strategy.name,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            final_capital=self.cash + final_positions_value,

            # 绩效指标
            total_return=metrics.get('total_return', 0),
            annual_return=metrics.get('annual_return', 0),
            benchmark_return=metrics.get('benchmark_return', 0),
            excess_return=metrics.get('excess_return', 0),
            sharpe_ratio=metrics.get('sharpe_ratio', 0),
            calmar_ratio=metrics.get('calmar_ratio', 0),
            max_drawdown=metrics.get('max_drawdown', 0),
            volatility=metrics.get('volatility', 0),
            max_consecutive_win=metrics.get('max_consecutive_win', 0),
            max_consecutive_loss=metrics.get('max_consecutive_loss', 0),

            # 交易指标
            total_trades=metrics.get('total_trades', 0),
            winning_trades=metrics.get('winning_trades', 0),
            losing_trades=metrics.get('losing_trades', 0),
            win_rate=metrics.get('win_rate', 0),
            profit_loss_ratio=metrics.get('profit_loss_ratio', 0),
            avg_holding_days=avg_holding_days,

            # 交易记录
            trades=self.trades,

            # 净值曲线
            equity_curve=self.equity_curve,
            net_value_curve=self.net_value_curve,
            benchmark_curve=benchmark_curve,

            # 持仓记录
            positions_history=self.positions_history,
        )

        return result

    def _default_get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """默认获取交易日列表（从 data_manager/cp_history_store 读取）"""
        from backend.data_manager.cp_history_store import get_cp_history_store

        store = get_cp_history_store()
        conn = store._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT recorded_at FROM cp_history
            WHERE recorded_at >= ? AND recorded_at <= ?
            ORDER BY recorded_at
        """, (start_date, end_date))
        dates = [row['recorded_at'] for row in cursor.fetchall()]
        conn.close()
        return dates

    def _default_get_stock_factors(self, date: str, codes: List[str] = None) -> Dict[str, StockFactor]:
        """默认获取战力因子数据（从 data_manager/cp_history_store 读取）"""
        from backend.data_manager.cp_history_store import get_cp_history_store

        store = get_cp_history_store()
        conn = store._get_conn()
        cursor = conn.cursor()

        if codes:
            placeholders = ','.join('?' * len(codes))
            cursor.execute(f"""
                SELECT * FROM cp_history
                WHERE recorded_at = ? AND code IN ({placeholders})
            """, [date] + codes)
        else:
            cursor.execute("""
                SELECT * FROM cp_history
                WHERE recorded_at = ?
            """, (date,))

        result = {}
        for row in cursor.fetchall():
            data = dict(row)
            factor = StockFactor(
                code=data.get('code', ''),
                name=data.get('name', ''),
                date=data.get('recorded_at', date),
                close=data.get('close', 0) or data.get('price', 0),
                change_pct=data.get('change_pct', 0),
                total_cp=data.get('total_cp', 0),
                growth_score=data.get('growth_score', 0),
                value_score=data.get('value_score', 0),
                momentum_score=data.get('momentum_score', 0),
                quality_score=data.get('quality_score', 0),
                is_limit_up=data.get('change_pct', 0) >= 9.9,
                is_limit_down=data.get('change_pct', 0) <= -9.9,
                is_suspended=False
            )
            result[factor.code] = factor

        conn.close()
        return result

    def _default_get_price_data(self, code: str, date: str) -> Dict:
        """默认获取价格数据"""
        from backend.simulator.database import get_db

        db = get_db()
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT close, change_pct FROM price_history
            WHERE code = ? AND date <= ?
            ORDER BY date DESC LIMIT 1
        """, (code, date))
        row = cursor.fetchone()
        if row:
            return {'close': row['close'], 'change_pct': row['change_pct']}
        return {'close': 0, 'change_pct': 0}

    def _default_get_benchmark_data(self, date: str) -> Optional[float]:
        """默认获取基准数据（返回净值）"""
        # 默认不提供基准数据
        return None


# ==================== 兼容层：BacktestEngine ====================
# 用于兼容 api/router.py 中的旧版 API
# 如果需要使用新功能，请使用 Backtest 类


class BacktestEngine:
    """回测引擎兼容层 (v19.3)

    警告：此兼容层仅用于保持API兼容，
    实际回测逻辑已迁移到 backtester 模块。
    """

    def __init__(self):
        from backend.data_manager.cp_history_store import get_cp_history_store
        self.cp_store = get_cp_history_store()

    def get_available_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取回测期间内有数据的日期（从 cp_history_store 读取）"""
        conn = self.cp_store._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT recorded_at FROM cp_history
            WHERE recorded_at >= ? AND recorded_at <= ?
            ORDER BY recorded_at
        """, (start_date, end_date))
        dates = [row['recorded_at'] for row in cursor.fetchall()]
        conn.close()
        return dates

    def get_top_stocks_at_date(self, date: str, limit: int = 10) -> List[Dict]:
        """获取指定日期的TOP N股票（从 cp_history_store 读取）"""
        conn = self.cp_store._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM cp_history
            WHERE recorded_at = ?
            ORDER BY rank
            LIMIT ?
        """, (date, limit))
        result = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return result

    def get_stock_price_at_date(self, code: str, date: str) -> Optional[float]:
        """获取指定日期之后的第一个交易日价格（优先从DuckDB获取）"""
        # 首先尝试从 DuckDB 获取（推荐方式）
        try:
            from backend.data_manager.duckdb_store import get_duckdb_store
            duckdb = get_duckdb_store()
            # DuckDB 日期格式需要 YYYY-MM-DD
            if len(date) == 8:
                date_fmt = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
            else:
                date_fmt = date
            result = duckdb.get_klines(code, end_date=date_fmt, limit=1)
            if result.success and result.data is not None and len(result.data) > 0:
                return float(result.data.iloc[0]['close'])
        except Exception as e:
            pass

        # 回退到 DuckDB 查询（使用更早的日期范围确保找到数据）
        # v19.9.5: 移除无效的 SQLite fallback（DuckDB 是唯一数据源）
        return None

    def calculate_simple_backtest(
        self,
        start_date: str,
        end_date: str,
        holding_days: int = 30,
        top_n: int = 10
    ) -> Dict:
        """简单持有回测（兼容旧API）"""
        # 获取可用日期
        dates = self.get_available_dates(start_date, end_date)
        if len(dates) < 2:
            return {"error": "数据不足"}

        # 简化计算：取首尾日期的TOP N平均战力
        initial_date = dates[0]
        final_date = dates[-1]

        initial_stocks = self.get_top_stocks_at_date(initial_date, limit=top_n)
        final_stocks = self.get_top_stocks_at_date(final_date, limit=top_n)

        if not initial_stocks or not final_stocks:
            return {"error": "数据不足"}

        # 计算平均战力变化
        initial_avg_cp = sum(s.get('total_cp', 0) for s in initial_stocks) / len(initial_stocks)
        final_avg_cp = sum(s.get('total_cp', 0) for s in final_stocks) / len(final_stocks)

        cp_change = (final_avg_cp - initial_avg_cp) / initial_avg_cp * 100 if initial_avg_cp > 0 else 0

        return {
            "dates": dates,
            "initial_date": initial_date,
            "final_date": final_date,
            "holding_days": holding_days,
            "top_n": top_n,
            "initial_avg_cp": round(initial_avg_cp, 2),
            "final_avg_cp": round(final_avg_cp, 2),
            "cp_change": round(cp_change, 2),
            "initial_stocks": len(initial_stocks),
            "final_stocks": len(final_stocks),
        }

    def calculate_compare_backtest(
        self,
        start_date: str,
        end_date: str,
        holding_days: int = 30
    ) -> Dict:
        """对比回测（兼容旧API）"""
        return self.calculate_simple_backtest(start_date, end_date, holding_days, top_n=10)

    def calculate_benchmark_backtest(
        self,
        start_date: str,
        end_date: str,
        benchmark: str = '000300'
    ) -> Dict:
        """基准对比回测（兼容旧API）"""
        result = self.calculate_simple_backtest(start_date, end_date, holding_days=30, top_n=10)
        result["benchmark"] = benchmark
        return result
