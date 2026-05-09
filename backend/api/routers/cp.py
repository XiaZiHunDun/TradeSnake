"""CP域路由 — 战力、推荐、换股"""
import backend.api.dependencies as _deps
from fastapi import APIRouter, HTTPException, Query
from typing import List
from datetime import datetime

from backend.api.dependencies import (
    cp_engine, recommend_engine, portfolio as _portfolio,
)
from backend.models.schemas import (
    CPListResponse, SingleStockResponse, StockCPData,
    SwapSuggestion, RecommendResponse, CPExplanationResponse,
    MarketStatsResponse,
)
from backend.engine.cp_engine import StockCP

router = APIRouter()


def _build_stock_response(stock: StockCP) -> SingleStockResponse:
    """Build SingleStockResponse from StockCP (same as original)"""
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
        high=stock.high,
        low=stock.low,
        data_quality=stock.data_quality,
        board_type=stock.board_type,
        board_name=stock.board_name,
        sector=stock.sector,
        can_trade_newbie=stock.can_trade_newbie,
        trade_requirement=stock.trade_requirement,
        current_ratio=stock.current_ratio,
        interest_coverage=stock.interest_coverage,
        deducted_net_profit=stock.deducted_net_profit,
    )


# ==================== 战力榜 ====================

@router.get("/api/cp/top", response_model=CPListResponse)
async def get_cp_top(limit: int = Query(50, ge=1, le=200)):
    """获取战力榜TOP N"""
    if not cp_engine.stocks:
        return CPListResponse(data=[], total=0, updated_at="")
    stocks = cp_engine.get_top(limit)
    return CPListResponse(
        data=[_build_stock_response(s) for s in stocks],
        total=len(cp_engine.stocks),
        updated_at=_deps.last_update_time or datetime.now().isoformat()
    )


@router.get("/api/cp/bottom", response_model=CPListResponse)
async def get_cp_bottom(limit: int = Query(10, ge=1, le=50)):
    """获取避雷榜（战力最弱）BOTTOM N"""
    if not cp_engine.stocks:
        return CPListResponse(data=[], total=0, updated_at="")
    stocks = cp_engine.get_bottom(limit)
    return CPListResponse(
        data=[_build_stock_response(s) for s in stocks],
        total=len(cp_engine.stocks),
        updated_at=_deps.last_update_time or datetime.now().isoformat()
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
    stocks = cp_engine.stocks
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

    stocks = cp_engine.stocks
    if exclude_holdings and holding_codes:
        stocks = [s for s in stocks if s.code not in holding_codes]

    if fusion:
        principal = 100000
        fusion_signals = recommend_engine.get_buy_signals(
            stocks=stocks,
            principal=principal,
            risk_preference=risk_preference,
            limit=20,
            use_fusion=True
        )

        recs = []
        for sig in fusion_signals:
            stock_obj = next((s for s in stocks if s.code == sig['code']), None)
            if stock_obj:
                resp = _build_stock_response(stock_obj)
                resp_dict = resp.model_dump()
                resp_dict['kelly_position'] = sig.get('kelly_position', 0)
                resp_dict['predicted_gain_5d'] = sig.get('predicted_gain_5d', 0)
                resp_dict['up_probability_5d'] = sig.get('up_probability_5d', 0)
                resp_dict['prediction_confidence'] = sig.get('prediction_confidence', 0)
                resp_dict['fused_score'] = sig.get('fused_score', 0)
                recs.append(resp_dict)
    else:
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
            'net_benefit': s.get('net_profit', 0),
            'trade_cost': s.get('trade_cost', 0),
            'holding_days_equivalent': s.get('breakeven_days', 0),
            'action_level': s.get('action_level', ''),
            'action_label': s.get('action_label', ''),
        })

    return mapped_suggestions
