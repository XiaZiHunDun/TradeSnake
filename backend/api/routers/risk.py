"""Risk域路由 — 风险分析"""
from fastapi import APIRouter, HTTPException

from backend.api.dependencies import cp_engine, portfolio as _portfolio, account, trader, db
from backend.engine.cp_engine.risk_analyzer import RiskAnalyzer

router = APIRouter()


@router.get("/api/risk/report")
async def get_risk_report():
    """获取风险报告"""
    holdings = _portfolio.get_holdings()
    market_cp = RiskAnalyzer.get_market_cp(cp_engine.stocks)
    capital = account.cash

    return RiskAnalyzer.generate_risk_report(
        db=db,
        holdings=holdings,
        all_stocks=cp_engine.stocks,
        market_cp=market_cp,
        capital=capital
    )


@router.get("/api/risk/break-even/{code}")
async def get_break_even(code: str):
    """计算解套所需涨幅"""
    position = trader.get_position(code)
    if not position:
        raise HTTPException(status_code=404, detail=f"未持有{code}")

    cost_price = position.get('cost_price', 0)
    current_price = position.get('current_price', 0)

    return RiskAnalyzer.calculate_break_even(cost_price, current_price)
