"""Backtest域路由 — 回测、优化、因子分析"""
import asyncio
import uuid
from typing import Dict
from fastapi import APIRouter, HTTPException, Query

from backend.api.dependencies import backtest_engine
from backend.models.schemas import FullBacktestResponse, BacktestTradeResponse, EquityPointResponse

router = APIRouter()

# 存储异步任务状态
_optimization_tasks: Dict[str, dict] = {}

# ==================== 回测 ====================


@router.get("/api/backtest/simple")
async def backtest_simple(
    start_date: str,
    end_date: str,
    holding_days: int = Query(30, ge=1, le=365),
    top_n: int = Query(10, ge=1, le=50)
):
    """简单回测"""
    return backtest_engine.calculate_simple_backtest(start_date, end_date, holding_days, top_n)


@router.get("/api/backtest/compare")
async def backtest_compare(
    start_date: str,
    end_date: str,
    holding_days: int = Query(30, ge=1, le=365)
):
    """对比回测"""
    return backtest_engine.calculate_compare_backtest(start_date, end_date, holding_days)


@router.get("/api/backtest/benchmark")
async def backtest_benchmark(
    start_date: str,
    end_date: str,
    benchmark: str = Query("hs300", pattern="^(hs300|zz500|equal_weight)$")
):
    """基准回测"""
    return backtest_engine.calculate_benchmark_backtest(start_date, end_date, benchmark)


@router.get("/api/backtest/full", response_model=FullBacktestResponse)
async def full_backtest(
    start_date: str = Query(..., pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    end_date: str = Query(..., pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    strategy: str = Query("top", pattern="^(top|value|growth|momentum|rising_cp|hybrid)$"),
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
        trades=[BacktestTradeResponse(**t) for t in stats.trades],
        completed_pnls=stats.completed_pnls
    )


# ==================== 策略优化 ====================

async def _run_optimization(task_id: str, request: dict):
    """后台执行优化流程"""
    from backend.backtester.strategy_comparator import StrategyComparisonResult
    from backend.backtester.parameter_scanner import ScanResult
    from backend.backtester.factor_attributor import FactorAttributor

    try:
        start_date = request.get('start_date', '2024-01-01')
        end_date = request.get('end_date', '2024-12-31')
        val_start = request.get('val_start', '2025-01-01')
        val_end = request.get('val_end', '2025-06-30')

        # 阶段1：策略对比
        _optimization_tasks[task_id]['progress'] = 'stage 1/3 - comparing strategies'
        comparator = StrategyComparator()
        compare_results = comparator.compare_strategies(
            start_date=start_date,
            end_date=end_date
        )
        best_strategy = comparator.get_best_strategy(compare_results)

        # 阶段2：参数扫描
        _optimization_tasks[task_id]['progress'] = 'stage 2/3 - parameter scanning'
        scanner = ParameterScanner()
        scan_result = scanner.optimize(
            strategy_name=best_strategy,
            train_start=start_date,
            train_end=end_date,
            val_start=val_start,
            val_end=val_end
        )

        # 阶段3：因子分析
        _optimization_tasks[task_id]['progress'] = 'stage 3/3 - factor analysis'
        attributor = FactorAttributor()
        factor_result = attributor.analyze(
            factor_data={},  # TODO: 需要传入实际的因子数据
            return_data={},
            factor_names=['growth_score', 'value_score', 'momentum_score', 'quality_score']
        )

        _optimization_tasks[task_id]['status'] = 'completed'
        _optimization_tasks[task_id]['progress'] = 'completed'
        _optimization_tasks[task_id]['result'] = {
            'best_strategy': best_strategy,
            'compare_results': {k: v.__dict__ for k, v in compare_results.items()},
            'scan_result': scan_result.__dict__ if scan_result else None,
            'factor_result': factor_result
        }

    except Exception as e:
        _optimization_tasks[task_id]['status'] = 'failed'
        _optimization_tasks[task_id]['error'] = str(e)


@router.post("/api/backtest/optimize")
async def optimize_strategy(request: dict):
    """
    触发策略优化流程（异步）

    Request body:
    {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "val_start": "2025-01-01",
        "val_end": "2025-06-30"
    }

    Returns:
    {"task_id": "xxx", "status": "running"}
    """
    task_id = str(uuid.uuid4())
    _optimization_tasks[task_id] = {
        'status': 'running',
        'progress': 'initializing',
        'result': None,
        'error': None
    }

    # 异步执行（不阻塞）
    asyncio.create_task(_run_optimization(task_id, request))

    return {"task_id": task_id, "status": "running"}


@router.get("/api/backtest/status/{task_id}")
async def get_optimization_status(task_id: str):
    """查询优化任务状态"""
    if task_id not in _optimization_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task = _optimization_tasks[task_id]
    # 转换状态为JSON安全格式
    import json
    result = {
        'status': task.get('status'),
        'progress': task.get('progress'),
        'error': task.get('error'),
    }
    if task.get('result'):
        result['result'] = _convert_to_json_safe(task['result'])
    return result


def _convert_to_json_safe(obj):
    """递归转换对象为JSON安全的Python原生类型"""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _convert_to_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_json_safe(item) for item in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif hasattr(obj, '__dataclass_fields__'):
        # dataclass 转 dict
        return {f: _convert_to_json_safe(getattr(obj, f)) for f in obj.__dataclass_fields__}
    elif hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    return obj


@router.get("/api/backtest/factor_analysis")
async def get_factor_analysis(
    start_date: str = Query(..., pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    end_date: str = Query(..., pattern="^\\d{4}-\\d{2}-\\d{2}$")
):
    """获取因子归因分析

    基于cp_history中的战力因子数据和K线收益数据进行IC分析。
    因子：total_cp, growth_score, value_score, momentum_score, quality_score, change_pct, cp_change
    收益：下一天收益率
    """
    from backend.backtester.factor_attributor import ICResult, GroupReturnResult
    from backend.data_manager.cp_history_store import get_cp_history_store
    from backend.data_manager.duckdb_store import get_duckdb_store
    from scipy import stats as scipy_stats

    cp_store = get_cp_history_store()
    duckdb = get_duckdb_store()

    # 获取日期范围内的所有日期
    conn = cp_store._get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT recorded_at FROM cp_history
        WHERE recorded_at >= ? AND recorded_at <= ?
        ORDER BY recorded_at
    """, (start_date, end_date))
    date_rows = cursor.fetchall()
    conn.close()

    if len(date_rows) < 10:
        return {
            'ic_analysis': [],
            'group_returns': {},
            'correlation_matrix': {},
            'recommendation': f'数据不足（{len(date_rows)}天），至少需要10天数据'
        }

    dates = [row[0] for row in date_rows]

    # 因子列表
    factor_names = ['total_cp', 'growth_score', 'value_score',
                    'momentum_score', 'quality_score', 'change_pct', 'cp_change']

    # 收集所有有K线数据的股票在某一天的因子值和收益率
    all_stock_data = []

    for i, signal_date in enumerate(dates[:-1]):
        next_date = dates[i + 1]
        cp_data = cp_store.get_cp_history_by_date(signal_date)
        if not cp_data:
            continue

        codes = [s['code'] for s in cp_data]

        # 使用 get_klines_bulk_for_date 确保信号日和下一天数据都在
        try:
            klines = duckdb.get_klines_bulk_for_date(codes, end_date=next_date, days=10)
        except Exception:
            continue

        for stock in cp_data:
            code = stock['code']
            kl = klines.get(code)
            if kl is None or kl.empty:
                continue

            # 构建日期->收盘价字典
            kl_dict = {}
            for _, row in kl.iterrows():
                d = str(row.get('trade_date', ''))[:10]  # 取日期部分 "YYYY-MM-DD"
                kl_dict[d] = row.get('close', 0)

            signal_close = kl_dict.get(signal_date, 0)
            next_close = kl_dict.get(next_date, 0)

            if signal_close > 0 and next_close > 0:
                ret = (next_close - signal_close) / signal_close * 100
                all_stock_data.append({
                    'date': next_date,
                    'code': code,
                    'factors': {
                        'total_cp': stock.get('total_cp', 0),
                        'growth_score': stock.get('growth_score', 0),
                        'value_score': stock.get('value_score', 0),
                        'momentum_score': stock.get('momentum_score', 0),
                        'quality_score': stock.get('quality_score', 0),
                        'change_pct': stock.get('change_pct', 0),
                        'cp_change': stock.get('cp_change', 0),
                    },
                    'return': ret
                })

    if len(all_stock_data) < 50:
        return {
            'ic_analysis': [],
            'group_returns': {},
            'correlation_matrix': {},
            'recommendation': f'有效数据点不足（{len(all_stock_data)}个），至少需要50个'
        }

    # 按因子分组计算IC和分组收益
    ic_results = []
    group_results = {}
    correlation_matrix = {}

    for fname in factor_names:
        factors = [d['factors'].get(fname, 0) for d in all_stock_data]
        returns = [d['return'] for d in all_stock_data]

        if len(factors) < 10:
            continue

        ic, p_value = scipy_stats.spearmanr(factors, returns)

        ir = abs(ic) / 0.05 if ic != 0 else 0
        direction = 'positive' if ic > 0.02 else ('negative' if ic < -0.02 else 'neutral')

        ic_results.append(ICResult(
            factor_name=fname,
            ic_mean=round(ic, 4) if not (ic != ic) else 0,
            ic_std=0.0,
            ir=round(ir, 2),
            direction=direction,
            p_value=round(p_value, 4) if not (p_value != p_value) else 1.0
        ))

        # 分组收益计算
        sorted_pairs = sorted(zip(factors, returns), key=lambda x: x[0])
        n_groups = 5
        n = len(sorted_pairs) // n_groups
        groups_list = []
        for gi in range(n_groups):
            start_idx = gi * n
            end_idx = start_idx + n if gi < n_groups - 1 else len(sorted_pairs)
            group_returns = [p[1] for p in sorted_pairs[start_idx:end_idx]]
            if group_returns:
                groups_list.append(GroupReturnResult(
                    group=f"Q{gi + 1}",
                    avg_return=round(sum(group_returns) / len(group_returns), 4),
                    n_samples=len(group_returns)
                ))
        group_results[fname] = groups_list

    # 相关性矩阵
    for i, f1 in enumerate(factor_names):
        for f2 in factor_names[i+1:]:
            f1_vals = [d['factors'].get(f1, 0) for d in all_stock_data]
            f2_vals = [d['factors'].get(f2, 0) for d in all_stock_data]
            if len(f1_vals) > 10:
                corr, _ = scipy_stats.pearsonr(f1_vals, f2_vals)
                if not (corr != corr):
                    correlation_matrix[f'{f1}-{f2}'] = round(corr, 3)

    recommendation = '; '.join([
        f"{ic.factor_name} IR={ic.ir}"
        for ic in sorted(ic_results, key=lambda x: x.ir, reverse=True)[:3]
    ]) if ic_results else '数据不足'

    # 清理 NaN/inf 值，确保 JSON 兼容
    def clean_value(v):
        import math
        if isinstance(v, float):
            if math.isnan(v) or math.isinf(v):
                return None
        return v

    result = {
        'ic_analysis': [
            {k: clean_value(v) for k, v in ic.__dict__.items()}
            for ic in ic_results
        ],
        'group_returns': {
            k: [
                {gk: clean_value(gv) for gk, gv in g.__dict__.items()}
                for g in v
            ]
            for k, v in group_results.items()
        },
        'correlation_matrix': {
            k: clean_value(v) for k, v in correlation_matrix.items()
        },
        'recommendation': recommendation
    }
    return result


# ==================== Walk-Forward 回测 ====================

@router.get("/api/backtest/walk_forward")
async def walk_forward_backtest(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    top_n: int = Query(6, description="持仓数量"),
    rebalance_freq: int = Query(5, description="换仓频率（交易日）"),
    stop_loss: float = Query(-0.07, description="止损阈值"),
):
    """Walk-forward 回测 — 滚动窗口训练+测试，避免前瞻偏差"""
    from backend.backtester.walk_forward import WalkForwardBacktester, WalkForwardConfig
    config = WalkForwardConfig(
        top_n=top_n, rebalance_freq=rebalance_freq, stop_loss=stop_loss,
    )
    backtester = WalkForwardBacktester(config)
    report = backtester.run(start_date, end_date)
    if not report.folds:
        raise HTTPException(status_code=400, detail="数据不足，无法完成 walk-forward 回测")
    return {
        "total_return": round(report.total_return, 2),
        "annual_return": round(report.annual_return, 2),
        "sharpe": round(report.sharpe, 2),
        "sortino": round(report.sortino, 2),
        "max_drawdown": round(report.max_drawdown, 2),
        "calmar": round(report.calmar, 2),
        "total_trades": report.total_trades,
        "turnover_rate": round(report.turnover_rate, 1),
        "total_fees": round(report.total_fees, 2),
        "fee_ratio": round(report.fee_ratio, 2),
        "folds": [
            {
                "fold_id": f.fold_id,
                "train": f"{f.train_start}~{f.train_end}",
                "test": f"{f.test_start}~{f.test_end}",
                "return": round(f.total_return, 2),
                "sharpe": round(f.sharpe, 2),
                "max_drawdown": round(f.max_drawdown, 2),
                "trades": f.n_trades,
            }
            for f in report.folds
        ],
    }
