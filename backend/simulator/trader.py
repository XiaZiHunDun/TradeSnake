"""
交易执行 - Trader v19.1
"""

import time
import threading
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from .database import get_db
from .account import Account, COMMISSION_RATE, MIN_COMMISSION, STAMP_TAX_RATE, TRANSFER_FEE_RATE
from .portfolio import Portfolio
from .risk_control import RiskControl
from backend.risk.risk_control import RiskManager

logger = logging.getLogger(__name__)


class OrderError(Exception):
    """订单异常"""
    pass


class Trader:
    """交易执行器 v19.1"""

    def __init__(self):
        self.db = get_db()
        self.account = Account()
        self.portfolio = Portfolio()
        self._is_running = False
        self._poll_thread = None

    def get_market_price(self, code: str, action: str) -> float:
        """获取市价单成交价（v19.1修正）

        注意：不按涨跌停价成交，直接按当前最新价
        涨跌停时无法成交（由风控检查拦截）
        """
        from backend.data_manager.fetcher import get_single_stock_data

        stock = get_single_stock_data(code)
        if not stock:
            raise OrderError(f"股票{code}不存在")

        price = stock.get('price', 0)
        if price <= 0:
            raise OrderError(f"股票{code}价格无效")

        # 涨跌停检查
        if action == 'buy' and stock.get('is_limit_up'):
            raise OrderError("涨停无法买入")
        if action == 'sell' and stock.get('is_limit_down'):
            raise OrderError("跌停无法卖出")

        return price

    def buy(self, code: str, quantity: int, price: float = None,
            order_type: str = 'market', stop_loss: float = 0, take_profit: float = 0) -> Dict:
        """买入股票

        Args:
            code: 股票代码
            quantity: 数量（手）
            price: 委托价格（None=市价）
            order_type: 'market' | 'limit'
            stop_loss: 止损价
            take_profit: 止盈价

        Returns:
            成交/委托结果
        """
        from backend.data_manager.fetcher import get_single_stock_data

        stock = get_single_stock_data(code)
        if not stock:
            return {'success': False, 'error': f"股票{code}不存在"}

        name = stock.get('name', code)
        current_price = stock.get('price', 0)

        # 确定成交价
        if order_type == 'market':
            # 市价单：按当前价，立即成交
            try:
                exec_price = self.get_market_price(code, 'buy')
            except OrderError as e:
                return {'success': False, 'error': str(e)}
        else:
            # 限价单
            if price is None:
                price = current_price
            # 涨跌停检查
            if stock.get('is_limit_up'):
                return {'success': False, 'error': '涨停无法买入'}
            exec_price = price

        # 风控检查（使用RiskControl.check_all()，包含所有风控规则）
        can_trade, reason = RiskControl.check_all(
            'buy', code, quantity, exec_price, self.account, self.portfolio
        )
        if not can_trade:
            return {'success': False, 'error': reason}

        # 计算冻结金额
        freeze_amount = self.account.calculate_freeze(quantity, exec_price, is_buy=True)

        # 市价单立即成交
        if order_type == 'market':
            return self._execute_market_buy(code, name, quantity, exec_price, stop_loss, take_profit)
        else:
            # 限价单：创建pending委托
            return self._create_limit_buy_order(code, name, quantity, exec_price, freeze_amount, stop_loss, take_profit)

    def _execute_market_buy(self, code: str, name: str, quantity: int,
                           price: float, stop_loss: float = 0, take_profit: float = 0) -> Dict:
        """执行市价买入（立即成交）"""
        # 计算费用
        amount = quantity * price
        commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
        transfer_fee = amount * TRANSFER_FEE_RATE
        total_cost = amount + commission + transfer_fee

        # 扣除资金
        self.account.deduct_cost(total_cost)

        # 增加持仓
        self.portfolio.add_holding(code, name, quantity, price, stop_loss=stop_loss, take_profit=take_profit)

        # 记录交易
        trade_id = self.db.record_trade({
            'code': code,
            'name': name,
            'action': 'buy',
            'quantity': quantity,
            'price': price,
            'commission': commission,
            'stamp_tax': 0,
            'transfer_fee': transfer_fee,
            'total_amount': total_cost
        })

        # 记录费用流水
        self.account.record_commission(trade_id, commission, 0, transfer_fee)

        # 更新冷却
        self.db.update_trade_cooldown(code)

        return {
            'success': True,
            'order_id': trade_id,
            'code': code,
            'name': name,
            'action': 'buy',
            'quantity': quantity,
            'price': price,
            'commission': round(commission, 2),
            'transfer_fee': round(transfer_fee, 2),
            'total_cost': round(total_cost, 2),
            'remaining_cash': round(self.account.cash, 2),
            'trade_time': datetime.now().isoformat()
        }

    def _create_limit_buy_order(self, code: str, name: str, quantity: int,
                               price: float, freeze_amount: float,
                               stop_loss: float = 0, take_profit: float = 0) -> Dict:
        """创建限价买入委托（挂单）"""
        # 创建委托单
        order_id = self.db.create_order({
            'code': code,
            'name': name,
            'action': 'buy',
            'order_type': 'limit',
            'price': price,
            'quantity': quantity,
            'frozen_amount': freeze_amount,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        })

        # 记录冻结流水
        self.db.record_flow({
            'change_type': 'buy_freeze',
            'amount': -freeze_amount,
            'balance_after': self.account.cash,
            'order_id': order_id,
            'remark': f'限价买入委托{order_id}冻结'
        })

        return {
            'success': True,
            'order_id': order_id,
            'status': 'pending',
            'code': code,
            'name': name,
            'action': 'buy',
            'order_type': 'limit',
            'quantity': quantity,
            'price': price,
            'frozen_amount': round(freeze_amount, 2),
            'message': '限价委托已提交，等待成交',
            'created_at': datetime.now().isoformat()
        }

    def sell(self, code: str, quantity: int, price: float = None,
             order_type: str = 'market', reason: str = '') -> Dict:
        """卖出股票

        Args:
            code: 股票代码
            quantity: 数量
            price: 委托价格（None=市价）
            order_type: 'market' | 'limit'
            reason: 卖出原因（用于风控记录）

        Returns:
            成交/委托结果
        """
        from backend.data_manager.fetcher import get_single_stock_data

        stock = get_single_stock_data(code)
        if not stock:
            return {'success': False, 'error': f"股票{code}不存在"}

        name = stock.get('name', code)

        # 确定成交价（需要先获取价格才能进行风控检查）
        if order_type == 'market':
            try:
                exec_price = self.get_market_price(code, 'sell')
            except OrderError as e:
                return {'success': False, 'error': str(e)}
        else:
            if price is None:
                price = stock.get('price', 0)
            if stock.get('is_limit_down'):
                return {'success': False, 'error': '跌停无法卖出'}
            exec_price = price

        # 风控检查（使用RiskControl.check_all()，包含T+1检查、持仓检查等所有风控规则）
        can_trade, risk_reason = RiskControl.check_all(
            'sell', code, quantity, exec_price, self.account, self.portfolio
        )
        if not can_trade:
            return {'success': False, 'error': risk_reason}

        # 市价单立即成交
        if order_type == 'market':
            return self._execute_market_sell(code, name, quantity, exec_price, reason)
        else:
            # 限价单：创建pending委托
            return self._create_limit_sell_order(code, name, quantity, exec_price, reason)

    def _execute_market_sell(self, code: str, name: str, quantity: int,
                           price: float, reason: str = '') -> Dict:
        """执行市价卖出（立即成交）"""
        # 计算费用
        amount = quantity * price
        commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
        stamp_tax = amount * STAMP_TAX_RATE
        transfer_fee = amount * TRANSFER_FEE_RATE
        total_proceeds = amount - commission - stamp_tax - transfer_fee

        # 减少持仓
        success, details = self.portfolio.reduce_holding(code, quantity)
        if not success:
            return {'success': False, 'error': '持仓不足'}

        # 增加资金
        self.account.add_proceeds(total_proceeds)

        # 记录交易（包含 sell_reason）
        trade_id = self.db.record_trade({
            'code': code,
            'name': name,
            'action': 'sell',
            'quantity': quantity,
            'price': price,
            'commission': commission,
            'stamp_tax': stamp_tax,
            'transfer_fee': transfer_fee,
            'total_amount': total_proceeds,
            'sell_reason': reason  # v21 新增：卖出原因
        })

        # 记录费用流水
        self.account.record_commission(trade_id, commission, stamp_tax, transfer_fee)

        # 更新冷却
        self.db.update_trade_cooldown(code)

        return {
            'success': True,
            'order_id': trade_id,
            'code': code,
            'name': name,
            'action': 'sell',
            'quantity': quantity,
            'price': price,
            'sell_value': round(amount, 2),
            'commission': round(commission, 2),
            'stamp_tax': round(stamp_tax, 2),
            'transfer_fee': round(transfer_fee, 2),
            'total_proceeds': round(total_proceeds, 2),
            'remaining_cash': round(self.account.cash, 2),
            'trade_time': datetime.now().isoformat()
        }

    def _create_limit_sell_order(self, code: str, name: str, quantity: int,
                                 price: float, reason: str = '') -> Dict:
        """创建限价卖出委托（挂单）"""
        order_id = self.db.create_order({
            'code': code,
            'name': name,
            'action': 'sell',
            'order_type': 'limit',
            'price': price,
            'quantity': quantity,
            'frozen_amount': 0,  # 卖出冻结的是股份，不是资金
            'reason': reason
        })

        return {
            'success': True,
            'order_id': order_id,
            'status': 'pending',
            'code': code,
            'name': name,
            'action': 'sell',
            'order_type': 'limit',
            'quantity': quantity,
            'price': price,
            'message': '限价委托已提交，等待成交',
            'created_at': datetime.now().isoformat()
        }

    def cancel_order(self, order_id: int) -> Dict:
        """撤销委托单"""
        order = self.db.get_order(order_id)
        if not order:
            return {'success': False, 'error': f'委托单{order_id}不存在'}

        if order['status'] != 'pending':
            return {'success': False, 'error': f'委托单状态为{order["status"]}，无法撤销'}

        # 解冻资金（买入委托）
        if order['action'] == 'buy' and order.get('frozen_amount', 0) > 0:
            # 资金已扣除，只需记录解冻流水
            self.db.record_flow({
                'change_type': 'buy_unfreeze',
                'amount': order['frozen_amount'],
                'balance_after': self.account.cash + order['frozen_amount'],
                'order_id': order_id,
                'remark': f'委托单{order_id}撤单解冻'
            })

        # 更新订单状态
        self.db.cancel_order(order_id, '用户撤单')

        return {
            'success': True,
            'order_id': order_id,
            'status': 'cancelled',
            'message': '撤单成功',
            'cancelled_at': datetime.now().isoformat()
        }

    def check_pending_orders(self, code: str = None):
        """检查限价挂单是否可成交（v19.1新增）

        触发机制：
        - 事件驱动：行情更新时调用
        - 定时轮询：启动后台线程定期检查
        - 手动调用：查询账户时触发
        """
        from backend.data_manager.fetcher import get_single_stock_data

        pending = self.db.get_pending_orders(code)

        for order in pending:
            try:
                stock = get_single_stock_data(order['code'])
                if not stock:
                    continue

                current_price = stock.get('price', 0)
                if current_price <= 0:
                    continue

                can_match = False

                if order['action'] == 'buy':
                    # 买入：市价 <= 限价 时成交
                    if current_price <= order['price']:
                        can_match = True
                else:
                    # 卖出：市价 >= 限价 时成交
                    if current_price >= order['price']:
                        can_match = True

                if can_match:
                    # 执行成交
                    if order['action'] == 'buy':
                        self._execute_limit_buy_fill(order, current_price)
                    else:
                        self._execute_limit_sell_fill(order, current_price, order.get('reason', ''))

            except Exception as e:
                # 继续处理其他订单
                continue

    def _execute_limit_buy_fill(self, order: Dict, current_price: float):
        """限价买入成交"""
        quantity = order['quantity']
        code = order['code']
        name = order['name']

        # 计算实际费用
        amount = quantity * current_price
        commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
        transfer_fee = amount * TRANSFER_FEE_RATE
        total_cost = amount + commission + transfer_fee

        # 解冻并扣减资金
        frozen_amount = order.get('frozen_amount', 0)
        refund = frozen_amount - total_cost

        self.account.deduct_cost(total_cost)
        if refund > 0:
            self.db.record_flow({
                'change_type': 'buy_refund',
                'amount': refund,
                'balance_after': self.account.cash,
                'order_id': order['id'],
                'remark': f'限价买入{order["id"]}差额返还'
            })

        # 增加持仓
        stop_loss = order.get('stop_loss', 0)
        take_profit = order.get('take_profit', 0)
        self.portfolio.add_holding(code, name, quantity, current_price, stop_loss=stop_loss, take_profit=take_profit)

        # 记录交易
        trade_id = self.db.record_trade({
            'code': code,
            'name': name,
            'action': 'buy',
            'quantity': quantity,
            'price': current_price,
            'commission': commission,
            'stamp_tax': 0,
            'transfer_fee': transfer_fee,
            'total_amount': total_cost
        })

        # 记录费用流水
        self.account.record_commission(trade_id, commission, 0, transfer_fee)

        # 更新订单状态
        self.db.update_order_status(order['id'], 'filled',
                                   filled_quantity=quantity,
                                   filled_price=current_price)

        # 更新冷却
        self.db.update_trade_cooldown(code)

    def _execute_limit_sell_fill(self, order: Dict, current_price: float, reason: str = ''):
        """限价卖出成交"""
        quantity = order['quantity']
        code = order['code']
        name = order['name']

        # 计算实际费用
        amount = quantity * current_price
        commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
        stamp_tax = amount * STAMP_TAX_RATE
        transfer_fee = amount * TRANSFER_FEE_RATE
        total_proceeds = amount - commission - stamp_tax - transfer_fee

        # 减少持仓
        success, details = self.portfolio.reduce_holding(code, quantity)
        if not success:
            return {'success': False, 'error': '持仓不足'}

        # 增加资金
        self.account.add_proceeds(total_proceeds)

        # 记录交易
        trade_id = self.db.record_trade({
            'code': code,
            'name': name,
            'action': 'sell',
            'quantity': quantity,
            'price': current_price,
            'commission': commission,
            'stamp_tax': stamp_tax,
            'transfer_fee': transfer_fee,
            'total_amount': total_proceeds,
            'sell_reason': reason
        })

        # 更新订单状态
        self.db.update_order_status(order['id'], 'filled',
                                   filled_quantity=quantity,
                                   filled_price=current_price)

        # 更新冷却
        self.db.update_trade_cooldown(code)

    def get_pending_orders(self, code: str = None) -> List[Dict]:
        """获取待成交委托"""
        return self.db.get_pending_orders(code)

    def get_order_history(self, limit: int = 50) -> List[Dict]:
        """获取委托历史"""
        return self.db.get_order_history(limit)

    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """获取交易历史"""
        return self.db.get_trades(limit)

    def get_position(self, code: str) -> Optional[Dict]:
        """获取持仓详情"""
        from backend.data_manager.fetcher import get_single_stock_data

        holding = self.portfolio.get_holding(code)
        if not holding:
            return None

        stock = get_single_stock_data(code)
        current_price = stock.get('price', 0) if stock else 0

        profit_info = self.portfolio.get_holding_profit(code, current_price)

        return {
            'code': code,
            'name': holding.get('name', ''),
            'quantity': holding.get('total_quantity', 0),
            'avg_cost_price': holding.get('avg_cost_price', 0),
            'current_price': current_price,
            **profit_info,
            'earliest_bought_at': holding.get('earliest_bought_at', ''),
            'latest_bought_at': holding.get('latest_bought_at', '')
        }

    # ==================== 定时轮询（可选） ====================

    def start_polling(self, interval_sec: float = 5.0):
        """启动定时检查限价单（后台线程）"""
        if self._is_running:
            return

        self._is_running = True
        self._poll_thread = threading.Thread(
            target=self._polling_loop,
            args=(interval_sec,),
            daemon=True
        )
        self._poll_thread.start()

    def stop_polling(self):
        """停止定时检查"""
        self._is_running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=1)

    def _polling_loop(self, interval_sec: float):
        """定时轮询循环"""
        while self._is_running:
            try:
                self.check_pending_orders()
            except Exception as e:
                logger.warning(f"_polling_loop: check_pending_orders failed: {e}")
            time.sleep(interval_sec)

    # ==================== 风控检查（可选） ====================

    def check_risk_and_execute(self) -> List[Dict]:
        """每日风控检查

        自动执行止损、尾随止损、组合熔断
        Returns: list of executed trades
        """
        risk_manager = RiskManager()
        executed = []

        # 获取账户信息
        account_info = {
            'total_assets': self.account.total_assets,
            'peak_assets': getattr(self.account, 'peak_assets', self.account.total_assets),
        }

        # 1. 检查组合回撤
        should_reduce, reason, action = risk_manager.check_portfolio_drawdown(account_info)
        if should_reduce:
            holdings = self.portfolio.get_holdings()
            if action == 'clear':
                # 清仓
                for h in holdings:
                    code = h.get('code', '')
                    qty = h.get('total_quantity', 0)
                    if qty > 0:
                        try:
                            result = self.sell(code, qty, reason=reason)
                            if result.get('success'):
                                executed.append(result)
                        except Exception as e:
                            logger.warning(f"风控{action}卖出失败 {code}: {e}")
            elif action == 'reduce':
                # 减半仓
                for h in holdings:
                    code = h.get('code', '')
                    qty = h.get('total_quantity', 0)
                    reduce_qty = qty // 2
                    if reduce_qty > 0:
                        try:
                            result = self.sell(code, reduce_qty, reason=reason)
                            if result.get('success'):
                                executed.append(result)
                        except Exception as e:
                            logger.warning(f"风控{action}卖出失败 {code}: {e}")

        # 2. 更新持仓最高价
        holdings = self.portfolio.get_holdings()
        prices = {}
        for h in holdings:
            code = h.get('code', '')
            lookup_code = code.replace('sh', '').replace('sz', '')
            stock = self.db.get_stock(lookup_code)
            if stock and stock.get('price', 0) > 0:
                prices[code] = stock.get('price', 0)
        if prices:
            self.portfolio.update_peak_prices(prices)

        # 3. 检查每只持仓的止损
        for h in holdings:
            code = h.get('code', '')
            current_price = prices.get(code, 0)
            cost_price = h.get('avg_cost_price', 0)
            peak_price = h.get('peak_price', current_price)

            position = {
                'current_price': current_price,
                'cost_price': cost_price,
                'peak_price': peak_price,
            }

            should_sell, reason = risk_manager.check_stop_loss(position)
            if not should_sell:
                should_sell, reason = risk_manager.check_trailing_stop(position)
            if should_sell:
                qty = h.get('total_quantity', 0)
                if qty > 0:
                    try:
                        result = self.sell(code, qty, reason=reason)
                        if result.get('success'):
                            executed.append(result)
                            logger.info(f"风控卖出 {code}: {reason}")
                    except Exception as e:
                        logger.warning(f"风控止损卖出失败 {code}: {e}")

        return executed

    def get_kelly_size(self, code: str, price: float) -> int:
        """获取 Kelly 建议手数

        Args:
            code: 股票代码
            price: 当前价格

        Returns:
            建议买入股数（100的整数倍），0表示不建议买入
        """
        risk_manager = RiskManager()
        account_value = self.account.total_assets
        return risk_manager.calculate_kelly_position_size(code, account_value, price)

    def get_market_regime(self) -> str:
        """获取当前市场环境（bull/bear/unknown）"""
        risk_manager = RiskManager()
        return risk_manager.detect_market_regime()

    def get_position_limit(self) -> float:
        """根据市场环境获取仓位限制"""
