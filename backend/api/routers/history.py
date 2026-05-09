"""历史域路由 — 战力历史"""
from fastapi import APIRouter, Query

from backend.engine.cp_engine.history import (
    get_cp_changes, get_stock_history,
    get_historical_rankings,
)

router = APIRouter()


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
