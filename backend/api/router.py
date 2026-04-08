"""
API路由 - TradeSnake API Routes (Refactored)
"""

import asyncio
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime

from models.schemas import (
    CPListResponse, SingleStockResponse, StockCPData,
    SwapSuggestion, RecommendResponse, CPExplanationResponse,
    AccountResponse, HoldingDetail, PortfolioResponse,
    TradeRequest, TradeResponse, TradeHistoryResponse,
    UserProfile, UserProfileResponse, HealthResponse
)

# 使用新的模块导入
from backend.engine.cp_engine import CPEngine, StockCP, create_stock_from_raw, CashCP, TradeDecision
from backend.engine.history import (
    save_history, get_cp_changes, get_stock_history,
    get_historical_rankings, get_ranking_changes,
    get_momentum_3d, get_momentum_5d
)
from backend.engine.risk_analyzer import RiskAnalyzer
from backend.simulator.database import get_db
from backend.simulator.account import Account
from backend.simulator.portfolio import Portfolio
from backend.simulator.trader import Trader
from backend.recommender.recommend_engine import RecommendEngine
from backtester.backtest import BacktestEngine
from data_manager.fetcher import get_stock_data_api, get_single_stock_data
from data_manager.cache import get_cache_manager

router = APIRouter()

# 全局实例
cp_engine = CPEngine()
recommend_engine = RecommendEngine()
_db = get_db()
_account = Account()
_portfolio = Portfolio()
_trader = Trader()
_backtest_engine = BacktestEngine()

last_update_time = None
_cp_lock = asyncio.Lock()


def _build_stock_response(stock: StockCP) -> SingleStockResponse:
    """构建单股票响应数据"""
    return SingleStockResponse(
        code=stock.code,
        name=stock.name,
        price=stock.price,
        pe=stock.pe,
        roe=stock.roe,
        net_profit_growth=stock.net_profit_growth,
        revenue_growth=stock.revenue_growth,
        change_pct=stock.change_pct,
        growth_score=round(stock.growth_score, 1),
        value_score=round(stock.value_score, 1),
        quality_score=round(stock.quality_score, 1),
        momentum_score=round(stock.momentum_score, 1),
        total_cp=round(stock.total_cp, 1),
        risk_score=stock.risk_score,
        risk_level=stock.get_risk_level(),
        peg=round(stock.peg, 2),
        pb=stock.pb,
        gross_margin=stock.gross_margin,
        revenue=stock.revenue,
        cashflow=stock.cashflow,
        debt_ratio=stock.debt_ratio,
        dividend_yield=stock.dividend_yield,
        market_cap=stock.market_cap,
        data_quality=stock.data_quality,
        board_type=stock.board_type,
        board_name=stock.board_name,
        can_trade_newbie=stock.can_trade_newbie,
        trade_requirement=stock.trade_requirement,
        current_ratio=stock.current_ratio,
        interest_coverage=stock.interest_coverage,
        deducted_net_profit=stock.deducted_net_profit
    )


# ==================== 战力榜 ====================

@router.get("/api/cp/top", response_model=CPListResponse)
async def get_cp_top(limit: int = Query(50, ge=1, le=200)):
    """获取战力榜TOP N"""
    global last_update_time
    if not cp_engine.stocks:
        return CPListResponse(data=[], total=0, updated_at="")
    stocks = cp_engine.get_top(limit)
    return CPListResponse(
        data=[_build_stock_response(s) for s in stocks],
        total=len(cp_engine.stocks),
        updated_at=last_update_time or datetime.now().isoformat()
    )


@router.get("/api/cp/stock/{code}", response_model=SingleStockResponse)
async def get_cp_stock(code: str):
    """获取单只股票战力"""
    stock = cp_engine.get_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票{code}不存在")
    return _build_stock_response(stock)


@router.get("/api/cp/explain/{code}", response_model=CPExplanationResponse)
async def get_cp_explain(code: str):
    """获取战力分解说明"""
    stock = cp_engine.get_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票{code}不存在")
    return CPExplanationResponse(**stock.get_cp_explanation())


# ==================== 推荐 ====================

@router.get("/api/cp/recommend", response_model=RecommendResponse)
async def get_recommend(
    category: str = Query("value", pattern="^(value|growth|momentum|quality)$"),
    risk_preference: str = Query("balanced", pattern="^(conservative|balanced|aggressive)$"),
    exclude_holdings: bool = True
):
    """获取推荐股票"""
    holdings = _portfolio.get_holdings() if exclude_holdings else []
    holding_codes = [h.get('code') for h in holdings]

    # 直接使用 cp_engine.stocks
    stocks = cp_engine.stocks
    if exclude_holdings and holding_codes:
        stocks = [s for s in stocks if s.code not in holding_codes]

    # 排序
    if category == 'value':
        sorted_stocks = sorted(stocks, key=lambda x: x.value_score, reverse=True)
    elif category == 'growth':
        sorted_stocks = sorted(stocks, key=lambda x: x.growth_score, reverse=True)
    elif category == 'momentum':
        sorted_stocks = sorted(stocks, key=lambda x: x.momentum_score, reverse=True)
    elif category == 'quality':
        sorted_stocks = sorted(stocks, key=lambda x: x.quality_score, reverse=True)
    else:
        sorted_stocks = sorted(stocks, key=lambda x: x.total_cp, reverse=True)

    # 风险过滤
    if risk_preference == 'conservative':
        sorted_stocks = [s for s in sorted_stocks if s.risk_score < 30]
    elif risk_preference == 'balanced':
        sorted_stocks = [s for s in sorted_stocks if s.risk_score < 50]

    recs = [_build_stock_response(s).model_dump() for s in sorted_stocks[:20]]

    return RecommendResponse(data=recs, total=len(recs), category=category)


@router.get("/api/cp/swap", response_model=List[SwapSuggestion])
async def get_swap_suggestions(principal: float = Query(100000, gt=0)):
    """获取换股建议"""
    holdings = _portfolio.get_holdings()
    all_stocks = cp_engine.stocks

    # 为持仓添加 CP 数据
    code_to_cp = {s.code: s.total_cp for s in all_stocks}
    enriched_holdings = []
    for h in holdings:
        cp = code_to_cp.get(h.get('code'), 0)
        if cp > 0:
            enriched_holdings.append({
                **h,
                'cp': cp
            })

    suggestions = recommend_engine.get_swap_suggestions(
        holdings=enriched_holdings,
        all_stocks=all_stocks,
        principal=principal
    )

    # 映射字段以匹配 SwapSuggestion schema
    mapped_suggestions = []
    for s in suggestions:
        mapped_suggestions.append({
            'from_code': s.get('from_code', ''),
            'from_name': s.get('from_name', ''),
            'from_cp': s.get('from_cp', 0),
            'to_code': s.get('to_code', ''),
            'to_name': s.get('to_name', ''),
            'to_cp': s.get('to_cp', 0),
            'cp_improvement': s.get('cp_improvement', 0),
            'net_benefit': s.get('net_profit', 0),  # 字段映射
            'trade_cost': s.get('trade_cost', 0),
            'holding_days_equivalent': s.get('breakeven_days', 0),  # 字段映射
            'action_level': s.get('action_level', ''),
            'action_label': s.get('action_label', ''),
        })

    return mapped_suggestions


# ==================== 历史 ====================

@router.get("/api/history/changes")
async def get_history_changes(days: int = Query(7, ge=1, le=30)):
    """获取战力变化"""
    return get_cp_changes(days)


@router.get("/api/history/{code}")
async def get_stock_history_endpoint(code: str, days: int = Query(7, ge=1, le=30)):
    """获取股票历史战力"""
    return get_stock_history(code, days)


@router.get("/api/history/rankings")
async def get_historical_rankings_endpoint(days: int = Query(30, ge=1, le=90), limit: int = Query(10, ge=1, le=50)):
    """获取历史榜单"""
    return get_historical_rankings(days, limit)


# ==================== 账户 ====================

@router.get("/api/account", response_model=AccountResponse)
async def get_account():
    """获取账户信息"""
    return AccountResponse(**_account.get_summary())


@router.get("/api/portfolio", response_model=PortfolioResponse)
async def get_portfolio():
    """获取持仓明细"""
    holdings = _portfolio.get_holdings()
    holding_details = []
    total_market_value = 0.0
    total_profit = 0.0

    for h in holdings:
        position = _trader.get_position(h.get('code'))
        if position:
            # 映射字段名以匹配 HoldingDetail schema
            mapped = {
                'code': position.get('code', ''),
                'name': position.get('name', ''),
                'quantity': position.get('quantity', 0),
                'cost_price': position.get('avg_cost_price', 0),
                'current_price': position.get('current_price', 0),
                'market_value': position.get('value_total', 0),
                'profit': position.get('profit', 0),
                'profit_rate': position.get('profit_rate', 0),
                'bought_at': position.get('latest_bought_at', ''),
                'can_sell': position.get('quantity', 0),  # 简化处理
                'on_cooldown': False,
                'cooldown_days_remaining': 0,
            }
            detail = HoldingDetail(**mapped)
            holding_details.append(detail)
            total_market_value += detail.market_value
            total_profit += detail.profit

    return PortfolioResponse(
        holdings=holding_details,
        total_market_value=total_market_value,
        total_profit=total_profit,
        cash=_account.cash,
        total_assets=_account.cash + total_market_value
    )


@router.post("/api/trade/buy", response_model=TradeResponse)
async def trade_buy(req: TradeRequest):
    """买入股票"""
    result = _trader.buy(req.code, req.quantity)
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error', '买入失败'))
    # 映射字段以匹配 TradeResponse schema
    return TradeResponse(
        success=result.get('success', True),
        action=result.get('action', 'buy'),
        code=result.get('code', ''),
        name=result.get('name', ''),
        quantity=result.get('quantity', 0),
        price=result.get('price', 0),
        total_amount=result.get('total_cost', 0),
        cost_detail={
            'commission': result.get('commission', 0),
            'stamp_tax': 0,
            'transfer_fee': result.get('transfer_fee', 0),
            'total_cost': result.get('total_cost', 0),
        },
        cash_after=result.get('remaining_cash', 0),
        message=''
    )


@router.post("/api/trade/sell", response_model=TradeResponse)
async def trade_sell(req: TradeRequest):
    """卖出股票"""
    result = _trader.sell(req.code, req.quantity)
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error', '卖出失败'))
    # 映射字段以匹配 TradeResponse schema
    return TradeResponse(
        success=result.get('success', True),
        action=result.get('action', 'sell'),
        code=result.get('code', ''),
        name=result.get('name', ''),
        quantity=result.get('quantity', 0),
        price=result.get('price', 0),
        total_amount=result.get('total_amount', 0),
        cost_detail={
            'commission': result.get('commission', 0),
            'stamp_tax': result.get('stamp_tax', 0),
            'transfer_fee': result.get('transfer_fee', 0),
            'total_cost': result.get('total_cost', 0),
        },
        cash_after=result.get('remaining_cash', 0),
        message=''
    )


@router.get("/api/trades", response_model=TradeHistoryResponse)
async def get_trades(limit: int = Query(50, ge=1, le=200)):
    """获取交易历史"""
    trades = _trader.get_trade_history(limit)
    return TradeHistoryResponse(trades=trades, total_count=len(trades))


# ==================== 用户配置 ====================

@router.get("/api/user/profile", response_model=UserProfileResponse)
async def get_user_profile():
    """获取用户配置"""
    profile = _db.get_user_profile()
    return UserProfileResponse(**profile)


@router.put("/api/user/profile")
async def update_user_profile(profile: UserProfile):
    """更新用户配置"""
    _db.save_user_profile(profile.dict())
    return {"success": True}


# ==================== 回测 ====================

@router.get("/api/backtest/simple")
async def backtest_simple(
    start_date: str,
    end_date: str,
    holding_days: int = Query(30, ge=1, le=365),
    top_n: int = Query(10, ge=1, le=50)
):
    """简单回测"""
    return _backtest_engine.calculate_simple_backtest(start_date, end_date, holding_days, top_n)


@router.get("/api/backtest/compare")
async def backtest_compare(
    start_date: str,
    end_date: str,
    holding_days: int = Query(30, ge=1, le=365)
):
    """对比回测"""
    return _backtest_engine.calculate_compare_backtest(start_date, end_date, holding_days)


@router.get("/api/backtest/benchmark")
async def backtest_benchmark(
    start_date: str,
    end_date: str,
    benchmark: str = Query("hs300", pattern="^(hs300|zz500|equal_weight)$")
):
    """基准回测"""
    return _backtest_engine.calculate_benchmark_backtest(start_date, end_date, benchmark)


# ==================== 风险 ====================

@router.get("/api/risk/report")
async def get_risk_report():
    """获取风险报告"""
    holdings = _portfolio.get_holdings()
    market_cp = RiskAnalyzer.get_market_cp(cp_engine.stocks)
    capital = _account.cash

    return RiskAnalyzer.generate_risk_report(
        db=_db,
        holdings=holdings,
        all_stocks=cp_engine.stocks,
        market_cp=market_cp,
        capital=capital
    )


@router.get("/api/risk/break-even/{code}")
async def get_break_even(code: str):
    """计算解套所需涨幅"""
    position = _trader.get_position(code)
    if not position:
        raise HTTPException(status_code=404, detail=f"未持有{code}")

    cost_price = position.get('cost_price', 0)
    current_price = position.get('current_price', 0)

    return RiskAnalyzer.calculate_break_even(cost_price, current_price)


# ==================== 健康检查 ====================

@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    cache_stats = get_cache_manager().get_cache_stats()
    now = datetime.now().isoformat()
    return HealthResponse(
        status="ok",
        timestamp=now,
        data_fresh=last_update_time is not None,
        last_update=last_update_time or now,
        stocks_count=len(cp_engine.stocks)
    )


# ==================== 数据刷新 ====================

@router.post("/api/refresh")
async def refresh_data(limit: int = Query(200, ge=1, le=500)):
    """刷新数据"""
    global last_update_time

    async with _cp_lock:
        try:
            stocks_data = get_stock_data_api(limit=limit)
            cp_engine.stocks = []

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
                    volume=data.get('volume', 0),
                    amount=data.get('amount', 0),
                    dividend_yield=data.get('dividend_yield', 0),
                    market_cap=data.get('market_cap', 0),
                    data_quality=data.get('data_quality', 'low')
                )
                cp_engine.add_stock(stock)

            cp_engine.calculate_all()

            # 保存历史
            stock_dicts = [s.to_dict() for s in cp_engine.stocks]
            save_history(stock_dicts)

            # 更新数据库
            _db.batch_upsert_stocks(stock_dicts)

            # 记录持仓快照 v19.7
            stocks_data = {s['code']: {'price': s['price'], 'total_cp': s['total_cp']} for s in stock_dicts}
            snapshot_count = _db.record_daily_holding_snapshots(date=datetime.now().strftime("%Y-%m-%d"), stocks_data=stocks_data)

            last_update_time = datetime.now().isoformat()

            return {
                "success": True,
                "stocks_updated": len(cp_engine.stocks),
                "snapshots_recorded": snapshot_count,
                "updated_at": last_update_time
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"刷新失败: {str(e)}")


# ==================== 持仓快照 v19.7 ====================

@router.post("/api/snapshot/record")
async def record_holding_snapshot(date: str = Query(None, description="快照日期，默认今日")):
    """记录每日持仓快照（收盘后调用）

    用于回测验证，记录持仓的收盘市值和盈亏
    """
    try:
        from backtester.verification import BacktestVerifier

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # 构建股票数据映射
        stocks_data = {}
        for stock in cp_engine.stocks:
            stocks_data[stock.code] = {
                'price': stock.price,
                'total_cp': stock.total_cp
            }

        # 记录快照
        count = _db.record_daily_holding_snapshots(date=date, stocks_data=stocks_data)

        return {
            "success": True,
            "date": date,
            "snapshots_recorded": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"记录快照失败: {str(e)}")


@router.get("/api/verify/report")
async def get_verification_report(days: int = Query(30, ge=7, le=365, description="验证最近N天")):
    """获取回测验证报告 v19.7

    包含：
    - 换股效果验证（胜率、平均收益）
    - 战力预测准确性（高战力组是否跑赢市场）
    """
    try:
        from backtester.verification import BacktestVerifier

        verifier = BacktestVerifier(_db)
        report = verifier.get_verification_report(days=days)

        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取验证报告失败: {str(e)}")


@router.get("/api/verify/swap")
async def verify_swap_effectiveness(
    start_date: str = Query(None, description="开始日期"),
    end_date: str = Query(None, description="结束日期"),
    min_hold_days: int = Query(1, ge=1, le=30, description="最小持有天数")
):
    """验证换股效果 v19.7

    分析所有卖出交易，计算持有到现在是否盈利
    """
    try:
        from backtester.verification import BacktestVerifier

        verifier = BacktestVerifier(_db)
        verifications = verifier.verify_swap_effectiveness(
            start_date=start_date,
            end_date=end_date,
            min_hold_days=min_hold_days
        )

        summary = verifier.get_swap_summary(verifications)

        return {
            "verifications": [
                {
                    "code": v.code,
                    "name": v.name,
                    "swap_date": v.swap_date,
                    "hold_days": v.hold_days,
                    "price_change_pct": v.price_change_pct,
                    "cp_change": v.cp_change,
                    "is_profitable": v.is_profitable,
                    "profit": v.profit
                }
                for v in verifications
            ],
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证换股失败: {str(e)}")


@router.get("/api/verify/cp_accuracy")
async def verify_cp_prediction_accuracy(
    date: str = Query(None, description="基准日期"),
    holding_days: int = Query(5, ge=1, le=30, description="持有天数"),
    high_cp_threshold: float = Query(70, ge=50, le=100, description="高战力阈值"),
    low_cp_threshold: float = Query(50, ge=30, le=60, description="低战力阈值")
):
    """验证战力预测准确性 v19.7

    比较战力高的股票组和战力低的股票组在未来N天的表现差异
    """
    try:
        from backtester.verification import BacktestVerifier

        verifier = BacktestVerifier(_db)
        result = verifier.verify_cp_prediction_accuracy(
            date=date,
            holding_days=holding_days,
            high_cp_threshold=high_cp_threshold,
            low_cp_threshold=low_cp_threshold
        )

        return {
            "period": result.period,
            "total_stocks": result.total_stocks,
            "high_cp_group_avg_profit": result.avg_profit_if_hold_high_cp,
            "low_cp_group_avg_profit": result.avg_profit_if_hold_low_cp,
            "high_cp_beats_market_rate": result.accuracy,
            "high_cp_vs_market": result.high_cp_above_avg,
            "low_cp_vs_market": result.low_cp_below_avg
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证战力预测失败: {str(e)}")
