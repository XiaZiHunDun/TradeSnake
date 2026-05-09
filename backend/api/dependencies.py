"""共享依赖 — 所有子路由从此处获取引擎实例"""
import asyncio
from concurrent.futures import ThreadPoolExecutor

from backend.engine.cp_engine import CPEngine, StockCP
from backend.recommender.recommend_engine import RecommendEngine
from backend.simulator.database import get_db
from backend.simulator.account import Account
from backend.simulator.portfolio import Portfolio
from backend.simulator.trader import Trader
from backend.backtester.backtest import BacktestEngine

# 全局实例
cp_engine = CPEngine()
recommend_engine = RecommendEngine()
db = get_db()
account = Account()
portfolio = Portfolio()
trader = Trader()
backtest_engine = BacktestEngine()

executor = ThreadPoolExecutor(max_workers=2)
cp_lock = asyncio.Lock()
last_update_time: str | None = None


def get_stock_selector():
    """获取 StockSelector 单例（延迟导入避免循环）"""
    from backend.api.main import get_stock_selector as _get
    return _get()
