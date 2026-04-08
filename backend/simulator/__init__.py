"""
模拟炒股模块 - Simulator v19.7
=============================
职责：交易执行、持仓管理、账户追踪

单人模拟炒股 v19.7:
- 市价单按当前最新价立即成交
- 限价单挂单等待价格满足条件
- FIFO批次管理持仓
- T+1交易限制
- 冻结资金机制

v19.7新增：
- 每日持仓快照记录（holding_snapshots表）
- 换股效果验证
- 战力预测准确性分析
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
