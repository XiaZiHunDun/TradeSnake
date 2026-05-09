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
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.api.router import router
from backend.api.routers import maturity
from backend.api.dependencies import cp_engine, recommend_engine
from backend.api.limits import limiter
from backend.api.websocket import WebSocketManager
from backend.config import DATA_DIR, SQLITE_PATH, REFRESH_STATE_FILE


def preload_cp_engine_from_cache():
    """从磁盘缓存预加载战力引擎数据（快速启动）"""
    from backend.engine.cp_engine import create_stock_from_raw

    print("[启动] 从本地缓存预加载战力数据...")

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
        conn = sqlite3.connect(SQLITE_PATH, timeout=10)
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
    # v19.9.3: 持久化状态文件路径
    _STATE_FILE = REFRESH_STATE_FILE

    def __init__(self):
        self.last_core_refresh = 0      # 上次核心池刷新时间
        self.last_active_refresh = 0     # 上次活跃池刷新时间
        self.core_stocks = []            # 核心池股票列表
        self.active_stocks = []          # 活跃池股票列表
        self.all_analysable_codes = set() # 所有可分析股票
        # v19.9.3: 从文件加载上次预测保存日期
        self.last_prediction_save_date = self._load_state_value('last_prediction_save_date')
        # v19.9.7: 从文件加载上次K线填充日期
        self.last_kline_fill_date = self._load_state_value('last_kline_fill_date')
        # v19.9.8: 从文件加载上次分钟K线填充日期
        self.last_minute_kline_fill_date = self._load_state_value('last_minute_kline_fill_date')
        # v19.9.9: 从文件加载上次adj_factor填充日期
        self.last_adj_factor_fill_date = self._load_state_value('last_adj_factor_fill_date')

    def _load_state_value(self, key: str) -> Optional[str]:
        """从文件加载指定状态值"""
        try:
            if self._STATE_FILE.exists():
                with open(self._STATE_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get(key)
        except Exception:
            pass
        return None

    def _save_state_value(self, key: str, value: str):
        """保存状态值到文件"""
        try:
            data = {}
            if self._STATE_FILE.exists():
                try:
                    with open(self._STATE_FILE, 'r') as f:
                        data = json.load(f)
                except Exception:
                    pass
            data[key] = value
            with open(self._STATE_FILE, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    def save_prediction_date(self, date_str: str):
        """保存预测日期到文件"""
        self._save_state_value('last_prediction_save_date', date_str)
        self.last_prediction_save_date = date_str

    def save_kline_fill_date(self, date_str: str):
        """保存K线填充日期到文件"""
        self._save_state_value('last_kline_fill_date', date_str)
        self.last_kline_fill_date = date_str

    def save_minute_kline_fill_date(self, date_str: str):
        """保存分钟K线填充日期到文件"""
        self._save_state_value('last_minute_kline_fill_date', date_str)
        self.last_minute_kline_fill_date = date_str

    def save_adj_factor_fill_date(self, date_str: str):
        """保存adj_factor填充日期到文件 v19.9.9"""
        self._save_state_value('last_adj_factor_fill_date', date_str)
        self.last_adj_factor_fill_date = date_str

_refresh_state = RefreshState()
_cp_engine_lock = asyncio.Lock()  # v19.9.3: 保护 cp_engine.stocks 并发访问

_scheduler_for_background = None
last_pool_rebalance_date: Optional[date] = None


def _normalize_code(raw_code: str) -> str:
    """标准化股票代码为6位格式（去掉sh/sz前缀和.SH/.SZ后缀）"""
    code = raw_code
    # 去除前缀
    if code.startswith('sh'):
        code = code[2:]
    elif code.startswith('sz'):
        code = code[2:]
    # 去除后缀（处理Tushare格式如 000001.SH）
    if '.' in code:
        code = code.split('.')[0]
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
                    except Exception:
                        pass

            print(f"[后台] 最终加载: {len(stocks_data)} 只", flush=True)

            # v19.9.3: 使用 asyncio.Lock 保护 cp_engine.stocks 并发访问
            async with _cp_engine_lock:
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
                if analysable_codes:
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

            # 收盘后（15:00之后）且当日尚未保存预测时，计算并保存预测 v19.8
            import time
            current_struct = time.localtime()
            current_hour = current_struct.tm_hour
            today_date_str = time.strftime("%Y-%m-%d", current_struct)

            if current_hour >= 16 and _refresh_state.last_prediction_save_date != today_date_str:
                # 执行预测计算并保存
                try:
                    from backend.engine import gain_predictor, probability_predictor
                    from backend.data_manager.manager import get_data_manager

                    print(f"[后台] 开始收盘后预测计算并保存...", flush=True)

                    # 获取K线数据
                    dm = get_data_manager()
                    codes_to_predict = [s.code for s in cp_engine.stocks][:500]  # 限制数量避免超时

                    # 计算并保存涨幅预测
                    try:
                        gain_preds = gain_predictor.save_predictions_to_store(codes_to_predict, dm)
                        print(f"[后台] 涨幅预测已保存: {gain_preds}", flush=True)
                    except Exception as pred_e:
                        print(f"[后台] 涨幅预测保存失败: {pred_e}", flush=True)

                    # 计算并保存上涨概率预测
                    try:
                        prob_preds = probability_predictor.save_predictions_to_store(codes_to_predict, dm)
                        print(f"[后台] 上涨概率预测已保存: {prob_preds}", flush=True)
                    except Exception as prob_e:
                        print(f"[后台] 上涨概率预测保存失败: {prob_e}", flush=True)

                    _refresh_state.save_prediction_date(today_date_str)
                    print(f"[后台] 收盘后预测保存完成，日期: {today_date_str}", flush=True)
                except Exception as pred_err:
                    print(f"[后台] 收盘后预测保存出错: {pred_err}", flush=True)

            # 收盘后（16:00之后）且当日尚未填充K线时，执行增量填充 v19.9.7
            if current_hour >= 16 and _refresh_state.last_kline_fill_date != today_date_str:
                try:
                    # v19.9.9: 先获取 Tushare adj_factor 数据到 SQLite
                    if _refresh_state.last_adj_factor_fill_date != today_date_str:
                        try:
                            from backend.data_manager.filler import ExRightFactorFiller
                            print("[后台] 开始收盘后adj_factor填充...", flush=True)
                            adj_filler = ExRightFactorFiller(rate_limit_sleep=0.3)
                            adj_result = adj_filler.fill_all(limit=200)
                            print(f"[后台] adj_factor填充完成: 成功{adj_result.success}, 失败{adj_result.failed}", flush=True)
                            _refresh_state.save_adj_factor_fill_date(today_date_str)
                        except Exception as adj_err:
                            print(f"[后台] adj_factor填充失败: {adj_err}", flush=True)

                    from backend.data_manager.filler import KlineFiller
                    print("[后台] 开始收盘后K线填充...", flush=True)
                    kf = KlineFiller()
                    # 增量填充最近7天的数据
                    result = kf.fill_incremental(days_back=7)
                    print(f"[后台] K线填充完成: 成功{result.success}, 失败{result.failed}, 记录{result.total_records}", flush=True)
                    _refresh_state.save_kline_fill_date(today_date_str)

                    # v19.9.9: KlineFiller 完成后，回填 adj_factor 到 DuckDB
                    try:
                        from backend.data_manager.duckdb_store import get_duckdb_store
                        d = get_duckdb_store()
                        bf_result = d.backfill_adj_factor(batch_size=500)
                        print(f"[后台] adj_factor回填完成: 处理{bf_result.get('symbols_processed', 0)}只, 更新{bf_result.get('rows_updated', 0)}行", flush=True)
                    except Exception as bf_err:
                        print(f"[后台] adj_factor回填失败: {bf_err}", flush=True)
                except Exception as kline_err:
                    print(f"[后台] K线填充失败: {kline_err}", flush=True)

            # 收盘后（16:30之后）且当日尚未填充分钟K线时，执行核心池+活跃池分钟K线填充 v19.9.8
            # 注意：分钟K线获取较慢（每只约2秒），所以限制数量避免阻塞
            if current_hour >= 16 and _refresh_state.last_minute_kline_fill_date != today_date_str:
                try:
                    from backend.data_manager.filler import get_minute_kline_filler
                    from backend.stock_selector.enums import PoolTier
                    print("[后台] 开始收盘后分钟K线填充...", flush=True)
                    minute_filler = get_minute_kline_filler()
                    # 获取核心池+活跃池股票（每天轮换50只，避免耗时过长）
                    selector = get_stock_selector()
                    core_codes = selector.get_pool(PoolTier.CORE)
                    active_codes = selector.get_pool(PoolTier.ACTIVE)
                    # 合并并去重
                    all_pool_codes = list(set(core_codes + active_codes))
                    # 根据日期选择不同的子集（每天约50只，约4天轮换完全部）
                    day_index = datetime.now().timetuple().tm_yday
                    subset_size = 50
                    start_idx = (day_index * subset_size) % len(all_pool_codes) if all_pool_codes else 0
                    # 简单轮换选择
                    codes_to_fill = []
                    remaining = all_pool_codes
                    while len(codes_to_fill) < subset_size and remaining:
                        idx = (start_idx + len(codes_to_fill)) % len(remaining)
                        codes_to_fill.append(remaining[idx])
                    if codes_to_fill:
                        result = minute_filler.fill_all(codes=codes_to_fill, days_back=1)
                        print(f"[后台] 分钟K线填充完成: 成功{result.success}, 失败{result.failed}, 记录{result.total_records}", flush=True)
                    else:
                        print("[后台] 分钟K线填充跳过: 无可填充的股票", flush=True)
                    _refresh_state.save_minute_kline_fill_date(today_date_str)
                except Exception as minute_err:
                    print(f"[后台] 分钟K线填充失败: {minute_err}", flush=True)

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

            # 保存池状态到 SQLite (v19.9.9)
            def _save_pool_state():
                sel._pm.save_state()
            await loop.run_in_executor(None, _save_pool_state)

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

        # v19.9.11: 从 SQLite stocks 表获取财务数据用于选股器准入检查
        financial_data = {}
        try:
            import sqlite3
            conn = sqlite3.connect(SQLITE_PATH)
            cursor = conn.execute("""
                SELECT code, net_profit, revenue_growth, debt_ratio
                FROM stocks WHERE code IN ({})
            """.format(','.join('?' * len(all_list_codes))), all_list_codes)
            for row in cursor:
                code, net_profit, revenue_growth, debt_ratio = row
                financial_data[str(code)] = {
                    'net_profit': net_profit or 0,
                    'revenue_yoy': revenue_growth or 0,
                    'debt_ratio': debt_ratio or 0,
                }
            conn.close()
            print(f"[启动] 财务数据加载完成: {len(financial_data)} 只股票")
        except Exception as e:
            print(f"[启动] 财务数据加载失败: {e}")

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

            # 尝试从持久化状态恢复池组成 (v19.9.9)
            # 注意：只在新池为空时才恢复，避免覆盖已初始化的有效数据
            current_stats = selector.get_pool_stats()
            if sum(current_stats.values()) == 0 and selector._pm.has_persistent_state():
                print("[启动] 检测到空的池状态，尝试从持久化恢复...")
                loaded = selector._pm.load_state()
                if loaded:
                    print(f"[启动] 池状态已从持久化恢复: {selector.get_pool_stats()}")
            else:
                print(f"[启动] 使用新初始化的池状态: {current_stats}")
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


# 全局异常处理器 - 捕获所有未处理的异常
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    error_msg = str(exc)
    # 隐藏 NoneType 等内部错误信息
    detail = error_msg if "NoneType" not in error_msg and "attribute" not in error_msg.lower() else "An internal error occurred"
    print(f"[ERROR] Global exception on {request.method} {request.url.path}: {error_msg}")
    print(f"[ERROR] Traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": detail
        }
    )


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
app.include_router(maturity.router)


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
