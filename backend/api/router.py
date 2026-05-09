"""API路由聚合器 — 组合所有子路由"""
from fastapi import APIRouter
from backend.api.routers import cp, history, simulator, backtest, risk, prediction, system

router = APIRouter()

router.include_router(cp.router, tags=["战力/推荐/换股"])
router.include_router(history.router, tags=["历史数据"])
router.include_router(simulator.router, tags=["模拟交易"])
router.include_router(backtest.router, tags=["回测优化"])
router.include_router(risk.router, tags=["风险分析"])
router.include_router(prediction.router, tags=["预测分析"])
router.include_router(system.router, tags=["系统管理"])
