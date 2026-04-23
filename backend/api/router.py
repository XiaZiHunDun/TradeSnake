"""
API路由 - TradeSnake API Routes (Refactored)
"""

import asyncio
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime

from backend.models.schemas import (
    CPListResponse, SingleStockResponse, StockCPData,
    SwapSuggestion, RecommendResponse, CPExplanationResponse,
    AccountResponse, HoldingDetail, PortfolioResponse,
    TradeRequest, TradeResponse, TradeHistoryResponse,
    UserProfile, UserProfileResponse, HealthResponse,
    MarketStatsResponse,
    GainPredictionResponse, GainPredictionItem,
    ProbabilityPredictionResponse, ProbabilityPredictionItem,
    FullBacktestResponse, BacktestTradeResponse, EquityPointResponse,
)

# 线程池用于CPU密集型任务（如预测计算）
from concurrent.futures import ThreadPoolExecutor
_executor = ThreadPoolExecutor(max_workers=2)

# 使用新的模块导入
from backend.engine.cp_engine import CPEngine, StockCP, create_stock_from_raw, CashCP, TradeDecision
from backend.engine.cp_engine.history import (
    save_history, get_cp_changes, get_stock_history,
    get_historical_rankings, get_ranking_changes,
    get_momentum_3d, get_momentum_5d
)
from backend.engine.cp_engine.risk_analyzer import RiskAnalyzer
from backend.simulator.database import get_db
from backend.simulator.account import Account
from backend.simulator.portfolio import Portfolio
from backend.simulator.trader import Trader
from backend.recommender.recommend_engine import RecommendEngine
from backend.backtester.backtest import BacktestEngine
from backend.data_manager.fetcher import get_stock_data_api, get_single_stock_data
from backend.data_manager.cache import get_cache_manager
def get_stock_selector():
    """延迟导入避免循环依赖"""
    from backend.api.main import get_stock_selector as _get
    return _get()

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


@router.get("/api/cp/bottom", response_model=CPListResponse)
async def get_cp_bottom(limit: int = Query(10, ge=1, le=50)):
    """获取避雷榜（战力最弱）BOTTOM N"""
    global last_update_time
    if not cp_engine.stocks:
        return CPListResponse(data=[], total=0, updated_at="")
    stocks = cp_engine.get_bottom(limit)
    return CPListResponse(
        data=[_build_stock_response(s) for s in stocks],
        total=len(cp_engine.stocks),
        updated_at=last_update_time or datetime.now().isoformat()
    )


@router.get("/api/stats/market", response_model=MarketStatsResponse)
async def get_market_stats():
    """获取市场统计信息"""
    if not cp_engine.stocks:
        return MarketStatsResponse(
            total_stocks=0, avg_cp=0, high_cp_count=0, mid_cp_count=0,
            low_cp_count=0, avg_change=0, rising_stocks=0, falling_stocks=0,
            unchanged_stocks=0
        )
    stocks = cp_engine.stocks  # list of StockCP
    total = len(stocks)
    avg_cp = sum(s.total_cp for s in stocks) / total
    high_cp = sum(1 for s in stocks if s.total_cp >= 70)
    mid_cp = sum(1 for s in stocks if 40 <= s.total_cp < 70)
    low_cp = sum(1 for s in stocks if s.total_cp < 40)
    changes = [s.change_pct for s in stocks if hasattr(s, 'change_pct') and s.change_pct != 0]
    avg_change = sum(changes) / len(changes) if changes else 0
    rising = sum(1 for s in stocks if hasattr(s, 'change_pct') and s.change_pct > 0)
    falling = sum(1 for s in stocks if hasattr(s, 'change_pct') and s.change_pct < 0)
    unchanged = total - rising - falling
    return MarketStatsResponse(
        total_stocks=total,
        avg_cp=round(avg_cp, 1),
        high_cp_count=high_cp,
        mid_cp_count=mid_cp,
        low_cp_count=low_cp,
        avg_change=round(avg_change, 2),
        rising_stocks=rising,
        falling_stocks=falling,
        unchanged_stocks=unchanged,
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
    exclude_holdings: bool = True,
    fusion: bool = Query(False, description="是否使用战力+预测融合推荐 (v19.9.5)")
):
    """获取推荐股票

    Args:
        fusion: True时使用战力×涨幅预测×上涨概率融合推荐，False时使用纯战力排序
    """
    holdings = _portfolio.get_holdings() if exclude_holdings else []
    holding_codes = [h.get('code') for h in holdings]

    # 直接使用 cp_engine.stocks
    stocks = cp_engine.stocks
    if exclude_holdings and holding_codes:
        stocks = [s for s in stocks if s.code not in holding_codes]

    if fusion:
        # v19.9.5: 使用预测融合推荐
        principal = 100000  # 默认本金10万
        fusion_signals = recommend_engine.get_buy_signals(
            stocks=stocks,
            principal=principal,
            risk_preference=risk_preference,
            limit=20,
            use_fusion=True
        )

        # 将融合结果转换为 StockCPData 格式
        recs = []
        for sig in fusion_signals:
            # 获取原始 stock 对象
            stock_obj = next((s for s in stocks if s.code == sig['code']), None)
            if stock_obj:
                resp = _build_stock_response(stock_obj)
                resp_dict = resp.model_dump()
                # 添加融合字段
                resp_dict['kelly_position'] = sig.get('kelly_position', 0)
                resp_dict['predicted_gain_5d'] = sig.get('predicted_gain_5d', 0)
                resp_dict['up_probability_5d'] = sig.get('up_probability_5d', 0)
                resp_dict['prediction_confidence'] = sig.get('prediction_confidence', 0)
                resp_dict['fused_score'] = sig.get('fused_score', 0)
                recs.append(resp_dict)
            # stock_obj 为 None 时跳过（不应该发生）
    else:
        # 原有逻辑：按单维度排序
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

    return RecommendResponse(data=recs, total=len(recs), category=category,
                              risk_preference=risk_preference)


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
    """获取账户信息（使用本地SQLite价格，快速响应）"""
    from backend.simulator.database import get_db

    db = get_db()
    acct = db.get_account()
    cash = acct.get('cash', 0)

    # 使用SQLite stocks表的价格计算市值（避免网络请求）
    holdings = db.get_holdings()
    total_market_value = 0.0
    for h in holdings:
        code = h.get('code', '')
        qty = h.get('total_quantity', 0)
        # holdings用sh/sz前缀，stocks表不用
        lookup_code = code.replace('sh', '').replace('sz', '')
        stock = db.get_stock(lookup_code)
        if stock and stock.get('price', 0) > 0:
            total_market_value += stock.get('price', 0) * qty

    total_assets = cash + total_market_value
    initial_cash = acct.get('initial_cash', 20000)
    total_profit = total_assets - initial_cash
    profit_rate = (total_profit / initial_cash * 100) if initial_cash > 0 else 0

    return AccountResponse(
        cash=round(cash, 2),
        initial_cash=round(initial_cash, 2),
        total_market_value=round(total_market_value, 2),
        total_assets=round(total_assets, 2),
        total_profit=round(total_profit, 2),
        profit_rate=round(profit_rate, 2)
    )


@router.get("/api/portfolio", response_model=PortfolioResponse)
async def get_portfolio():
    """获取持仓明细（使用本地SQLite价格，快速响应）"""
    from backend.simulator.database import get_db

    db = get_db()
    holdings = db.get_holdings()
    holding_details = []
    total_market_value = 0.0
    total_profit = 0.0

    for h in holdings:
        code = h.get('code', '')
        name = h.get('name', '')
        qty = h.get('total_quantity', 0)
        cost_price = h.get('avg_cost_price', 0)

        # 使用SQLite stocks表的价格（避免网络请求）
        lookup_code = code.replace('sh', '').replace('sz', '')
        stock = db.get_stock(lookup_code)
        current_price = stock.get('price', 0) if stock else 0

        market_value = current_price * qty
        cost_total = cost_price * qty
        profit = market_value - cost_total
        profit_rate = (profit / cost_total * 100) if cost_total > 0 else 0

        detail = HoldingDetail(
            code=code,
            name=name,
            quantity=qty,
            cost_price=round(cost_price, 2),
            current_price=round(current_price, 2),
            market_value=round(market_value, 2),
            profit=round(profit, 2),
            profit_rate=round(profit_rate, 2),
            bought_at=h.get('latest_bought_at', ''),
            can_sell=qty,
            on_cooldown=False,
            cooldown_days_remaining=0,
        )
        holding_details.append(detail)
        total_market_value += market_value
        total_profit += profit

    cash = db.get_account().get('cash', 0)

    return PortfolioResponse(
        holdings=holding_details,
        total_market_value=round(total_market_value, 2),
        total_profit=round(total_profit, 2),
        cash=round(cash, 2),
        total_assets=round(cash + total_market_value, 2)
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
    return UserProfileResponse(profile=profile)


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


@router.get("/api/backtest/full", response_model=FullBacktestResponse)
async def full_backtest(
    start_date: str = Query(..., regex="^\\d{4}-\\d{2}-\\d{2}$"),
    end_date: str = Query(..., regex="^\\d{4}-\\d{2}-\\d{2}$"),
    strategy: str = Query("top", pattern="^(top|value|growth|momentum|quality|rising_cp|hybrid)$"),
    top_n: int = Query(10, ge=1, le=50),
    initial_capital: float = Query(20000, gt=0)
):
    """
    完整回测

    基于历史战力数据进行真实收益率回测，返回：
    - 总收益率
    - 年化收益率
    - 夏普比率
    - 最大回撤
    - 胜率
    - 每日净值曲线
    - 交易记录
    """
    from backend.backtester.full_backtest import FullBacktestEngine

    engine = FullBacktestEngine()
    stats = engine.run(
        start_date=start_date,
        end_date=end_date,
        strategy_name=strategy,
        top_n=top_n,
        initial_capital=initial_capital
    )

    return FullBacktestResponse(
        start_date=start_date,
        end_date=end_date,
        strategy=strategy,
        top_n=top_n,
        initial_capital=stats.initial_capital,
        final_value=stats.final_value,
        total_return=round(stats.total_return, 2),
        annualized_return=round(stats.annualized_return, 2),
        sharpe_ratio=round(stats.sharpe_ratio, 2),
        max_drawdown=round(stats.max_drawdown, 2),
        win_rate=round(stats.win_rate, 2),
        total_trades=stats.total_trades,
        equity_curve=[EquityPointResponse(**eq) for eq in stats.equity_curve],
        trades=[BacktestTradeResponse(**t) for t in stats.trades]
    )


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
            # 获取 StockSelector 的核心池+活跃池股票代码集合
            selector = get_stock_selector()
            analysable_codes = set(selector.get_all_analysable_codes())
            print(f"[刷新] StockSelector 可分析股票: {len(analysable_codes)} 只")

            # 获取足够多的股票数据（按成交额排序）
            all_stocks_data = get_stock_data_api(limit=1500)
            print(f"[刷新] 获取股票数据: {len(all_stocks_data)} 只")

            # 过滤出可分析股票
            stocks_data = []
            found_codes = set()
            missing_codes = set()

            for data in all_stocks_data:
                raw_code = data.get('code', '')
                code = raw_code
                if code.startswith('sh'):
                    code = code[2:]
                elif code.startswith('sz'):
                    code = code[2:]

                if code in analysable_codes:
                    stocks_data.append(data)
                    found_codes.add(code)

            missing_codes = analysable_codes - found_codes
            if missing_codes:
                print(f"[刷新] 警告: {len(missing_codes)} 只可分析股票未获取到数据")
                # 尝试逐个获取缺失的股票
                for code in list(missing_codes)[:100]:  # 最多补100只
                    try:
                        single = get_single_stock_data(code)
                        if single:
                            stocks_data.append(single)
                    except:
                        pass

            print(f"[刷新] 最终加载: {len(stocks_data)} 只")

            # 清空并重新加载
            cp_engine.stocks = []

            for data in stocks_data:
                # 标准化代码：去除 sh/sz 前缀
                raw_code = data.get('code', '')
                code = raw_code
                if code.startswith('sh'):
                    code = code[2:]
                elif code.startswith('sz'):
                    code = code[2:]

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


# ==================== 批量更新财务数据 v19.8 ====================

@router.post("/api/refresh/financials")
async def refresh_financials():
    """
    批量更新所有股票的PE/ROE数据 v19.8

    使用Tushare一次性获取所有股票的每日指标（PE/PB），
    并获取财务指标（ROE等）来更新stocks表。

    注意：此接口需要较长时间（可能需要几分钟），请耐心等待。
    """
    from backend.data_manager.fetcher import batch_update_stocks_pe_roe

    try:
        result = batch_update_stocks_pe_roe()

        if result.get('error'):
            raise HTTPException(status_code=500, detail=result['error'])

        return {
            "success": True,
            "total": result['total'],
            "pe_updated": result['pe_updated'],
            "roe_updated": result['roe_updated'],
            "message": f"共{result['total']}只股票, PE有效{result['success']}只, ROE有效{result['roe_updated']}只"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


# ==================== 持仓快照 v19.7 ====================

@router.post("/api/snapshot/record")
async def record_holding_snapshot(date: str = Query(None, description="快照日期，默认今日")):
    """记录每日持仓快照（收盘后调用）

    用于回测验证，记录持仓的收盘市值和盈亏
    """
    try:
        from backend.backtester.verification import BacktestVerifier

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
        from backend.backtester.verification import BacktestVerifier

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
        from backend.backtester.verification import BacktestVerifier

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
        from backend.backtester.verification import BacktestVerifier

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


# ==================== 预测引擎API ====================

@router.get("/api/prediction/gain/top", response_model=GainPredictionResponse)
async def get_gain_predictions_top(
    limit: int = Query(50, ge=1, le=200, description="返回数量")
):
    """获取涨幅预测TOP N

    基于技术指标规则模型预测股票未来N日涨幅
    """
    try:
        def _run_prediction():
            from backend.engine.gain_predictor import GainPredictor
            from backend.data_manager.duckdb_store import get_klines_bulk
            from backend.data_manager import get_stock_list

            stock_list = get_stock_list()
            codes = [s.get('code') for s in stock_list if s.get('code')]

            # 单次连接批量拉取所有股票K线，避免 5000+ 次连接开销
            bulk = get_klines_bulk(codes, days=60)

            klines_dict = {}
            for code, df in bulk.items():
                if not df.empty:
                    records = df.to_dict('records')
                    klines_dict[code] = list(reversed(records))

            predictor = GainPredictor()
            return predictor.predict(klines_dict)

        result = await asyncio.get_event_loop().run_in_executor(None, _run_prediction)

        # 取TOP N
        top_predictions = result.predictions[:limit]

        return GainPredictionResponse(
            predictions=[
                GainPredictionItem(
                    code=p.code,
                    name=p.name,
                    predicted_gain_3d=p.predicted_gain_3d,
                    predicted_gain_5d=p.predicted_gain_5d,
                    confidence=p.confidence,
                    confidence_interval_3d=p.confidence_interval_3d,
                    confidence_interval_5d=p.confidence_interval_5d,
                    features=p.features,
                    model_version=p.model_version,
                )
                for p in top_predictions
            ],
            calculated_at=result.calculated_at,
            data_timestamp=result.data_timestamp,
            stock_count=len(top_predictions),
            distribution=result.distribution,
            avg_confidence=result.avg_confidence,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"涨幅预测失败: {str(e)}")


@router.get("/api/prediction/probability/top", response_model=ProbabilityPredictionResponse)
async def get_probability_predictions_top(
    limit: int = Query(50, ge=1, le=200, description="返回数量")
):
    """获取上涨概率预测TOP N

    基于技术指标规则模型预测股票未来N日上涨概率
    """
    try:
        def _run_prediction():
            from backend.engine.probability_predictor import ProbabilityPredictor
            from backend.data_manager.duckdb_store import get_klines_bulk
            from backend.data_manager import get_stock_list

            stock_list = get_stock_list()
            codes = [s.get('code') for s in stock_list if s.get('code')]

            # 单次连接批量拉取所有股票K线，避免 5000+ 次连接开销
            bulk = get_klines_bulk(codes, days=60)

            klines_dict = {}
            for code, df in bulk.items():
                if not df.empty:
                    records = df.to_dict('records')
                    klines_dict[code] = list(reversed(records))

            predictor = ProbabilityPredictor()
            return predictor.predict(klines_dict)

        result = await asyncio.get_event_loop().run_in_executor(None, _run_prediction)

        # 取TOP N
        top_predictions = result.predictions[:limit]

        return ProbabilityPredictionResponse(
            predictions=[
                ProbabilityPredictionItem(
                    code=p.code,
                    name=p.name,
                    up_probability_3d=p.up_probability_3d,
                    up_probability_5d=p.up_probability_5d,
                    confidence=p.confidence,
                    risk_level=p.risk_level,
                    features=p.features,
                    model_version=p.model_version,
                )
                for p in top_predictions
            ],
            calculated_at=result.calculated_at,
            data_timestamp=result.data_timestamp,
            stock_count=len(top_predictions),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上涨概率预测失败: {str(e)}")


@router.get("/api/prediction/gain/{code}")
async def get_gain_prediction(code: str):
    """获取单只股票的涨幅预测"""
    try:
        from backend.engine.gain_predictor import GainPredictor
        from backend.data_manager.duckdb_store import get_klines

        klines_result = get_klines(code, days=60)
        if not klines_result.success or klines_result.data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的数据")

        # DuckDB返回按日期降序，需要反转成升序以匹配predictor期望
        klines = list(reversed(klines_result.data.to_dict('records')))
        predictor = GainPredictor()
        result = predictor.predict({code: klines})

        if not result.predictions:
            raise HTTPException(status_code=404, detail=f"无法预测股票 {code}")

        p = result.predictions[0]
        return {
            "code": p.code,
            "name": p.name,
            "predicted_gain_3d": p.predicted_gain_3d,
            "predicted_gain_5d": p.predicted_gain_5d,
            "confidence": p.confidence,
            "confidence_interval_3d": p.confidence_interval_3d,
            "confidence_interval_5d": p.confidence_interval_5d,
            "features": p.features,
            "model_version": p.model_version,
            "data_timestamp": result.data_timestamp,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取涨幅预测失败: {str(e)}")


@router.get("/api/prediction/probability/{code}")
async def get_probability_prediction(code: str):
    """获取单只股票的上涨概率预测"""
    try:
        from backend.engine.probability_predictor import ProbabilityPredictor
        from backend.data_manager.duckdb_store import get_klines

        klines_result = get_klines(code, days=60)
        if not klines_result.success or klines_result.data.empty:
            raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的数据")

        # DuckDB返回按日期降序，需要反转成升序以匹配predictor期望
        klines = list(reversed(klines_result.data.to_dict('records')))
        predictor = ProbabilityPredictor()
        result = predictor.predict({code: klines})

        if not result.predictions:
            raise HTTPException(status_code=404, detail=f"无法预测股票 {code}")

        p = result.predictions[0]
        return {
            "code": p.code,
            "name": p.name,
            "up_probability_3d": p.up_probability_3d,
            "up_probability_5d": p.up_probability_5d,
            "confidence": p.confidence,
            "risk_level": p.risk_level,
            "features": p.features,
            "model_version": p.model_version,
            "data_timestamp": result.data_timestamp,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取上涨概率预测失败: {str(e)}")


# ==================== 预测验证API ====================

@router.get("/api/verify/gain_accuracy")
async def verify_gain_prediction_accuracy(
    date: str = Query(None, description="基准日期"),
    holding_days: int = Query(5, ge=1, le=30, description="持有天数"),
    top_n: int = Query(20, ge=1, le=100, description="验证前N只")
):
    """验证涨幅预测准确性

    比较预测涨幅最高的股票组和实际涨幅表现
    """
    try:
        from backend.backtester.verification import verify_gain_prediction_accuracy

        result = verify_gain_prediction_accuracy(
            db=_db,
            date=date,
            holding_days=holding_days,
            top_n=top_n
        )

        return {
            "period": result.period,
            "total_stocks": result.total_stocks,
            "avg_predicted_gain": result.avg_predicted_gain,
            "avg_actual_gain": result.avg_actual_gain,
            "prediction_error": result.prediction_error,
            "mean_absolute_error": result.mean_absolute_error,
            "accuracy_direction": result.accuracy_direction,
            "top_predicted_avg": result.top_predicted_avg,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证涨幅预测失败: {str(e)}")


@router.get("/api/verify/probability_accuracy")
async def verify_probability_prediction_accuracy(
    date: str = Query(None, description="基准日期"),
    high_prob_threshold: float = Query(0.6, ge=0.5, le=0.9, description="高概率阈值"),
    low_prob_threshold: float = Query(0.4, ge=0.1, le=0.5, description="低概率阈值")
):
    """验证上涨概率预测准确性

    比较高概率组和低概率组的实际涨跌比例
    """
    try:
        from backend.backtester.verification import verify_probability_prediction_accuracy

        result = verify_probability_prediction_accuracy(
            db=_db,
            date=date,
            high_prob_threshold=high_prob_threshold,
            low_prob_threshold=low_prob_threshold
        )

        return {
            "period": result.period,
            "total_stocks": result.total_stocks,
            "high_prob_avg_actual": result.high_prob_avg_actual,
            "low_prob_avg_actual": result.low_prob_avg_actual,
            "calibration_error": result.calibration_error,
            "direction_accuracy": result.direction_accuracy,
            "high_prob_accuracy": result.high_prob_accuracy,
            "low_prob_accuracy": result.low_prob_accuracy,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证上涨概率预测失败: {str(e)}")
