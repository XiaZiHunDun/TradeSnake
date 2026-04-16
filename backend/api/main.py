"""
TradeSnake API 主入口 (Refactored)
"""

import os
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.api.router import router, cp_engine, recommend_engine
from backend.api.limits import limiter
from backend.api.websocket import WebSocketManager


def preload_cp_engine_from_cache():
    """从磁盘缓存预加载战力引擎数据（快速启动）"""
    from backend.engine.cp_engine import create_stock_from_raw

    print("[启动] 从本地缓存预加载战力数据...")
    DATA_DIR = Path("/home/ailearn/projects/TradeSnake/data")

    # 1. 先从市场缓存构建价格映射表
    price_map = {}
    market_files = list(DATA_DIR.glob("market_*_cache.json"))
    for mf in market_files:
        try:
            with open(mf) as fp:
                cache = json.load(fp)
                for item in cache.get("data", []):
                    code = item.get("code", "")
                    price = item.get("price", 0)
                    numeric_code = code.replace("sh", "").replace("sz", "")
                    if numeric_code and price > 0:
                        price_map[numeric_code] = {
                            "price": price,
                            "change_pct": item.get("change_pct", 0),
                            "high": item.get("high", price),
                            "low": item.get("low", price),
                            "name": item.get("name", numeric_code),
                            "original_code": code,
                        }
        except Exception:
            continue

    print(f"[启动] 从市场缓存中找到 {len(price_map)} 只股票的价格")

    # 2. 读取财务缓存加载股票
    fin_files = list(DATA_DIR.glob("financial_*.json"))
    print(f"[启动] 发现 {len(fin_files)} 个财务缓存文件")

    loaded = 0
    for f in fin_files:
        try:
            with open(f) as fp:
                cache = json.load(fp)
                data = cache.get("data", {})

            code = f.stem.replace("financial_", "")
            market_info = price_map.get(code, {})
            price = market_info.get("price", data.get("price", 0))
            change_pct = market_info.get("change_pct", data.get("change_pct", 0))
            high = market_info.get("high", data.get("high", price))
            low = market_info.get("low", data.get("low", price))

            if price <= 0:
                continue

            def safe_float(val, default=0):
                return float(val) if val is not None else default

            stock = create_stock_from_raw(
                code=code,
                name=market_info.get("name", data.get("name", code)),
                price=price,
                pe=safe_float(data.get("pe")),
                roe=safe_float(data.get("roe")),
                net_profit_growth=safe_float(data.get("net_profit_growth")),
                revenue_growth=safe_float(data.get("revenue_growth")),
                change_pct=change_pct,
                pb=safe_float(data.get("pb")),
                gross_margin=safe_float(data.get("gross_margin")),
                revenue=safe_float(data.get("revenue")),
                cashflow=safe_float(data.get("cashflow")),
                debt_ratio=safe_float(data.get("debt_ratio")),
                volume=0,
                amount=0,
                dividend_yield=safe_float(data.get("dividend_yield")),
                market_cap=safe_float(data.get("market_cap")),
                high=high,
                low=low,
                data_quality=data.get("data_quality", "medium"),
                current_ratio=safe_float(data.get("current_ratio")),
                interest_coverage=safe_float(data.get("interest_coverage")),
                deducted_net_profit=safe_float(data.get("deducted_net_profit"))
            )

            cp_engine.add_stock(stock)
            loaded += 1

        except Exception as e:
            continue

    if cp_engine.stocks:
        cp_engine.calculate_all()
        from backend.api import router as router_module
        router_module.last_update_time = datetime.now().isoformat()
        print(f"[启动] 已预加载 {len(cp_engine.stocks)} 只股票到战力引擎")

    return loaded


def preload_cp_engine_from_history(allowed_codes: Optional[Set[str]] = None):
    """从SQLite stocks表快速预加载战力引擎数据（启动用）

    注意：之前使用cp_history表，但该表只存储基础CP字段（缺少PE/ROE等财务数据）。
    现在改用stocks表，该表存储完整数据（含所有财务字段），确保战力引擎启动时
    拥有完整的股票数据。

    与 preload_cp_engine_from_cache 的区别：
    - 直接从SQLite读取已计算的CP分数，无需重新计算
    - 加载速度快（<1秒 vs 2855文件的慢速加载）
    - 使用预计算的分数（可能有轻微滞后）

    Args:
        allowed_codes: 若给定（如 StockSelector 核心池+活跃池），仅加载这些代码；
            若无交集则回退为全表 total_cp 前 300。
    """
    from backend.engine.cp_engine import StockCP
    import sqlite3

    print("[启动] 从stocks表快速预加载战力数据...")
    DB_PATH = "/home/ailearn/projects/TradeSnake/data/tradesnake.db"

    sql_select = """
            SELECT code, name, price,
                   pe, roe, net_profit_growth, revenue_growth, change_pct,
                   pb, gross_margin, revenue, cashflow, debt_ratio,
                   growth_score, value_score, quality_score,
                   momentum_score, risk_score, total_cp,
                   data_quality, sector
            FROM stocks
    """

    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row

        rows = []
        if allowed_codes:
            codes_list = [str(c).strip() for c in allowed_codes if c]
            by_code: Dict[str, Any] = {}
            chunk_size = 400
            for i in range(0, len(codes_list), chunk_size):
                chunk = codes_list[i : i + chunk_size]
                placeholders = ",".join(["?"] * len(chunk))
                cur = conn.execute(
                    f"{sql_select} WHERE code IN ({placeholders})",
                    chunk,
                )
                for row in cur.fetchall():
                    by_code[str(row["code"])] = row
            rows = sorted(by_code.values(), key=lambda r: float(r["total_cp"] or 0), reverse=True)

        if not rows:
            cursor = conn.execute(f"{sql_select} ORDER BY total_cp DESC LIMIT 300")
            rows = cursor.fetchall()

        loaded = 0
        for row in rows:
            try:
                stock = StockCP.from_precalculated(
                    code=str(row['code']),
                    name=str(row['name']),
                    price=float(row['price'] or 0),
                    total_cp=float(row['total_cp'] or 0),
                    growth_score=float(row['growth_score'] or 0),
                    value_score=float(row['value_score'] or 0),
                    quality_score=float(row['quality_score'] or 0),
                    momentum_score=float(row['momentum_score'] or 0),
                    risk_score=float(row['risk_score'] or 0),
                    pe=float(row['pe'] or 0),
                    roe=float(row['roe'] or 0),
                    net_profit_growth=float(row['net_profit_growth'] or 0),
                    revenue_growth=float(row['revenue_growth'] or 0),
                    change_pct=float(row['change_pct'] or 0),
                    pb=float(row['pb'] or 0),
                    gross_margin=float(row['gross_margin'] or 0),
                    revenue=float(row['revenue'] or 0),
                    cashflow=float(row['cashflow'] or 0),
                    debt_ratio=float(row['debt_ratio'] or 0),
                    data_quality=str(row['data_quality'] or 'medium'),
                    sector=str(row['sector'] or ''),
                    rank=loaded + 1,
                )
                cp_engine.add_stock(stock)
                loaded += 1
            except Exception:
                continue

        conn.close()
        print(f"[启动] 已从stocks表快速加载 {loaded} 只股票到战力引擎")

    except Exception as e:
        print(f"[启动] stocks表快速预加载失败: {e}")


class RefreshState:
    """差异化刷新的状态管理"""
    def __init__(self):
        self.last_core_refresh = 0      # 上次核心池刷新时间
        self.last_active_refresh = 0     # 上次活跃池刷新时间
        self.core_stocks = []            # 核心池股票列表
        self.active_stocks = []          # 活跃池股票列表
        self.all_analysable_codes = set() # 所有可分析股票

_refresh_state = RefreshState()

_scheduler_for_background = None
last_pool_rebalance_date: Optional[date] = None


def _normalize_code(raw_code: str) -> str:
    """标准化股票代码"""
    code = raw_code
    if code.startswith('sh'):
        code = code[2:]
    elif code.startswith('sz'):
        code = code[2:]
    return code


async def background_refresh_task():
    """
    后台持续刷新任务 - 差异化池刷新策略

    刷新策略（按 STOCK_SELECTOR_ARCHITECTURE.md v19.5.3）：
    - 核心池：5分钟刷新间隔
    - 活跃池：30分钟刷新间隔
    - 观察池：盘中不刷新（仅盘后批处理）
    """
    from backend.data_manager.fetcher import get_stock_data_api, get_single_stock_data
    from backend.engine.cp_engine import create_stock_from_raw
    from backend.stock_selector.enums import PoolTier

    print("[后台] 启动数据刷新任务（差异化池策略）", flush=True)

    # 初始等待，让服务器先启动完成
    await asyncio.sleep(5)

    while True:
        try:
            import time
            current_time = time.time()

            # 获取 StockSelector
            selector = get_stock_selector()

            # 获取各池股票（按差异化间隔刷新）
            # 核心池：5分钟 = 300秒
            # 活跃池：30分钟 = 1800秒
            should_refresh_core = (current_time - _refresh_state.last_core_refresh) >= 300
            should_refresh_active = (current_time - _refresh_state.last_active_refresh) >= 1800

            if not should_refresh_core and not should_refresh_active:
                # 两边都没到刷新时间，等待较短时间
                wait_time = min(300 - (current_time - _refresh_state.last_core_refresh),
                               1800 - (current_time - _refresh_state.last_active_refresh))
                wait_time = max(wait_time, 10)  # 至少等10秒
                print(f"[后台] 差异化等待 {int(wait_time)} 秒...", flush=True)
                await asyncio.sleep(wait_time)
                continue

            # 获取股票列表
            all_analysable_codes = set(selector.get_all_analysable_codes())
            analysable_codes = all_analysable_codes

            # 分类核心池和活跃池股票
            core_codes = set(selector.get_pool(PoolTier.CORE))
            active_codes = set(selector.get_pool(PoolTier.ACTIVE))
            observe_codes = set(selector.get_pool(PoolTier.OBSERVE))

            # 确定需要刷新的股票
            stocks_to_refresh = []

            if should_refresh_core:
                # 刷新核心池股票
                _refresh_state.core_stocks = list(core_codes & analysable_codes)
                stocks_to_refresh.extend(_refresh_state.core_stocks)
                _refresh_state.last_core_refresh = current_time

            if should_refresh_active:
                # 刷新活跃池股票
                _refresh_state.active_stocks = list(active_codes & analysable_codes)
                stocks_to_refresh.extend(_refresh_state.active_stocks)
                _refresh_state.last_active_refresh = current_time

            # 观察池盘中不刷新（只在盘后批处理）
            observe_in_analysable = observe_codes & analysable_codes
            if observe_in_analysable and len(stocks_to_refresh) < 100:
                # 如果核心+活跃池股票不足100只，可以补充观察池
                # 但这不是常态，只是为了确保 cp_engine 有足够数据
                pass

            print(f"[后台] 核心池 {len(_refresh_state.core_stocks)} 只, 活跃池 {len(_refresh_state.active_stocks)} 只, 待刷新 {len(stocks_to_refresh)} 只", flush=True)

            if not stocks_to_refresh:
                await asyncio.sleep(30)
                continue

            # 获取成交额前1500只股票作为基础数据
            print("[后台] 开始获取股票数据...", flush=True)
            loop = asyncio.get_event_loop()
            all_stocks_data = await loop.run_in_executor(None, lambda: get_stock_data_api(limit=1500))
            print(f"[后台] 获取到 {len(all_stocks_data)} 只股票数据", flush=True)

            # 构建代码到数据的映射，并过滤
            code_to_data = {}
            for data in all_stocks_data:
                code = _normalize_code(data.get('code', ''))
                if code in analysable_codes:
                    code_to_data[code] = data

            # 合并需要刷新的股票数据
            stocks_data = []
            for code in stocks_to_refresh:
                if code in code_to_data:
                    stocks_data.append(code_to_data[code])
                else:
                    # 补充缺失的股票
                    try:
                        single = await loop.run_in_executor(None, lambda c=code: get_single_stock_data(c))
                        if single:
                            stocks_data.append(single)
                    except:
                        pass

            print(f"[后台] 最终加载: {len(stocks_data)} 只", flush=True)

            async with cp_engine._lock if hasattr(cp_engine, '_lock') else asyncio.Lock():
                # 增量更新：仅保留「可分析池」内且本次未刷新的股票
                stocks_to_keep = [
                    s for s in cp_engine.stocks
                    if s.code not in stocks_to_refresh and s.code in analysable_codes
                ]

                # 清空并重新加载需要刷新的股票
                cp_engine.stocks = stocks_to_keep

                for data in stocks_data:
                    code = _normalize_code(data.get('code', ''))

                    stock = create_stock_from_raw(
                        code=code,
                        name=data.get('name', ''),
                        price=data.get('price', 0),
                        pe=data.get('pe', 0),
                        roe=data.get('roe', 0),
                        net_profit_growth=data.get('net_profit_growth', 0),
                        revenue_growth=data.get('revenue_growth', 0),
                        change_pct=data.get('change_pct', 0),
                        pb=data.get('pb', 0),
                        gross_margin=data.get('gross_margin', 0),
                        revenue=data.get('revenue', 0),
                        cashflow=data.get('cashflow', 0),
                        debt_ratio=data.get('debt_ratio', 0),
                        data_quality=data.get('data_quality', 'low')
                    )
                    cp_engine.add_stock(stock)

                cp_engine.calculate_all()

                # 仅保留核心池+活跃池内的股票，与 StockSelector 语义一致
                cp_engine.stocks = [s for s in cp_engine.stocks if s.code in analysable_codes]

                # 持久化到数据库
                from backend.simulator.database import get_db
                from backend.engine.cp_engine.history import save_history
                stock_dicts = [s.to_dict() for s in cp_engine.stocks]
                save_history(stock_dicts)
                _db = get_db()
                _db.batch_upsert_stocks(stock_dicts)

            if _scheduler_for_background and getattr(_scheduler_for_background, "strategy", None):
                try:
                    await loop.run_in_executor(
                        None,
                        lambda: _scheduler_for_background.trading_day_update(limit_per_batch=25),
                    )
                except Exception as _e:
                    print(f"[后台] UpdateScheduler 批次更新跳过: {_e}", flush=True)

            print(f"[后台] 刷新完成，当前 {len(cp_engine.stocks)} 只股票", flush=True)

            # 更新全局可分析代码集合
            _refresh_state.all_analysable_codes = analysable_codes

        except asyncio.CancelledError:
            print("[后台] 刷新任务已停止")
            break
        except Exception as e:
            print(f"[后台] 刷新出错: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(60)


async def pool_rebalance_background_task():
    """交易日收盘后触发一次股票池再平衡（refresh_pools）。"""
    global last_pool_rebalance_date
    await asyncio.sleep(180)
    while True:
        try:
            from backend.engine.cp_engine.trading_time import get_trading_status
            from backend.data_manager.fetcher import StockDataFetcher
            from backend.stock_selector.market_snapshot import (
                build_market_data_from_fetcher_rows,
                merge_market_data_for_stock_list,
            )
            from backend.stock_selector.enums import PoolTier

            now = datetime.now()
            if now.weekday() >= 5:
                await asyncio.sleep(900)
                continue

            st = get_trading_status()
            if now.hour < 15 or st.get("status") != "closed" or st.get("reason") != "已收盘":
                await asyncio.sleep(480)
                continue

            today = now.date()
            if last_pool_rebalance_date == today:
                await asyncio.sleep(1800)
                continue

            sel = get_stock_selector()
            if not sel.is_initialized():
                await asyncio.sleep(600)
                continue

            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(
                None,
                lambda: StockDataFetcher().get_batch_market_data(2000, prefer_top=True, page=0),
            )
            index_flags: Dict[str, Dict[str, bool]] = {}
            for t in (PoolTier.CORE, PoolTier.ACTIVE, PoolTier.OBSERVE):
                for code in sel.get_pool(t):
                    info = sel.get_stock_info(code)
                    if info:
                        index_flags[code] = {
                            "in_hs300": info.in_hs300,
                            "in_zz500": info.in_zz500,
                            "in_zz1000": info.in_zz1000,
                        }
            pool_codes: List[str] = []
            for t in (PoolTier.CORE, PoolTier.ACTIVE, PoolTier.OBSERVE):
                pool_codes.extend(sel.get_pool(t))
            base_md = build_market_data_from_fetcher_rows(raw, index_flags)
            md = merge_market_data_for_stock_list(pool_codes, base_md, index_flags)

            def _run_rebalance():
                return sel.refresh_pools(md)

            stats = await loop.run_in_executor(None, _run_rebalance)
            print(f"[池再平衡] {today} 完成: {stats}", flush=True)
            last_pool_rebalance_date = today
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[池再平衡] 错误: {e}", flush=True)
            import traceback
            traceback.print_exc()
        await asyncio.sleep(600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据"""
    global _scheduler_for_background
    _scheduler_for_background = None

    # 初始化StockSelector（基础实例化，完整初始化需要数据）
    selector = get_stock_selector()

    # 获取必要数据并初始化 StockSelector
    try:
        from backend.data_manager.manager import get_data_manager
        dm = get_data_manager()

        # 获取股票列表
        stock_list = dm.get_stock_list(use_cache=True, force_refresh=False)
        # 格式化股票列表 (转为 StockSelector 需要的格式)
        formatted_stock_list = []
        for s in stock_list:
            name = s.get("name", "")
            # 从名称判断是否ST股
            is_st = "*" in name or "ST" in name or "退市" in name
            # listing_days默认365天，避免次新股排除（实际上市天数从数据库获取）
            formatted_stock_list.append({
                "code": s.get("code", ""),
                "name": name,
                "is_st": is_st,
                "listing_days": s.get("listing_days", 365),
                "in_hs300": False,  # 暂时设为 False，等指数同步
                "in_zz500": False,
                "in_zz1000": False,
            })

        # 获取指数成分
        index_data = dm.get_index_constituents(use_cache=True, force_refresh=False)

        # 处理指数成分，设置 in_hs300/in_zz500/in_zz1000 标志
        hs300_codes = set()
        zz500_codes = set()
        zz1000_codes = set()

        if index_data.get("hs300"):
            hs300_codes = {s["code"] for s in index_data["hs300"]}
        if index_data.get("zz500"):
            zz500_codes = {s["code"] for s in index_data["zz500"]}
        if index_data.get("zz1000"):
            zz1000_codes = {s["code"] for s in index_data["zz1000"]}

        # 更新股票列表中的指数标志
        for s in formatted_stock_list:
            s["in_hs300"] = s["code"] in hs300_codes
            s["in_zz500"] = s["code"] in zz500_codes
            s["in_zz1000"] = s["code"] in zz1000_codes

        print(f"[启动] 指数成分: 沪深300={len(hs300_codes)}, 中证500={len(zz500_codes)}, 中证1000={len(zz1000_codes)}")

        from backend.data_manager.fetcher import StockDataFetcher
        from backend.stock_selector.market_snapshot import (
            build_market_data_from_fetcher_rows,
            merge_market_data_for_stock_list,
        )

        print("[启动] 拉取行情用于股票池流动性与成交额排名...", flush=True)
        fetch_rows = StockDataFetcher().get_batch_market_data(2000, prefer_top=True, page=0)
        index_flags_by_code = {
            str(s.get("code", "")): {
                "in_hs300": bool(s.get("in_hs300")),
                "in_zz500": bool(s.get("in_zz500")),
                "in_zz1000": bool(s.get("in_zz1000")),
            }
            for s in formatted_stock_list
            if s.get("code")
        }
        base_market = build_market_data_from_fetcher_rows(fetch_rows, index_flags_by_code)
        all_list_codes = [str(s.get("code", "")) for s in formatted_stock_list if s.get("code")]
        market_data = merge_market_data_for_stock_list(all_list_codes, base_market, index_flags_by_code)

        financial_data = {}

        # 注册 UpdateScheduler 必须在 initialize 之前，以便初始化入池事件能写入调度队列
        scheduler = None
        try:
            from backend.data_manager.update_scheduler import UpdateScheduler, StockSelectorCallback
            from backend.stock_selector.update_strategy import UpdateStrategyProvider

            pool_manager = getattr(selector, '_pm', None)
            if pool_manager is None:
                pool_manager = getattr(selector, 'pool_manager', None)

            if pool_manager is None:
                print("[启动] UpdateScheduler 使用简化模式（PoolManager 未直接暴露）")
                strategy_provider = None
            else:
                strategy_provider = UpdateStrategyProvider(pool_manager)

            scheduler = UpdateScheduler(dm, strategy_provider)
            selector.register_callback(StockSelectorCallback(scheduler))
            app.state.scheduler = scheduler
            print("[启动] UpdateScheduler + StockSelectorCallback 注册完成")
        except Exception as e:
            print(f"[启动] UpdateScheduler 注册失败: {e}")
            import traceback
            traceback.print_exc()

        _scheduler_for_background = scheduler

        # 初始化 StockSelector
        if formatted_stock_list:
            selector.initialize(formatted_stock_list, market_data, financial_data)
            print(f"[启动] StockSelector 初始化完成: {selector.get_pool_stats()}")
        else:
            print(f"[启动] StockSelector 初始化跳过: stock_list={len(formatted_stock_list)}")

    except Exception as e:
        print(f"[启动] StockSelector 初始化失败: {e}")
        import traceback
        traceback.print_exc()

    # 注册 Recommender 回调
    try:
        from backend.recommender.recommend_engine import RecommenderCallback
        recommender_callback = RecommenderCallback(recommend_engine)
        selector.register_recommender_callback(recommender_callback)
        print("[启动] RecommenderCallback 注册完成")
    except Exception as e:
        print(f"[启动] RecommenderCallback 注册失败: {e}")

    # preload_cp_engine_from_cache()  # 临时禁用 - 加载2855个文件太慢
    # 改用快速版本：从SQLite stocks 加载；默认仅加载核心池+活跃池代码
    preload_allowed: Optional[Set[str]] = None
    if selector.is_initialized():
        _codes = set(selector.get_all_analysable_codes())
        if _codes:
            preload_allowed = _codes
    preload_cp_engine_from_history(allowed_codes=preload_allowed)

    # 启动后台刷新任务（会延迟5秒后执行）
    refresh_task = asyncio.create_task(background_refresh_task())
    pool_rebalance_task = asyncio.create_task(pool_rebalance_background_task())

    print("[启动] 服务已就绪")

    yield

    # 正确取消后台任务
    pool_rebalance_task.cancel()
    refresh_task.cancel()
    for t in (pool_rebalance_task, refresh_task):
        try:
            await asyncio.wait_for(t, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass
    print("[关闭] 服务关闭")


app = FastAPI(
    title="TradeSnake API",
    description="股市贪吃蛇 - 战力值计算API",
    version="18.x",
    lifespan=lifespan
)

# 全局StockSelector实例（延迟初始化）
_stock_selector = None


def get_stock_selector():
    """获取StockSelector单例"""
    global _stock_selector
    if _stock_selector is None:
        try:
            from backend.stock_selector import StockSelector
            _stock_selector = StockSelector()
            print("[启动] StockSelector 初始化完成")
        except Exception as e:
            print(f"[启动] StockSelector 初始化失败: {e}")
    return _stock_selector


ws_manager = WebSocketManager()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def get_cors_origins():
    env_origins = os.environ.get("CORS_ORIGINS", "")
    if env_origins:
        return [origin.strip() for origin in env_origins.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://localhost:5174"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/")
async def root():
    return {
        "name": "TradeSnake API",
        "version": "18.x",
        "description": "股市贪吃蛇 - 战力值计算API"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
