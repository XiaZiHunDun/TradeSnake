"""
模拟炒股模块 - Simulator v19.8
=============================
职责：交易执行、持仓管理、账户追踪

单人模拟炒股 v19.8:
- 市价单按当前最新价立即成交
- 限价单挂单等待价格满足条件
- FIFO批次管理持仓
- T+1交易限制
- 冻结资金机制
- 涨跌停限制（依赖data_manager提供is_limit_up/is_limit_down）

v19.8修复：
- 修复导入路径错误（TRADE_COST）
- 盈亏计算使用FIFO匹配买卖批次
- 最大回撤使用快照表计算
- 限价买入成交添加费用流水记录
"""

from .database import Database, get_db
from .account import Account, COMMISSION_RATE, MIN_COMMISSION, STAMP_TAX_RATE, TRANSFER_FEE_RATE
from .portfolio import Portfolio
from .trader import Trader, OrderError
from .stats import Stats
from .risk_control import RiskControl

__all__ = [
    # 数据库
    'Database', 'get_db',
    # 账户
    'Account',
    'COMMISSION_RATE', 'MIN_COMMISSION', 'STAMP_TAX_RATE', 'TRANSFER_FEE_RATE',
    # 持仓
    'Portfolio',
    # 交易
    'Trader', 'OrderError',
    # 统计
    'Stats',
    # 风控
    'RiskControl',
]
