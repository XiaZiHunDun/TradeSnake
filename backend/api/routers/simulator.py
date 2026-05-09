"""Simulator域路由 — 账户、持仓、交易"""
from fastapi import APIRouter, HTTPException, Query
from backend.api.dependencies import db, account, portfolio, trader
from backend.models.schemas import (
    AccountResponse, HoldingDetail, PortfolioResponse,
    TradeRequest, TradeResponse, TradeHistoryResponse,
    UserProfile, UserProfileResponse,
)

router = APIRouter()

# ==================== 账户 ====================

@router.get("/api/account", response_model=AccountResponse)
async def get_account():
    """获取账户信息（使用本地SQLite价格，快速响应）"""
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
            can_sell=max(0, qty - db.get_today_bought_quantity(lookup_code)),
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
    """买入股票

    字段说明:
    - total_amount: 成交金额 (gross, 印花税=0)
    - cost_detail.total_cost: 实际扣款 (net, 含佣金+过户费)
    """
    result = trader.buy(req.code, req.quantity, price=req.price, order_type=req.order_type)
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
        total_amount=result.get('price', 0) * result.get('quantity', 0),  # 成交金额 (gross)
        cost_detail={
            'commission': result.get('commission', 0),
            'stamp_tax': 0,  # 买入无印花税
            'transfer_fee': result.get('transfer_fee', 0),
            'total_cost': result.get('total_cost', 0),  # 实际扣款 (net)
        },
        cash_after=result.get('remaining_cash', 0),
        message=''
    )


@router.post("/api/trade/sell", response_model=TradeResponse)
async def trade_sell(req: TradeRequest):
    """卖出股票

    字段说明:
    - total_amount: 成交金额 (gross, 卖出得到的总金额)
    - cost_detail.total_cost: 实际到账 (net, 扣除佣金+印花税+过户费后)
    """
    result = trader.sell(req.code, req.quantity, price=req.price, order_type=req.order_type)
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
        total_amount=result.get('sell_value', 0),  # 成交金额 (gross)
        cost_detail={
            'commission': result.get('commission', 0),
            'stamp_tax': result.get('stamp_tax', 0),
            'transfer_fee': result.get('transfer_fee', 0),
            'total_cost': result.get('total_proceeds', 0),  # 实际到账 (net)
        },
        cash_after=result.get('remaining_cash', 0),
        message=''
    )


@router.get("/api/trades", response_model=TradeHistoryResponse)
async def get_trades(limit: int = Query(50, ge=1, le=200)):
    """获取交易历史"""
    trades = trader.get_trade_history(limit)
    return TradeHistoryResponse(trades=trades, total_count=len(trades))


# ==================== 用户配置 ====================

@router.get("/api/user/profile", response_model=UserProfileResponse)
async def get_user_profile():
    """获取用户配置"""
    profile = db.get_user_profile()
    return UserProfileResponse(profile=profile)


@router.put("/api/user/profile")
async def update_user_profile(profile: UserProfile):
    """更新用户配置"""
    db.save_user_profile(profile.dict())
    return {"success": True}


# ==================== 风控 API ====================

@router.post("/api/simulator/risk_check")
async def risk_check():
    """手动触发风控检查（止损/尾随止损/组合熔断）"""
    executed = trader.check_risk_and_execute()
    return {"triggered": len(executed), "trades": executed}


@router.get("/api/simulator/risk_config")
async def get_risk_config():
    """获取当前风控配置"""
    from backend.engine.cp_engine.constants import RISK_MANAGEMENT
    return RISK_MANAGEMENT


@router.get("/api/simulator/market_regime")
async def get_market_regime():
    """获取当前市场环境（bull/bear/unknown）"""
    regime = trader.get_market_regime()
    limit = trader.get_position_limit()
    return {"regime": regime, "position_limit": limit}


@router.get("/api/simulator/kelly/{code}")
async def get_kelly_size(code: str):
    """获取 Kelly 建议手数"""
    from backend.data_manager.fetcher import get_single_stock_data
    stock = get_single_stock_data(code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"股票{code}不存在")
    price = stock.get('price', 0)
    if price <= 0:
        raise HTTPException(status_code=400, detail=f"股票{code}价格无效")
    shares = trader.get_kelly_size(code, price)
    return {"code": code, "price": price, "kelly_shares": shares}
