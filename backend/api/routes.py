"""
API路由 - TradeSnake API Routes
"""

from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime

from models.schemas import CPListResponse, SingleStockResponse, StockCPData
from core.cp_engine import CPEngine, create_stock_from_raw
from core.history import save_history, get_cp_changes, get_stock_history, get_historical_rankings, get_ranking_changes
from data.fetcher import get_stock_data_api, get_single_stock_data
from api.limits import limiter

router = APIRouter()

# 全局战力引擎实例
cp_engine = CPEngine()
last_update_time = None


def refresh_cp_data(limit: int = 100, save_hist: bool = True):
    """刷新战力数据"""
    global last_update_time

    print(f"[{datetime.now()}] 刷新战力数据 (limit={limit})...")

    # 获取数据
    stock_data = get_stock_data_api(limit=limit)

    if not stock_data:
        print("  数据获取失败")
        return False

    print(f"  获取到 {len(stock_data)} 只股票数据")

    # 创建战力对象
    cp_engine.stocks.clear()
    stock_dicts = []
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
        except Exception as e:
            print(f"  创建战力对象失败: {e}")

    # 计算战力
    cp_engine.calculate_all()

    # 保存历史记录
    if save_hist:
        try:
            # 更新stock_dicts中的战力分数
            for i, s in enumerate(cp_engine.stocks):
                stock_dicts[i]["total_cp"] = s.total_cp
                stock_dicts[i]["growth_score"] = s.growth_score
                stock_dicts[i]["value_score"] = s.value_score
                stock_dicts[i]["momentum_score"] = s.momentum_score
            save_history(stock_dicts)
            print(f"  历史记录已保存")
        except Exception as e:
            print(f"  历史记录保存失败: {e}")

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
        success = refresh_cp_data(limit=limit)
        if not success and not cp_engine.stocks:
            return {"error": "数据刷新失败，请稍后重试", "total": 0, "data": [], "updated_at": None}
    else:
        # 检查是否需要自动刷新（超过1小时）
        time_diff = (datetime.now() - last_update_time).total_seconds()
        if time_diff > 3600:
            refresh_cp_data(limit=limit)

    # 如果仍然没有数据，返回错误
    if not cp_engine.stocks:
        return {"error": "暂无数据", "total": 0, "data": [], "updated_at": None}

    # 获取TOP N
    top_stocks = cp_engine.get_top(n=limit)

    data = []
    for s in top_stocks:
        data.append(StockCPData(
            code=s.code,
            name=s.name,
            price=s.price,
            pe=s.pe,
            roe=s.roe,
            net_profit_growth=s.net_profit_growth,
            revenue_growth=s.revenue_growth,
            change_pct=s.change_pct,
            growth_score=round(s.growth_score, 2),
            value_score=round(s.value_score, 2),
            momentum_score=round(s.momentum_score, 2),
            quality_score=round(s.quality_score, 2),
            total_cp=round(s.total_cp, 2),
            risk_score=round(s.risk_score, 2),
            risk_level=s.get_risk_level(),
            peg=round(s.peg, 2),
            pb=s.pb,
            gross_margin=s.gross_margin,
            revenue=s.revenue,
            cashflow=s.cashflow,
            debt_ratio=s.debt_ratio,
            dividend_yield=s.dividend_yield,
            market_cap=s.market_cap,
            high=s.high,
            low=s.low,
            data_quality=s.data_quality
        ))

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
        success = refresh_cp_data(limit=100)
        if not success and not cp_engine.stocks:
            return {"error": "数据刷新失败，请稍后重试", "total": 0, "data": [], "updated_at": None}

    bottom_stocks = cp_engine.get_bottom(n=limit)

    data = []
    for s in bottom_stocks:
        data.append(StockCPData(
            code=s.code,
            name=s.name,
            price=s.price,
            pe=s.pe,
            roe=s.roe,
            net_profit_growth=s.net_profit_growth,
            revenue_growth=s.revenue_growth,
            change_pct=s.change_pct,
            growth_score=round(s.growth_score, 2),
            value_score=round(s.value_score, 2),
            momentum_score=round(s.momentum_score, 2),
            quality_score=round(s.quality_score, 2),
            total_cp=round(s.total_cp, 2),
            risk_score=round(s.risk_score, 2),
            risk_level=s.get_risk_level(),
            peg=round(s.peg, 2),
            pb=s.pb,
            gross_margin=s.gross_margin,
            revenue=s.revenue,
            cashflow=s.cashflow,
            debt_ratio=s.debt_ratio,
            dividend_yield=s.dividend_yield,
            market_cap=s.market_cap,
            high=s.high,
            low=s.low,
            data_quality=s.data_quality
        ))

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
        return SingleStockResponse(
            code=cached.code,
            name=cached.name,
            price=cached.price,
            pe=cached.pe,
            roe=cached.roe,
            net_profit_growth=cached.net_profit_growth,
            revenue_growth=cached.revenue_growth,
            change_pct=cached.change_pct,
            growth_score=round(cached.growth_score, 2),
            value_score=round(cached.value_score, 2),
            momentum_score=round(cached.momentum_score, 2),
            quality_score=round(cached.quality_score, 2),
            total_cp=round(cached.total_cp, 2),
            risk_score=round(cached.risk_score, 2),
            risk_level=cached.get_risk_level(),
            peg=round(cached.peg, 2),
            pb=cached.pb,
            gross_margin=cached.gross_margin,
            revenue=cached.revenue,
            cashflow=cached.cashflow,
            debt_ratio=cached.debt_ratio,
            dividend_yield=cached.dividend_yield,
            market_cap=cached.market_cap,
            high=cached.high,
            low=cached.low,
            data_quality=cached.data_quality
        )

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


@router.post("/api/refresh")
@limiter.limit("5/minute")
async def refresh_data(request: Request, limit: int = Query(default=100, ge=10, le=500)):
    """手动刷新数据"""
    success = refresh_cp_data(limit=limit)
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
        success = refresh_cp_data(limit=200)
        if not success and not cp_engine.stocks:
            return {"error": "数据刷新失败，请稍后重试", "category": category, "total": 0, "data": []}

    data = []
    for s in cp_engine.stocks:
        data.append(StockCPData(
            code=s.code,
            name=s.name,
            price=s.price,
            pe=s.pe,
            roe=s.roe,
            net_profit_growth=s.net_profit_growth,
            revenue_growth=s.revenue_growth,
            change_pct=s.change_pct,
            growth_score=round(s.growth_score, 2),
            value_score=round(s.value_score, 2),
            momentum_score=round(s.momentum_score, 2),
            quality_score=round(s.quality_score, 2),
            total_cp=round(s.total_cp, 2),
            risk_score=round(s.risk_score, 2),
            risk_level=s.get_risk_level(),
            peg=round(s.peg, 2),
            pb=s.pb,
            gross_margin=s.gross_margin,
            revenue=s.revenue,
            cashflow=s.cashflow,
            debt_ratio=s.debt_ratio,
            dividend_yield=s.dividend_yield,
            market_cap=s.market_cap,
            high=s.high,
            low=s.low,
            data_quality=s.data_quality
        ))

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
            success = refresh_cp_data(limit=200)
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
            success = refresh_cp_data(limit=200)
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
        success = refresh_cp_data(limit=200)
        if not success and not cp_engine.stocks:
            return {"error": "数据刷新失败，请稍后重试", "data": []}

    result = []
    for code in unique_codes:
        # 先从引擎缓存中查找
        cached = cp_engine.get_by_code(code)
        if cached:
            result.append(SingleStockResponse(
                code=cached.code,
                name=cached.name,
                price=cached.price,
                pe=cached.pe,
                roe=cached.roe,
                net_profit_growth=cached.net_profit_growth,
                revenue_growth=cached.revenue_growth,
                change_pct=cached.change_pct,
                growth_score=round(cached.growth_score, 2),
                value_score=round(cached.value_score, 2),
                momentum_score=round(cached.momentum_score, 2),
                quality_score=round(cached.quality_score, 2),
                total_cp=round(cached.total_cp, 2),
                risk_score=round(cached.risk_score, 2),
                risk_level=cached.get_risk_level(),
                peg=round(cached.peg, 2),
                pb=cached.pb,
                gross_margin=cached.gross_margin,
                revenue=cached.revenue,
                cashflow=cached.cashflow,
                debt_ratio=cached.debt_ratio,
                dividend_yield=cached.dividend_yield,
                market_cap=cached.market_cap,
                high=cached.high,
                low=cached.low,
                data_quality=cached.data_quality
            ))
            continue

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

            result.append(SingleStockResponse(
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
            ))

    return {"total": len(result), "data": result}
