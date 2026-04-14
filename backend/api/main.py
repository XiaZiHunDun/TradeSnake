"""
TradeSnake API 主入口 (Refactored)
"""

import os
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.api.router import router, cp_engine
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


async def background_refresh_task():
    """后台持续刷新任务"""
    from backend.data_manager.fetcher import get_stock_data_api
    from backend.engine.cp_engine import create_stock_from_raw

    print("[后台] 启动数据刷新任务")

    # 初始等待，让服务器先启动完成
    await asyncio.sleep(5)

    while True:
        try:
            from backend.engine.cp_engine.refresh_strategy import get_refresh_interval
            interval = get_refresh_interval()
            print(f"[后台] 等待 {interval} 秒后刷新...")
            await asyncio.sleep(interval)

            # 执行增量刷新（在线程池中执行，避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            stocks_data = await loop.run_in_executor(None, lambda: get_stock_data_api(limit=100))

            async with cp_engine._lock if hasattr(cp_engine, '_lock') else asyncio.Lock():
                for data in stocks_data:
                    stock = create_stock_from_raw(
                        code=data.get('code', ''),
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

                # 持久化到数据库
                from backend.simulator.database import get_db
                from backend.engine.cp_engine.history import save_history
                stock_dicts = [s.to_dict() for s in cp_engine.stocks]
                save_history(stock_dicts)
                _db = get_db()
                _db.batch_upsert_stocks(stock_dicts)

            print(f"[后台] 刷新完成，当前 {len(cp_engine.stocks)} 只股票")

        except asyncio.CancelledError:
            print("[后台] 刷新任务已停止")
            break
        except Exception as e:
            print(f"[后台] 刷新出错: {e}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据"""
    # 初始化StockSelector（基础实例化，完整初始化需要数据）
    selector = get_stock_selector()
    if selector is not None:
        # 注册UpdateScheduler回调（用于联动data_manager更新调度）
        try:
            from backend.data_manager.update_scheduler import UpdateScheduler, StockSelectorCallback
            from backend.data_manager.manager import get_data_manager
            dm = get_data_manager()
            scheduler = UpdateScheduler(dm, None)  # 临时None，后续需要UpdateStrategyProvider
            callback = StockSelectorCallback(scheduler)
            selector.register_callback(callback)
            print("[启动] StockSelector 回调注册完成")
        except Exception as e:
            print(f"[启动] StockSelector 回调注册失败: {e}")

    # preload_cp_engine_from_cache()  # 临时禁用 - 加载2855个文件太慢

    # 启动后台刷新任务（会延迟5秒后执行）
    refresh_task = asyncio.create_task(background_refresh_task())

    print("[启动] 服务已就绪")

    yield

    # 正确取消后台任务
    refresh_task.cancel()
    try:
        await asyncio.wait_for(refresh_task, timeout=5.0)
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
