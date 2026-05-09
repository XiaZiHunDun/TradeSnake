"""Prediction域路由 — 预测模型"""
import asyncio
from fastapi import APIRouter, HTTPException, Query

from backend.api.dependencies import db
from backend.models.schemas import (
    GainPredictionResponse, GainPredictionItem,
    ProbabilityPredictionResponse, ProbabilityPredictionItem,
)

router = APIRouter()


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
            db=db,
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
            db=db,
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
