"""System域路由 — 健康、池统计、刷新、快照、验证"""
import asyncio
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime

from backend.api.dependencies import (
    cp_engine, db, account, portfolio, trader,
    cp_lock,
    get_stock_selector,
    executor,
)
import backend.api.dependencies as _deps
from backend.data_manager.cache import get_cache_manager
from backend.data_manager.fetcher import get_stock_data_api, get_single_stock_data
from backend.engine.cp_engine import create_stock_from_raw
from backend.engine.cp_engine.history import save_history
from backend.models.schemas import HealthResponse, PoolStatsResponse

router = APIRouter()


# ==================== 健康检查 ====================

@router.get("/api/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    cache_stats = get_cache_manager().get_cache_stats()
    now = datetime.now().isoformat()
    return HealthResponse(
        status="ok",
        timestamp=now,
        data_fresh=_deps.last_update_time is not None,
        last_update=_deps.last_update_time or now,
        stocks_count=len(cp_engine.stocks)
    )


# ==================== 股票池统计 ====================

@router.get("/api/pool/stats", response_model=PoolStatsResponse)
async def get_pool_stats():
    """获取股票池统计信息"""
    from backend.stock_selector.stock_selector import get_stock_selector
    selector = get_stock_selector()
    stats = selector.get_pool_stats()
    return PoolStatsResponse(
        core_count=stats.get('core', 0),
        active_count=stats.get('active', 0),
        observe_count=stats.get('observe', 0),
        total_count=stats.get('core', 0) + stats.get('active', 0) + stats.get('observe', 0)
    )


@router.post("/api/refresh")
async def refresh_data(limit: int = Query(200, ge=1, le=500)):
    """刷新数据"""
    async with cp_lock:
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
                    except Exception:
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
            db.batch_upsert_stocks(stock_dicts)

            # 记录持仓快照 v19.7
            stocks_data = {s['code']: {'price': s['price'], 'total_cp': s['total_cp']} for s in stock_dicts}
            snapshot_count = db.record_daily_holding_snapshots(date=datetime.now().strftime("%Y-%m-%d"), stocks_data=stocks_data)

            _deps.last_update_time = datetime.now().isoformat()

            return {
                "success": True,
                "stocks_updated": len(cp_engine.stocks),
                "snapshots_recorded": snapshot_count,
                "updated_at": _deps.last_update_time
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
        count = db.record_daily_holding_snapshots(date=date, stocks_data=stocks_data)

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

        verifier = BacktestVerifier(db)
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

        verifier = BacktestVerifier(db)
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

        verifier = BacktestVerifier(db)
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
