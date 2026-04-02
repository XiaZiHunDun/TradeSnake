"""
API路由 - TradeSnake API Routes
"""

import asyncio
from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime

from models.schemas import (
    CPListResponse, SingleStockResponse, StockCPData,
    TradeDecisionResponse, CashOpportunityResponse, TradeCostDetail,
    CPExplanationResponse, HoldingItem, HoldingsImportRequest, HoldingsExportResponse
)
from core.cp_engine import (
    CPEngine, create_stock_from_raw,
    CashCP, TradeDecision, TOTAL_TRADE_COST_RATE, TRADE_COST
)
from core.history import save_history, get_cp_changes, get_stock_history, get_historical_rankings, get_ranking_changes
from core.database import get_db
from data.fetcher import get_stock_data_api, get_single_stock_data
from api.limits import limiter

router = APIRouter()

# 全局战力引擎实例
cp_engine = CPEngine()
last_update_time = None

# 异步锁，保护cp_engine的并发访问
_cp_lock = asyncio.Lock()


def _build_stock_response(stock):
    """构建单股票响应数据（避免重复代码）"""
    return SingleStockResponse(
        code=stock.code,
        name=stock.name,
        price=stock.price,
        pe=stock.pe,
        roe=stock.roe,
        net_profit_growth=stock.net_profit_growth,
        revenue_growth=stock.revenue_growth,
        change_pct=stock.change_pct,
        growth_score=round(stock.growth_score, 2),
        value_score=round(stock.value_score, 2),
        momentum_score=round(stock.momentum_score, 2),
        quality_score=round(stock.quality_score, 2),
        total_cp=round(stock.total_cp, 2),
        risk_score=round(stock.risk_score, 2),
        risk_level=stock.get_risk_level(),
        peg=round(stock.peg, 2),
        pb=stock.pb,
        gross_margin=stock.gross_margin,
        revenue=stock.revenue,
        cashflow=stock.cashflow,
        debt_ratio=stock.debt_ratio,
        dividend_yield=stock.dividend_yield,
        market_cap=stock.market_cap,
        high=stock.high,
        low=stock.low,
        data_quality=stock.data_quality
    )


def _build_stock_cp_data(stock):
    """构建榜单股票数据（避免重复代码）"""
    return StockCPData(
        code=stock.code,
        name=stock.name,
        price=stock.price,
        pe=stock.pe,
        roe=stock.roe,
        net_profit_growth=stock.net_profit_growth,
        revenue_growth=stock.revenue_growth,
        change_pct=stock.change_pct,
        growth_score=round(stock.growth_score, 2),
        value_score=round(stock.value_score, 2),
        momentum_score=round(stock.momentum_score, 2),
        quality_score=round(stock.quality_score, 2),
        total_cp=round(stock.total_cp, 2),
        risk_score=round(stock.risk_score, 2),
        risk_level=stock.get_risk_level(),
        peg=round(stock.peg, 2),
        pb=stock.pb,
        gross_margin=stock.gross_margin,
        revenue=stock.revenue,
        cashflow=stock.cashflow,
        debt_ratio=stock.debt_ratio,
        dividend_yield=stock.dividend_yield,
        market_cap=stock.market_cap,
        high=stock.high,
        low=stock.low,
        data_quality=stock.data_quality
    )


async def refresh_cp_data(limit: int = 100, save_hist: bool = True):
    """刷新战力数据"""
    global last_update_time

    print(f"[{datetime.now()}] 刷新战力数据 (limit={limit})...")

    # 获取数据（在线程池中执行，避免阻塞事件循环）
    stock_data = await asyncio.to_thread(get_stock_data_api, limit=limit)

    if not stock_data:
        print("  数据获取失败")
        return False

    print(f"  获取到 {len(stock_data)} 只股票数据")

    # 使用异步锁保护临界区
    async with _cp_lock:
        # 创建战力对象
        cp_engine.stocks.clear()
        stock_dicts = []
        stock_map = {}  # 用于后续映射
        for data in stock_data:
            try:
                stock = create_stock_from_raw(
                    code=data['code'],
                    name=data['name'],
                    price=data['price'],
                    pe=data['pe'],
                    roe=data['roe'],
                    net_profit_growth=data['net_profit_growth'],
                    revenue_growth=data['revenue_growth'],
                    change_pct=data['change_pct'],
                    pb=data.get('pb', 0),
                    gross_margin=data.get('gross_margin', 0),
                    revenue=data.get('revenue', 0),
                    cashflow=data.get('cashflow', 0),
                    debt_ratio=data.get('debt_ratio', 0),
                    volume=data.get('volume', 0),
                    amount=data.get('amount', 0),
                    dividend_yield=data.get('dividend_yield', 0),
                    market_cap=data.get('market_cap', 0),
                    high=data.get('high', 0),
                    low=data.get('low', 0),
                    data_quality=data.get('data_quality', 'low')
                )
                cp_engine.add_stock(stock)
                stock_dicts.append(stock.to_dict())
                stock_map[stock.code] = stock  # 通过code映射
            except Exception as e:
                print(f"  创建战力对象失败: {e}")

        # 计算战力
        cp_engine.calculate_all()

        # 更新stock_dicts中的战力分数（使用code映射避免索引问题）
        for stock_dict in stock_dicts:
            code = stock_dict.get('code')
            if code in stock_map:
                s = stock_map[code]
                stock_dict["total_cp"] = s.total_cp
                stock_dict["growth_score"] = s.growth_score
                stock_dict["value_score"] = s.value_score
                stock_dict["momentum_score"] = s.momentum_score

    # 保存历史记录（锁外执行，避免长时间占用锁）
    if save_hist:
        try:
            save_history(stock_dicts)
            print(f"  历史记录已保存(JSON)")
        except Exception as e:
            print(f"  历史记录保存失败: {e}")

        # 同时保存到SQLite（v17新增）
        try:
            db = get_db()
            db.batch_upsert_stocks(stock_dicts)
            db.record_cp_history(stock_dicts)
            print(f"  SQLite已更新")
        except Exception as e:
            print(f"  SQLite保存失败: {e}")

    last_update_time = datetime.now()
    print(f"  战力计算完成，更新时间: {last_update_time}")

    return True


@router.get("/api/health")
async def health_check():
    """健康检查"""
    global last_update_time
    needs_refresh = False
    if last_update_time:
        time_diff = (datetime.now() - last_update_time).total_seconds()
        needs_refresh = time_diff > 3600  # 超过1小时需要刷新

    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "data_fresh": not needs_refresh,
        "last_update": last_update_time.isoformat() if last_update_time else None,
        "stocks_count": len(cp_engine.stocks)
    }


@router.get("/api/cp/top")
async def get_cp_top(
    limit: int = Query(default=50, ge=1, le=200),
    force_refresh: bool = Query(default=False)
):
    """获取战力榜TOP N"""
    global last_update_time

    # 如果数据为空或强制刷新，则刷新数据
    if not cp_engine.stocks or force_refresh or last_update_time is None:
        success = await refresh_cp_data(limit=limit)
        if not success and not cp_engine.stocks:
            return {"error": "数据刷新失败，请稍后重试", "total": 0, "data": [], "updated_at": None}
    else:
        # 检查是否需要自动刷新（超过1小时）
        time_diff = (datetime.now() - last_update_time).total_seconds()
        if time_diff > 3600:
            await refresh_cp_data(limit=limit)

    # 如果仍然没有数据，返回错误
    if not cp_engine.stocks:
        return {"error": "暂无数据", "total": 0, "data": [], "updated_at": None}

    # 获取TOP N
    top_stocks = cp_engine.get_top(n=limit)

    data = []
    for s in top_stocks:
        data.append(_build_stock_cp_data(s))

    return CPListResponse(
        total=len(data),
        data=data,
        updated_at=last_update_time.isoformat() if last_update_time else None
    )


@router.get("/api/cp/bottom")
async def get_cp_bottom(limit: int = Query(default=10, ge=1, le=50)):
    """获取战力榜BOTTOM N（避雷区）"""
    global last_update_time

    if not cp_engine.stocks:
        success = await refresh_cp_data(limit=100)
        if not success and not cp_engine.stocks:
            return {"error": "数据刷新失败，请稍后重试", "total": 0, "data": [], "updated_at": None}

    bottom_stocks = cp_engine.get_bottom(n=limit)

    data = []
    for s in bottom_stocks:
        data.append(_build_stock_cp_data(s))

    return CPListResponse(
        total=len(data),
        data=data,
        updated_at=last_update_time.isoformat() if last_update_time else None
    )


@router.get("/api/stock/{code}")
async def get_single_stock(code: str):
    """获取单只股票战力数据"""
    global last_update_time

    # 标准化股票代码格式
    code = code.upper().strip()

    # 先检查缓存中是否有
    cached = cp_engine.get_by_code(code)
    if cached:
        return _build_stock_response(cached)

    # 实时获取
    stock_data = get_single_stock_data(code)
    if not stock_data:
        raise HTTPException(status_code=404, detail="股票未找到")

    # 创建战力对象
    stock = create_stock_from_raw(
        code=stock_data['code'],
        name=stock_data['name'],
        price=stock_data['price'],
        pe=stock_data['pe'],
        roe=stock_data['roe'],
        net_profit_growth=stock_data['net_profit_growth'],
        revenue_growth=stock_data['revenue_growth'],
        change_pct=stock_data['change_pct'],
        pb=stock_data.get('pb', 0),
        gross_margin=stock_data.get('gross_margin', 0),
        revenue=stock_data.get('revenue', 0),
        cashflow=stock_data.get('cashflow', 0),
        debt_ratio=stock_data.get('debt_ratio', 0),
        volume=stock_data.get('volume', 0),
        amount=stock_data.get('amount', 0),
        dividend_yield=stock_data.get('dividend_yield', 0),
        market_cap=stock_data.get('market_cap', 0),
        high=stock_data.get('high', 0),
        low=stock_data.get('low', 0),
        data_quality=stock_data.get('data_quality', 'low')
    )

    # 如果引擎中有数据，重新计算百分位
    if cp_engine.stocks:
        # 获取当前引擎中的数据范围
        df = cp_engine.to_dataframe()

        # 计算百分位（基于v14公式权重）
        # 成长30% + 价值25% + 质量20% + 动量15% + 风险调整10%
        growth_pct = (df['growth_score'] < stock.growth_score).sum() / len(df) * 100
        value_pct = (df['value_score'] < stock.value_score).sum() / len(df) * 100
        quality_pct = (df['quality_score'] < stock.quality_score).sum() / len(df) * 100
        momentum_pct = (df['momentum_score'] < stock.momentum_score).sum() / len(df) * 100

        stock.growth_score = growth_pct
        stock.value_score = value_pct
        stock.quality_score = quality_pct
        stock.momentum_score = momentum_pct

        # 基础战力
        base_cp = (
            growth_pct * 0.30 +
            value_pct * 0.25 +
            quality_pct * 0.20 +
            momentum_pct * 0.15
        )
        # 风险调整
        risk_factor = 1 - (stock.risk_score / 100) * 0.10
        stock.total_cp = max(0, base_cp * risk_factor)

    return _build_stock_response(stock)


@router.post("/api/refresh")
@limiter.limit("5/minute")
async def refresh_data(request: Request, limit: int = Query(default=100, ge=10, le=500)):
    """手动刷新数据"""
    success = await refresh_cp_data(limit=limit)
    if success:
        return {"status": "success", "message": f"成功刷新 {len(cp_engine.stocks)} 只股票数据"}
    else:
        raise HTTPException(status_code=500, detail="数据刷新失败")


@router.get("/api/cp/recommend")
async def get_recommended_stocks(category: str = Query(default="value", description="类型: value=价值型, growth=成长型, momentum=趋势型, quality=质量型, allround=综合型")):
    """获取推荐股票"""
    # 验证category参数
    valid_categories = ["value", "growth", "momentum", "quality", "allround"]
    if category not in valid_categories:
        raise HTTPException(status_code=400, detail=f"无效的category类型，可选值: {', '.join(valid_categories)}")

    if not cp_engine.stocks:
        success = await refresh_cp_data(limit=200)
        if not success and not cp_engine.stocks:
            return {"error": "数据刷新失败，请稍后重试", "category": category, "total": 0, "data": []}

    data = []
    for s in cp_engine.stocks:
        data.append(_build_stock_cp_data(s))

    # 按类型筛选（使用v14公式权重计算综合战力）
    def calc_v14_score(s):
        """计算v14综合战力"""
        return (
            (s.growth_score or 0) * 0.30 +
            (s.value_score or 0) * 0.25 +
            (s.quality_score or 0) * 0.20 +
            (s.momentum_score or 0) * 0.15
        )

    if category == "value":
        # 价值型：高ROE + 低PE + 正增长（附加质量分过滤）
        filtered = [s for s in data if s.roe > 10 and s.pe > 0 and s.pe < 30 and s.net_profit_growth > 0]
        filtered.sort(key=lambda x: x.value_score * 0.6 + (x.quality_score or 0) * 0.4, reverse=True)
    elif category == "growth":
        # 成长型：高增长 + 中等ROE（附加质量分过滤）
        filtered = [s for s in data if s.net_profit_growth > 20 and s.revenue_growth > 10 and s.roe > 0]
        filtered.sort(key=lambda x: x.growth_score * 0.6 + (x.quality_score or 0) * 0.4, reverse=True)
    elif category == "momentum":
        # 趋势型：高动量 + 正增长（附加质量分过滤）
        filtered = [s for s in data if s.change_pct > 2 and s.net_profit_growth > 0]
        filtered.sort(key=lambda x: x.momentum_score * 0.6 + (x.quality_score or 0) * 0.4, reverse=True)
    elif category == "quality":
        # 质量型：高现金流 + 高毛利 + 低负债
        filtered = [s for s in data if (s.cashflow or 0) > 0 and (s.gross_margin or 0) > 15]
        filtered.sort(key=lambda x: (x.quality_score or 0), reverse=True)
    elif category == "allround":
        # 综合型：使用v14公式计算综合战力
        filtered = [s for s in data if s.total_cp > 0]
        filtered.sort(key=lambda x: calc_v14_score(x), reverse=True)

    return {
        "category": category,
        "total": len(filtered),
        "data": filtered[:20]
    }


@router.get("/api/history/changes")
async def get_history_changes(days: int = Query(default=7, ge=1, le=30)):
    """获取战力变化显著的股票"""
    try:
        changes = get_cp_changes(days)
        return {
            "days": days,
            "total": len(changes),
            "data": changes[:20]  # 返回TOP20变化
        }
    except Exception as e:
        return {"error": str(e), "data": []}


@router.get("/api/history/{code}")
async def get_stock_history_api(code: str, days: int = Query(default=7, ge=1, le=30)):
    """获取指定股票的历史战力"""
    try:
        history = get_stock_history(code.upper(), days)
        return {
            "code": code.upper(),
            "total": len(history),
            "data": history
        }
    except Exception as e:
        return {"error": str(e), "data": []}


@router.get("/api/history/rankings/top")
async def get_historical_top_api(days: int = Query(default=30, ge=7, le=90)):
    """获取历史TOP10榜单"""
    try:
        rankings = get_historical_rankings(days=days, limit=10)
        return {
            "days": days,
            "total": len(rankings),
            "data": rankings
        }
    except Exception as e:
        return {"error": str(e), "data": []}


@router.get("/api/history/rankings/changes")
async def get_ranking_changes_api(days: int = Query(default=30, ge=7, le=90)):
    """获取榜单排名变化"""
    try:
        changes = get_ranking_changes(days=days)
        return {
            "days": days,
            "total": len(changes),
            "data": changes
        }
    except Exception as e:
        return {"error": str(e), "data": []}


@router.get("/api/stats/market")
async def get_market_stats():
    """获取市场整体统计"""
    try:
        if not cp_engine.stocks:
            success = await refresh_cp_data(limit=200)
            if not success and not cp_engine.stocks:
                return {"error": "数据刷新失败，请稍后重试", "total_stocks": 0}

        stocks = cp_engine.stocks
        if not stocks:
            return {"error": "暂无数据", "total_stocks": 0}

        # 基本统计
        cps = [s.total_cp for s in stocks]
        pes = [s.pe for s in stocks if s.pe > 0]
        changes = [s.change_pct for s in stocks]

        # 战力分布
        high_cp = len([c for c in cps if c >= 70])
        mid_cp = len([c for c in cps if 50 <= c < 70])
        low_cp = len([c for c in cps if c < 50])

        # 亏损股票
        loss_stocks = len([s for s in stocks if s.roe < 0])

        # 高PE股票（PE>50可能高估）
        high_pe = len([p for p in pes if p > 50])

        return {
            "total_stocks": len(stocks),
            "avg_cp": round(sum(cps) / len(cps), 1),
            "high_cp_count": high_cp,
            "mid_cp_count": mid_cp,
            "low_cp_count": low_cp,
            "loss_stocks": loss_stocks,
            "high_pe_stocks": high_pe,
            "avg_change": round(sum(changes) / len(changes), 2),
            "rising_stocks": len([c for c in changes if c > 0]),
            "falling_stocks": len([c for c in changes if c < 0]),
            "unchanged_stocks": len([c for c in changes if c == 0]),
            # 风险统计
            "avg_risk": round(sum(s.risk_score for s in stocks) / len(stocks), 1),
            "high_risk_count": len([s for s in stocks if s.risk_score >= 60]),
            "medium_risk_count": len([s for s in stocks if 30 <= s.risk_score < 60]),
            "low_risk_count": len([s for s in stocks if s.risk_score < 30]),
        }
    except Exception as e:
        print(f"Market stats error: {e}")
        return {"error": str(e), "total_stocks": 0}


@router.get("/api/stats/risk")
async def get_risk_stats():
    """获取市场风险统计"""
    try:
        if not cp_engine.stocks:
            success = await refresh_cp_data(limit=200)
            if not success and not cp_engine.stocks:
                return {"error": "数据刷新失败，请稍后重试", "total_stocks": 0}

        stocks = cp_engine.stocks
        if not stocks:
            return {"error": "暂无数据", "total_stocks": 0}

        # 风险分布
        high_risk = [s for s in stocks if s.risk_score >= 60]
        medium_risk = [s for s in stocks if 30 <= s.risk_score < 60]
        low_risk = [s for s in stocks if s.risk_score < 30]

        # 高风险股票（TOP10）
        high_risk_stocks = sorted(high_risk, key=lambda s: s.risk_score, reverse=True)[:10]

        return {
            "total_stocks": len(stocks),
            "high_risk_count": len(high_risk),
            "medium_risk_count": len(medium_risk),
            "low_risk_count": len(low_risk),
            "avg_risk_score": round(sum(s.risk_score for s in stocks) / len(stocks), 1),
            "high_risk_stocks": [{
                "code": s.code,
                "name": s.name,
                "risk_score": round(s.risk_score, 1),
                "risk_level": s.get_risk_level()
            } for s in high_risk_stocks]
        }
    except Exception as e:
        print(f"Risk stats error: {e}")
        return {"error": str(e), "total_stocks": 0}


@router.post("/api/stocks/batch")
async def get_batch_stocks(codes: list[str]):
    """批量获取多只股票的战力数据"""
    global last_update_time

    # 限制批量大小，防止性能问题
    MAX_BATCH_SIZE = 50
    if len(codes) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=400, detail=f"批量数量不能超过{MAX_BATCH_SIZE}只")

    # 去重处理，避免重复查询
    unique_codes = list(dict.fromkeys(c.upper().strip() for c in codes))

    # 确保引擎有数据
    if not cp_engine.stocks:
        success = await refresh_cp_data(limit=200)
        if not success and not cp_engine.stocks:
            return {"error": "数据刷新失败，请稍后重试", "data": []}

    result = []
    for code in unique_codes:
        try:
            # 先从引擎缓存中查找
            cached = cp_engine.get_by_code(code)
            if cached:
                result.append(_build_stock_response(cached))
            else:
                # 实时获取（仅当缓存中没有时）
                stock_data = get_single_stock_data(code)
                if stock_data:
                    stock = create_stock_from_raw(
                        code=stock_data['code'],
                        name=stock_data['name'],
                        price=stock_data['price'],
                        pe=stock_data['pe'],
                        roe=stock_data['roe'],
                        net_profit_growth=stock_data['net_profit_growth'],
                        revenue_growth=stock_data['revenue_growth'],
                        change_pct=stock_data['change_pct'],
                        pb=stock_data.get('pb', 0),
                        gross_margin=stock_data.get('gross_margin', 0),
                        revenue=stock_data.get('revenue', 0),
                        cashflow=stock_data.get('cashflow', 0),
                        debt_ratio=stock_data.get('debt_ratio', 0),
                        volume=stock_data.get('volume', 0),
                        amount=stock_data.get('amount', 0),
                        dividend_yield=stock_data.get('dividend_yield', 0),
                        market_cap=stock_data.get('market_cap', 0),
                        high=stock_data.get('high', 0),
                        low=stock_data.get('low', 0),
                        data_quality=stock_data.get('data_quality', 'low')
                    )

                    # 计算百分位（基于v14公式权重）
                    if cp_engine.stocks:
                        df = cp_engine.to_dataframe()
                        growth_pct = (df['growth_score'] < stock.growth_score).sum() / len(df) * 100
                        value_pct = (df['value_score'] < stock.value_score).sum() / len(df) * 100
                        quality_pct = (df['quality_score'] < stock.quality_score).sum() / len(df) * 100
                        momentum_pct = (df['momentum_score'] < stock.momentum_score).sum() / len(df) * 100
                        stock.growth_score = growth_pct
                        stock.value_score = value_pct
                        stock.quality_score = quality_pct
                        stock.momentum_score = momentum_pct
                        # 基础战力
                        base_cp = growth_pct * 0.30 + value_pct * 0.25 + quality_pct * 0.20 + momentum_pct * 0.15
                        # 风险调整
                        risk_factor = 1 - (stock.risk_score / 100) * 0.10
                        stock.total_cp = max(0, base_cp * risk_factor)

                    result.append(_build_stock_response(stock))
        except Exception as e:
            # 单只股票处理失败不影响其他股票
            print(f"批量处理股票失败 {code}: {e}")
            continue

    return {"total": len(result), "data": result}


# ============================================
# 换股决策 API v15（交易成本建模）
# ============================================

@router.get("/api/trade/should_swap")
async def should_swap(
    from_code: str = Query(..., description="当前股票代码"),
    to_code: str = Query(..., description="目标股票代码"),
    principal: float = Query(default=100000, ge=1000, description="本金（元）"),
    holding_days: int = Query(default=30, ge=1, le=365, description="计划持有天数")
):
    """
    判断是否应该换股 v15

    考虑因素：
    - 战力差：目标股票战力 - 当前股票战力
    - 持有天数：持有越久，换股成本越值得
    - 交易成本：佣金+印花税+过户费，最低5元/笔

    核心公式：
        换股净收益 = (B战力 - A战力) × 本金 × (持有天数/365) - 交易成本

    返回：
    - action: swap/hold/avoid
    - action_level: strong_buy/buy/hold/danger
    - action_color: green/yellow/gray/red
    - action_label: 操作建议文字
    """
    # 获取两只股票的战力
    stock_from = cp_engine.get_by_code(from_code)
    stock_to = cp_engine.get_by_code(to_code)

    if not stock_from:
        raise HTTPException(status_code=404, detail=f"未找到股票 {from_code}")
    if not stock_to:
        raise HTTPException(status_code=404, detail=f"未找到股票 {to_code}")

    # 计算换股决策
    decision = TradeDecision.should_swap(
        cp_a=stock_from.total_cp,
        cp_b=stock_to.total_cp,
        principal=principal,
        holding_days=holding_days
    )

    return decision


@router.get("/api/trade/cost")
async def get_trade_cost(
    principal: float = Query(default=100000, ge=1000, description="本金（元）")
):
    """
    计算换股交易成本 v15

    返回：
    - 各项费用明细
    - 总成本
    - 成本比率
    """
    cost_detail = TradeDecision.calculate_trade_cost(principal)

    return {
        "principal": cost_detail['principal'],
        "sell_costs": {
            "commission": cost_detail['sell_commission'],
            "stamp_tax": cost_detail['sell_stamp_tax'],
            "transfer_fee": cost_detail['sell_transfer_fee']
        },
        "buy_costs": {
            "commission": cost_detail['buy_commission'],
            "transfer_fee": cost_detail['buy_transfer_fee']
        },
        "total_cost": cost_detail['total_cost'],
        "cost_rate": round(cost_detail['cost_rate'] * 100, 3),
        "min_trade_value_hint": "建议单次交易金额 >= 5万元，使最低消费影响 < 0.02%"
    }


@router.get("/api/trade/cash_cost")
async def get_cash_opportunity_cost(
    principal: float = Query(default=100000, ge=1000, description="本金（元）"),
    days: int = Query(default=30, ge=1, le=365, description="持有天数")
):
    """
    计算持有现金的机会成本 v15

    核心思想：现金应视为"特殊股票"，其战力损失 = 持有现金的利息损失

    公式：机会成本 = 本金 × (年化2% / 365) × 天数

    返回：
    - 每日机会成本率
    - 持有期间总机会成本
    - 等效战力损失
    """
    daily_cost_rate = CashCP.get_daily_cost_rate()
    opportunity_cost = CashCP.get_opportunity_cost(principal, days)

    # 战力损失估算（假设1元 ≈ 0.01战力）
    equivalent_cp_loss = opportunity_cost * 0.01

    hints = []
    if principal < 50000:
        hints.append(f"⚠️ 资金 < 5万，最低消费影响显著，换股成本偏高")
    if days < 7:
        hints.append(f"⚠️ 持有 < 7天，换股几乎不可能回本")
    elif days < 30:
        hints.append(f"⚠️ 持有 < 30天，换股需要较大战力差才能盈利")
    else:
        hints.append(f"✅ 持有 {days} 天以上，换股成本相对可控")

    return {
        "principal": principal,
        "days": days,
        "daily_cost_rate": round(daily_cost_rate * 100, 4),
        "annual_cost_rate": 2.0,
        "opportunity_cost": round(opportunity_cost, 2),
        "equivalent_cp_loss": round(equivalent_cp_loss, 2),
        "hints": hints,
        "warning": "⚠️ 换股成本提醒：完整换股一次成本 ≈ 0.112%，建议持有 >= 30天再考虑换股"
    }


@router.get("/api/trade/cp_threshold")
async def get_cp_threshold(
    principal: float = Query(default=100000, ge=1000, description="本金（元）"),
    holding_days: int = Query(default=30, ge=1, le=365, description="持有天数")
):
    """
    计算换股所需的最小战力差阈值 v15

    返回：
    - 不亏钱的最小战力差
    - 盈利10%的战力差要求
    - 盈利20%的战力差要求
    """
    # 不亏钱
    threshold_no_loss = TradeDecision.get_cp_threshold(
        principal=principal,
        holding_days=holding_days,
        threshold=0
    )

    # 盈利10%
    threshold_10pct = TradeDecision.get_cp_threshold(
        principal=principal,
        holding_days=holding_days,
        threshold=principal * 0.10
    )

    # 盈利20%
    threshold_20pct = TradeDecision.get_cp_threshold(
        principal=principal,
        holding_days=holding_days,
        threshold=principal * 0.20
    )

    return {
        "principal": principal,
        "holding_days": holding_days,
        "thresholds": {
            "no_loss": round(threshold_no_loss, 2),
            "profit_10pct": round(threshold_10pct, 2),
            "profit_20pct": round(threshold_20pct, 2)
        },
        "explanation": {
            "no_loss": f"战力差需要 > {threshold_no_loss:.1f} 分才能不亏钱",
            "profit_10pct": f"战力差需要 > {threshold_10pct:.1f} 分才能盈利10%",
            "profit_20pct": f"战力差需要 > {threshold_20pct:.1f} 分才能盈利20%"
        },
        "trade_cost_rate": round(TOTAL_TRADE_COST_RATE * 100, 3),
        "daily_cp_value": f"战力差1分 ≈ 年化收益1% ≈ 每日收益 {principal * 0.01 / 365:.0f} 元"
    }


# ============================================
# 战力解释 API v16（因子透明化）
# ============================================

@router.get("/api/cp/explain/{code}")
async def explain_stock_cp(
    code: str,
    force_refresh: bool = Query(default=False, description="是否强制刷新数据")
):
    """
    获取股票战力分解说明 v16

    解释这只股票的战力值是如何计算的，展示了每个因子的贡献：
    - 成长分(30%): 净利润增长 + 营收增长
    - 价值分(25%): ROE + PE健康度 + PEG估值
    - 质量分(20%): 现金流 + 毛利率 + 资产负债率
    - 动量分(15%): 当日涨跌幅

    返回：
    - 各因子的原始分、加权贡献、详细说明
    - 风险评估详情
    - 综合总结
    """
    # 获取股票
    stock = cp_engine.get_by_code(code)

    if not stock:
        # 尝试强制刷新
        if force_refresh:
            success = await refresh_cp_data(limit=200)
            stock = cp_engine.get_by_code(code)

        if not stock:
            raise HTTPException(status_code=404, detail=f"未找到股票 {code}")

    # 返回战力分解
    return stock.get_cp_explanation()


# ============================================
# 持仓管理 API v16（CSV导入/导出）
# ============================================

# 简单内存存储（生产环境应该用数据库）
_holdings_storage: dict = {
    "default": []  # 默认持仓列表
}


@router.get("/api/holdings/export")
async def export_holdings():
    """
    导出持仓列表 v16

    返回当前持仓列表，可用于CSV格式导出

    返回：
    - holdings: 持仓列表
    - total_count: 持仓数量
    - export_time: 导出时间
    """
    holdings = _holdings_storage.get("default", [])

    return HoldingsExportResponse(
        holdings=[HoldingItem(**h) for h in holdings],
        total_count=len(holdings),
        export_time=datetime.now().isoformat()
    )


@router.post("/api/holdings/import")
async def import_holdings(request: HoldingsImportRequest):
    """
    导入持仓列表 v16

    支持批量导入持仓数据，替换现有的持仓列表

    请求格式：
    {
        "holdings": [
            {"code": "600519", "name": "贵州茅台", "quantity": 100, "cost_price": 1800.0},
            ...
        ]
    }

    返回：
    - imported_count: 导入数量
    - holdings: 导入后的完整持仓列表
    """
    global _holdings_storage

    # 验证数据
    validated_holdings = []
    errors = []

    for i, h in enumerate(request.holdings):
        try:
            # 验证股票代码格式
            code = str(h.code).strip()
            if not code:
                errors.append(f"第{i+1}行：股票代码不能为空")
                continue

            # 验证数量
            if h.quantity <= 0:
                errors.append(f"第{i+1}行({h.name})：持股数量必须大于0")
                continue

            # 验证成本价
            if h.cost_price < 0:
                errors.append(f"第{i+1}行({h.name})：成本价不能为负")
                continue

            validated_holdings.append({
                "code": code,
                "name": h.name or code,
                "quantity": h.quantity,
                "cost_price": h.cost_price
            })
        except Exception as e:
            errors.append(f"第{i+1}行：解析错误 - {str(e)}")

    # 保存
    _holdings_storage["default"] = validated_holdings

    return {
        "imported_count": len(validated_holdings),
        "total_count": len(validated_holdings),
        "errors": errors if errors else None,
        "message": f"成功导入 {len(validated_holdings)} 只持仓" if not errors else f"导入完成，但有 {len(errors)} 个错误"
    }


@router.get("/api/holdings")
async def get_holdings():
    """
    获取持仓列表 v16

    返回当前管理的持仓列表
    """
    holdings = _holdings_storage.get("default", [])
    return {
        "holdings": holdings,
        "total_count": len(holdings)
    }


@router.post("/api/holdings/add")
async def add_holding(holding: HoldingItem):
    """
    添加单只持仓 v16
    """
    global _holdings_storage

    holdings = _holdings_storage.get("default", [])

    # 检查是否已存在
    for h in holdings:
        if h["code"] == holding.code:
            raise HTTPException(status_code=400, detail=f"股票 {holding.code} 已存在，请使用更新接口")

    holdings.append({
        "code": holding.code,
        "name": holding.name or holding.code,
        "quantity": holding.quantity,
        "cost_price": holding.cost_price
    })

    return {
        "message": f"成功添加 {holding.name or holding.code}",
        "total_count": len(holdings)
    }


@router.delete("/api/holdings/{code}")
async def delete_holding(code: str):
    """
    删除持仓 v16
    """
    global _holdings_storage

    holdings = _holdings_storage.get("default", [])

    original_count = len(holdings)
    holdings = [h for h in holdings if h["code"] != code]

    if len(holdings) == original_count:
        raise HTTPException(status_code=404, detail=f"未找到股票 {code}")

    _holdings_storage["default"] = holdings

    return {
        "message": f"成功删除 {code}",
        "total_count": len(holdings)
    }


@router.get("/api/holdings/analysis")
async def analyze_holdings():
    """
    持仓战力分析 v16

    分析当前持仓的战力贡献、风险暴露、置换建议等
    """
    holdings = _holdings_storage.get("default", [])

    if not holdings:
        return {
            "message": "暂无持仓",
            "total_cp": 0,
            "holdings_analysis": []
        }

    analysis = []
    total_cp = 0
    total_value = 0

    for h in holdings:
        stock = cp_engine.get_by_code(h["code"])
        if stock:
            value = h["quantity"] * stock.price
            cp_contribution = stock.total_cp * h["quantity"]
            total_cp += cp_contribution
            total_value += value

            analysis.append({
                "code": h["code"],
                "name": h["name"],
                "quantity": h["quantity"],
                "cost_price": h["cost_price"],
                "current_price": stock.price,
                "cost_value": h["cost_price"] * h["quantity"],
                "current_value": value,
                "profit_pct": ((stock.price - h["cost_price"]) / h["cost_price"] * 100) if h["cost_price"] > 0 else 0,
                "cp": round(stock.total_cp, 1),
                "cp_contribution": round(cp_contribution, 1),
                "risk_level": stock.get_risk_level(),
                "risk_score": stock.risk_score
            })
        else:
            analysis.append({
                "code": h["code"],
                "name": h["name"],
                "quantity": h["quantity"],
                "cost_price": h["cost_price"],
                "current_price": None,
                "cost_value": h["cost_price"] * h["quantity"],
                "current_value": None,
                "profit_pct": None,
                "cp": None,
                "cp_contribution": None,
                "risk_level": "未知",
                "risk_score": None,
                "error": "股票数据未找到"
            })

    # 按战力排序
    analysis.sort(key=lambda x: x.get("cp") or 0, reverse=True)

    return {
        "total_cp": round(total_cp, 1),
        "total_value": round(total_value, 2),
        "holdings_count": len(holdings),
        "holdings_analysis": analysis,
        "avg_cp": round(total_cp / len(holdings), 1) if holdings else 0,
        "message": f"持仓 {len(holdings)} 只，总战力 {round(total_cp, 1)}，总市值 {round(total_value/10000, 2)}万元"
    }
